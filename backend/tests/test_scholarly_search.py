import httpx
import pytest
from unittest.mock import AsyncMock

from app.services.manuscript import manuscript_provenance
from app.tools.search_models import SearchResult
from app.tools.scholarly_search import (
    ScholarlySearch,
    _crossref_record,
    _openalex_record,
    execute_scholarly_searches,
)


def test_deposit_date_is_not_reported_as_publication_date():
    record = _crossref_record({"DOI": "10.1234/x", "title": ["Undated paper"],
                              "created": {"date-parts": [[2024, 1, 1]]}})
    assert record.published_date is None


def test_reference_preserves_full_doi_and_venue():
    from app.services.references import format_reference
    _, text = format_reference({"source_title": "Paper", "doi": "10.1234/long/path",
                                "venue": "A Journal"}, 1, "IEEE")
    assert "https://doi.org/10.1234/long/path" in text and "A Journal" in text


@pytest.mark.asyncio
async def test_web_duplicate_does_not_displace_scholarly_metadata(monkeypatch):
    from app.tools import search, scholarly_search
    from app.core.config import settings
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "fixture-key")
    monkeypatch.setattr(settings, "TAVILY_ACADEMIC_DOMAINS", "")
    monkeypatch.setattr(search.TavilySearchTool, "search", AsyncMock(return_value=[
        SearchResult(title="Same Paper", url="https://example.org/web", provider="Tavily", query="q")]))
    monkeypatch.setattr(scholarly_search, "execute_scholarly_searches", AsyncMock(return_value=([
        SearchResult(title="Same Paper", url="https://example.org/paper", doi="10.1234/x", provider="OpenAlex", query="q")],
        [{"provider": "OpenAlex", "query": "q", "status": "SUCCESS", "candidate_count": 1}])))
    results, activity = await search.execute_parallel_searches(["q"], include_activity=True)
    assert len(results) == 1 and results[0].doi == "10.1234/x"
    assert next(e for e in activity if e["provider"] == "Tavily")["duplicate_count"] == 1


@pytest.mark.asyncio
async def test_failed_pdf_fetch_uses_explicit_abstract_scope_and_metadata(monkeypatch):
    from app.agents import nodes
    from app.tools import search, scraper
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    source = SearchResult(title="A Paper", url="https://example.org/paper", full_text_url="https://example.org/paper.pdf",
                          content="An abstract with only the documented high-level findings. " * 3,
                          source_type="PAPER", provider="OpenAlex", query="q", doi="10.1234/x", authors=["A. Author"])
    monkeypatch.setattr(search, "execute_parallel_searches", AsyncMock(return_value=([source], [
        {"provider": "OpenAlex", "query": "q", "status": "SUCCESS", "candidate_count": 1}])))
    monkeypatch.setattr(scraper, "fetch_urls_parallel", AsyncMock(return_value={}))
    result = await nodes.researcher_node({"delta_queries": ["q"], "max_sources": 10})
    assert result["collected_sources"][0]["text_scope"] == "ABSTRACT"
    assert result["collected_sources"][0]["doi"] == "10.1234/x"
    assert result["collected_sources"][0]["author"] == "A. Author"
    assert result["search_activity"][0]["fetch_failed_count"] == 1
    assert result["search_activity"][0]["abstract_only_count"] == 1
    assert "doi:10.1234/x" in result["visited_urls"]


def test_openalex_normalizes_bibliographic_fields_and_does_not_treat_landing_page_as_full_text():
    record = _openalex_record({
        "id": "https://openalex.org/W123",
        "doi": "https://doi.org/10.1234/example",
        "title": "A Research Paper",
        "publication_year": 2024,
        "authorships": [{"author": {"display_name": "A. Author"}}],
        "primary_location": {
            "landing_page_url": "https://publisher.example/paper",
            "source": {"display_name": "Journal of Tests"},
        },
        "best_oa_location": {"landing_page_url": "https://repository.example/item"},
        "abstract_inverted_index": {"evidence": [0], "supports": [1], "claim": [2]},
    }, "evidence support")

    assert record is not None
    assert record.doi == "10.1234/example"
    assert record.venue == "Journal of Tests"
    assert record.authors == ["A. Author"]
    assert record.content == "evidence supports claim"
    assert record.full_text_url is None
    assert record.provider == "OpenAlex"
    assert record.query == "evidence support"


def test_crossref_normalizes_doi_authors_date_and_venue():
    record = _crossref_record({
        "DOI": "10.5555/test",
        "title": ["A Citation Record"],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "published-print": {"date-parts": [[2023, 4, 2]]},
        "container-title": ["Proceedings"],
        "URL": "https://api.crossref.org/works/10.5555/test",
    })
    assert record is not None
    assert record.doi == "10.5555/test"
    assert record.authors == ["Ada Lovelace"]
    assert record.published_date == "2023-04-02"
    assert record.venue == "Proceedings"


@pytest.mark.asyncio
async def test_provider_queries_are_audited_and_crossref_enriches_openalex(monkeypatch):
    openalex = SearchResult(
        title="Same Paper", url="https://openalex.org/W1", content="abstract",
        provider="OpenAlex", source_type="PAPER", doi="10.1234/shared",
        query="fair matching", authors=["A. Author"],
    )
    crossref = SearchResult(
        title="Same Paper", url="https://doi.org/10.1234/shared", content="",
        provider="Crossref", source_type="PAPER", doi="10.1234/shared",
        query="fair matching", venue="Matching Journal", published_date="2024",
    )

    async def fake_openalex(self, query, limit):
        return [openalex], {"provider": "OpenAlex", "query": query, "candidate_count": 1, "status": "SUCCESS"}

    async def fake_crossref(self, query, limit):
        return [crossref], {"provider": "Crossref", "query": query, "candidate_count": 1, "status": "SUCCESS"}

    monkeypatch.setattr(ScholarlySearch, "search_openalex", fake_openalex)
    monkeypatch.setattr(ScholarlySearch, "search_crossref", fake_crossref)
    records, activity = await execute_scholarly_searches(["fair matching"], 5)

    assert len(records) == 1
    assert records[0].provider == "OpenAlex"
    assert records[0].venue == "Matching Journal"
    assert records[0].authors == ["A. Author"]
    assert {event["provider"] for event in activity} == {"OpenAlex", "Crossref"}
    assert all(event["query"] == "fair matching" for event in activity)


def test_provenance_names_only_successful_scholarly_indexes_and_keeps_tavily_distinct():
    result = manuscript_provenance({
        "search_activity": [
            {"provider": "Tavily academic-domain search", "query": "matching", "status": "SUCCESS", "candidate_count": 3},
            {"provider": "OpenAlex", "query": "matching", "status": "SUCCESS", "candidate_count": 4,
             "fetched_count": 2, "accepted_count": 2},
            {"provider": "Crossref", "query": "matching", "status": "FAILED", "candidate_count": 0},
        ],
        "collected_sources": [], "claims": [],
    })
    assert result["direct_scholarly_index_queries"] == ["OpenAlex"]
    assert result["direct_scholarly_index_query_executed"] is True
    assert result["direct_academic_database_search"] is False
    assert result["search_provider_summary"]["OpenAlex"]["accepted"] == 2
    assert result["search_provider_summary"]["Crossref"]["failed_queries"] == 1


@pytest.mark.asyncio
async def test_openalex_provider_failure_is_recorded_not_fabricated():
    async def handler(request):
        return httpx.Response(429, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records, event = await ScholarlySearch(client).search_openalex("rate limit", 5)

    assert records == []
    assert event["provider"] == "OpenAlex"
    assert event["status"] == "FAILED"
    assert event["candidate_count"] == 0
    assert event["error"] == "HTTPStatusError"
