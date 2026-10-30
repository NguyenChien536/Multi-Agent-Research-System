"""Structured scholarly search and normalization for literature-review tasks."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from html import unescape
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.tools.search_models import SearchResult
from app.services.provider_budget import (
    assert_task_active, reserve_provider_call, settle_provider_call,
    ProviderBudgetExceeded, ResearchTaskStopped,
)

logger = logging.getLogger(__name__)

OPENALEX_API = "https://api.openalex.org/works"
CROSSREF_API = "https://api.crossref.org/works"


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for word, indexes in inverted_index.items():
        for index in indexes:
            positions[index] = word
    return " ".join(positions[index] for index in sorted(positions))


def _clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value.strip(), flags=re.I)
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else None


def _openalex_record(item: dict[str, Any], query: str = "") -> SearchResult | None:
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    doi = _clean_doi(item.get("doi"))
    primary = item.get("primary_location") or {}
    source = primary.get("source") or {}
    best_oa = item.get("best_oa_location") or {}
    landing = (primary.get("landing_page_url") or item.get("id") or
               (f"https://doi.org/{doi}" if doi else None))
    if not landing or not str(landing).startswith(("http://", "https://")):
        return None
    authors = [
        str((authorship.get("author") or {}).get("display_name"))
        for authorship in item.get("authorships") or []
        if (authorship.get("author") or {}).get("display_name")
    ]
    abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))
    publication_date = item.get("publication_date") or (str(item.get("publication_year")) if item.get("publication_year") else None)
    # Only a provider-declared PDF is treated as a full-text candidate. An OA
    # landing page may contain metadata/abstract only.
    full_text_url = best_oa.get("pdf_url")
    return SearchResult(
        title=title[:500],
        url=landing,
        content=abstract,
        score=0.0,
        published_date=publication_date,
        authors=authors,
        doi=doi,
        venue=source.get("display_name"),
        source_type="PAPER",
        provider="OpenAlex",
        query=query,
        full_text_url=full_text_url if full_text_url and str(full_text_url).startswith(("http://", "https://")) else None,
    )


def _crossref_record(item: dict[str, Any], query: str = "") -> SearchResult | None:
    titles = item.get("title") or []
    title = str(titles[0] if titles else "").strip()
    doi = _clean_doi(item.get("DOI"))
    if not title or not doi:
        return None
    authors = []
    for author in item.get("author") or []:
        given, family = str(author.get("given") or "").strip(), str(author.get("family") or "").strip()
        name = " ".join(part for part in (given, family) if part)
        if name:
            authors.append(name)
    date_parts = (item.get("published-print") or item.get("published-online") or item.get("published") or {}).get("date-parts") or []
    date = date_parts[0] if date_parts else []
    publication_date = "-".join(f"{int(part):02d}" if i > 0 else str(int(part)) for i, part in enumerate(date)) if date else None
    url = item.get("URL") or f"https://doi.org/{doi}"
    if not str(url).startswith(("http://", "https://")):
        return None
    container = item.get("container-title") or []
    return SearchResult(
        title=title[:500], url=url,
        content=unescape(re.sub(r"<[^>]+>", " ", str(item.get("abstract") or ""))).strip(),
        published_date=publication_date, authors=authors, doi=doi,
        venue=str(container[0]) if container else None,
        source_type="PAPER", provider="Crossref",
        query=query,
    )


class ScholarlySearch:
    """Search OpenAlex and Crossref; failures remain visible to the caller."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def _get_client(self) -> tuple[httpx.AsyncClient, bool]:
        if self._client:
            return self._client, False
        return httpx.AsyncClient(
            timeout=httpx.Timeout(settings.SCHOLARLY_SEARCH_TIMEOUT_SECONDS),
            headers={"User-Agent": "SynthiaResearch/2.2 (scholarly literature discovery)"},
            follow_redirects=True,
        ), True

    async def search_openalex(self, query: str, limit: int = 8) -> tuple[list[SearchResult], dict[str, Any]]:
        client, should_close = await self._get_client()
        started = datetime.now(timezone.utc)
        try:
            params: dict[str, Any] = {
                "search": query,
                "per_page": min(max(limit, 1), 25),
                "select": "id,doi,title,publication_year,publication_date,authorships,primary_location,best_oa_location,abstract_inverted_index",
            }
            if settings.OPENALEX_API_KEY:
                params["api_key"] = settings.OPENALEX_API_KEY
            response = await client.get(OPENALEX_API, params=params)
            response.raise_for_status()
            body = response.json()
            records = [record for item in body.get("results", []) if (record := _openalex_record(item, query))]
            return records, {
                "provider": "OpenAlex", "query": query, "executed_at": started.isoformat(),
                "filters": {"per_page": params["per_page"]},
                "candidate_count": len(body.get("results", [])), "normalized_count": len(records),
                "status": "SUCCESS",
            }
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("OpenAlex search failed (%s)", type(exc).__name__)
            return [], {
                "provider": "OpenAlex", "query": query, "executed_at": started.isoformat(),
                "filters": {"per_page": min(max(limit, 1), 25)},
                "candidate_count": 0, "normalized_count": 0, "status": "FAILED",
                "error": type(exc).__name__,
            }
        finally:
            if should_close:
                await client.aclose()

    async def search_crossref(self, query: str, limit: int = 8) -> tuple[list[SearchResult], dict[str, Any]]:
        client, should_close = await self._get_client()
        started = datetime.now(timezone.utc)
        try:
            params: dict[str, Any] = {"query.bibliographic": query, "rows": min(max(limit, 1), 25)}
            if settings.CROSSREF_MAILTO:
                params["mailto"] = settings.CROSSREF_MAILTO
            response = await client.get(CROSSREF_API, params=params)
            response.raise_for_status()
            body = response.json().get("message", {})
            candidates = body.get("items", [])
            records = [record for item in candidates if (record := _crossref_record(item, query))]
            return records, {
                "provider": "Crossref", "query": query, "executed_at": started.isoformat(),
                "filters": {"rows": params["rows"]}, "candidate_count": len(candidates),
                "normalized_count": len(records), "status": "SUCCESS",
            }
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.warning("Crossref search failed (%s)", type(exc).__name__)
            return [], {
                "provider": "Crossref", "query": query, "executed_at": started.isoformat(),
                "filters": {"rows": min(max(limit, 1), 25)},
                "candidate_count": 0, "normalized_count": 0, "status": "FAILED",
                "error": type(exc).__name__,
            }
        finally:
            if should_close:
                await client.aclose()


def _dedupe_key(record: SearchResult) -> str:
    if record.doi:
        return "doi:" + _clean_doi(record.doi).casefold()
    return _title_key(record.title)


def _title_key(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return "title:" + " ".join(re.sub(r"[^\w\s]", " ", normalized).split())


async def execute_scholarly_searches(
    queries: list[str], max_results_per_query: int = 8,
    budget_context: dict[str, Any] | None = None,
) -> tuple[list[SearchResult], list[dict[str, Any]]]:
    async def guarded(method, query):
        reservation = None
        if budget_context:
            reservation = await reserve_provider_call(
                task_id=budget_context["task_id"], attempt_number=budget_context["attempt_number"],
                kind="search", fixed_cost_usd=settings.SCHOLARLY_REQUEST_COST_USD,
            )
        response = None
        try:
            if budget_context:
                await assert_task_active(budget_context["task_id"], budget_context["attempt_number"])
            response = await method(query, max_results_per_query)
        finally:
            if reservation:
                await settle_provider_call(
                    task_id=budget_context["task_id"], reservation_id=reservation,
                    input_tokens=0, output_tokens=0,
                    cost_usd=(settings.SCHOLARLY_REQUEST_COST_USD if response and response[1].get("status") == "SUCCESS" and method.__name__ == "search_openalex" and settings.OPENALEX_API_KEY else 0),
                    succeeded=bool(response and response[1].get("status") == "SUCCESS"),
                )
        if budget_context:
            await assert_task_active(budget_context["task_id"], budget_context["attempt_number"])
        return response

    timeout = httpx.Timeout(settings.SCHOLARLY_SEARCH_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(
        timeout=timeout,
        headers={"User-Agent": "SynthiaResearch/2.2 (scholarly literature discovery)"},
        follow_redirects=True,
    ) as client:
        service = ScholarlySearch(client)
        calls = [
            guarded(method, query)
            for query in queries
            for method in (service.search_openalex, service.search_crossref)
        ]
        responses = await asyncio.gather(*calls, return_exceptions=True)
    records_by_key: dict[str, SearchResult] = {}
    aliases: dict[str, str] = {}
    activity: list[dict[str, Any]] = []
    for response in responses:
        if isinstance(response, Exception):
            if isinstance(response, (ProviderBudgetExceeded, ResearchTaskStopped)):
                raise response
            logger.warning("Scholarly provider call failed: %s", type(response).__name__)
            continue
        provider_records, event = response
        activity.append(event)
        for record in provider_records:
            lookup_keys = [_dedupe_key(record), _title_key(record.title)]
            if record.doi:
                lookup_keys.append("doi:" + _clean_doi(record.doi).casefold())
            key = next((aliases[alias] for alias in lookup_keys if alias in aliases), lookup_keys[0])
            if key in records_by_key:
                event["duplicate_count"] = event.get("duplicate_count", 0) + 1
                previous = records_by_key[key]
                # Keep OpenAlex's abstract/open-access information while using
                # Crossref to fill publication metadata; never invent fields.
                chosen_provider = "OpenAlex" if "OpenAlex" in {previous.provider, record.provider} else previous.provider
                primary = previous if chosen_provider == previous.provider else record
                secondary = record if primary is previous else previous
                merged = primary.model_copy(update={
                    "authors": primary.authors or secondary.authors,
                    "published_date": primary.published_date or secondary.published_date,
                    "venue": primary.venue or secondary.venue,
                    "doi": primary.doi or secondary.doi,
                    "content": primary.content or secondary.content,
                    "full_text_url": primary.full_text_url or secondary.full_text_url,
                    "provider": primary.provider,
                })
                records_by_key[key] = merged
                for alias in lookup_keys:
                    aliases[alias] = key
                continue
            records_by_key[key] = record
            for alias in lookup_keys:
                aliases[alias] = key
    return list(records_by_key.values()), activity
