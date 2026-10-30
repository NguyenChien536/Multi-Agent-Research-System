import asyncio
import logging
from typing import List, Dict, Any, Optional
from tavily import AsyncTavilyClient
from app.tools.search_models import SearchResult

from app.core.config import settings
from app.services.provider_budget import (
    ProviderBudgetExceeded,
    ResearchTaskStopped,
    assert_task_active,
    reserve_provider_call,
    settle_provider_call,
)

logger = logging.getLogger(__name__)

class TavilySearchTool:
    """Công cụ thực hiện tìm kiếm web sử dụng Tavily API (Bất đồng bộ)."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.TAVILY_API_KEY
        if not self.api_key:
            logger.warning("TAVILY_API_KEY không được cung cấp. SearchTool sẽ không hoạt động.")
            self.client = None
        else:
            self.client = AsyncTavilyClient(api_key=self.api_key)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        budget_context: dict[str, Any] | None = None,
        raise_errors: bool = False,
    ) -> List[SearchResult]:
        """Thực hiện tìm kiếm."""
        if not self.client:
            raise ValueError("Tavily client chưa được khởi tạo. Kiểm tra TAVILY_API_KEY.")

        logger.info(f"Đang tìm kiếm: '{query}' (depth={search_depth}, max={max_results})")

        request_cost = settings.TAVILY_REQUEST_COST_USD * (2 if search_depth == "advanced" else 1)
        reservation_id = None
        if budget_context:
            reservation_id = await reserve_provider_call(
                task_id=budget_context["task_id"],
                attempt_number=budget_context["attempt_number"],
                kind="search",
                fixed_cost_usd=request_cost,
            )

        try:
            # Gọi API bất đồng bộ
            if reservation_id:
                await assert_task_active(budget_context["task_id"], budget_context["attempt_number"])
            response = await self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
                include_domains=include_domains or None,
                exclude_domains=None
            )

            if reservation_id:
                await settle_provider_call(
                    task_id=budget_context["task_id"], reservation_id=reservation_id,
                    input_tokens=0, output_tokens=0,
                    cost_usd=request_cost, succeeded=True,
                )
                await assert_task_active(budget_context["task_id"], budget_context["attempt_number"])

            results = []
            for item in response.get("results", []):
                # Ép kiểu dữ liệu an toàn
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date"),
                    source_type="WEBSITE",
                    provider="Tavily academic-domain search" if include_domains else "Tavily",
                    query=query,
                ))

            logger.info(f"Tìm thấy {len(results)} kết quả cho '{query}'")
            return results

        except Exception as e:
            if reservation_id:
                await settle_provider_call(
                    task_id=budget_context["task_id"], reservation_id=reservation_id,
                    input_tokens=0, output_tokens=0, cost_usd=0, succeeded=False,
                )
            logger.error(f"Lỗi khi tìm kiếm Tavily với query '{query}': {str(e)}")
            if isinstance(e, (ProviderBudgetExceeded, ResearchTaskStopped)):
                raise
            if raise_errors:
                raise
            return []

async def execute_parallel_searches(
    queries: List[str], max_results_per_query: int = 3,
    budget_context: dict[str, Any] | None = None,
    *, include_activity: bool = False, search_depth: str | None = None,
) -> List[SearchResult] | tuple[List[SearchResult], list[dict[str, Any]]]:
    """Search scholarly indexes plus the web; optionally return an audit trail."""
    tool = TavilySearchTool()
    depth = search_depth or settings.TAVILY_SEARCH_DEPTH
    if depth not in {"basic", "advanced", "fast", "ultra-fast"}:
        raise ValueError("Unsupported Tavily search depth")
    from app.tools.scholarly_search import execute_scholarly_searches

    activity: list[dict[str, Any]] = []
    calls = []
    for query in queries:
        if tool.client:
            calls.append((query, "Tavily", tool.search(
                query=query,
                max_results=max_results_per_query,
                search_depth=depth,
                budget_context=budget_context,
                raise_errors=True,
            )))
            domains = [item.strip() for item in settings.TAVILY_ACADEMIC_DOMAINS.split(",") if item.strip()]
            if domains:
                calls.append((query, "Tavily academic-domain search", tool.search(
                    query=query,
                    max_results=max_results_per_query,
                    search_depth=depth,
                    include_domains=domains,
                    budget_context=budget_context,
                    raise_errors=True,
                )))
        else:
            activity.append({
                "provider": "Tavily", "query": query, "status": "NOT_CONFIGURED",
                "candidate_count": 0, "fetched_count": 0,
                "filters": {"search_depth": depth},
            })

    tavily_responses = await asyncio.gather(*(call[2] for call in calls), return_exceptions=True)
    final_results: list[SearchResult] = []
    for (query, provider, _call), response in zip(calls, tavily_responses):
        if isinstance(response, Exception):
            if isinstance(response, (ResearchTaskStopped, ProviderBudgetExceeded)):
                raise response
            logger.warning("%s failed for query %r (%s)", provider, query, type(response).__name__)
            activity.append({
                "provider": provider, "query": query, "status": "FAILED",
                "candidate_count": 0, "fetched_count": 0,
                "filters": {"search_depth": depth},
                "error": type(response).__name__,
            })
            continue
        final_results.extend(response)
        activity.append({
            "provider": provider, "query": query, "status": "SUCCESS",
            "candidate_count": len(response), "fetched_count": 0,
            "filters": {
                "search_depth": depth,
                "include_domains": [item.strip() for item in settings.TAVILY_ACADEMIC_DOMAINS.split(",") if item.strip()] if provider.endswith("domain search") else [],
            },
        })

    scholarly_results, scholarly_activity = await execute_scholarly_searches(
        queries, max_results_per_query=max(8, max_results_per_query), budget_context=budget_context,
    )
    final_results = scholarly_results + final_results
    activity.extend(scholarly_activity)

    # Deduplicate using DOI first, then normalized title, then canonical URL.
    from app.tools.scholarly_search import _title_key, _clean_doi
    seen: set[str] = set()
    key_to_result = {}
    duplicate_counts: dict[tuple[str, str | None], int] = {}
    unique: list[SearchResult] = []
    duplicate_count = 0
    for result in final_results:
        keys = {"url:" + str(result.url).rstrip("/").casefold()}
        if result.doi:
            keys.add("doi:" + _clean_doi(result.doi).casefold())
        if result.title.strip():
            keys.add(_title_key(result.title))
        if keys & seen:
            existing = next(key_to_result[k] for k in keys if k in key_to_result)
            existing.matched_queries = list(dict.fromkeys(existing.matched_queries + ([existing.query] if existing.query else []) + result.matched_queries + ([result.query] if result.query else [])))
            duplicate_count += 1
            duplicate_key = (result.provider, result.query)
            duplicate_counts[duplicate_key] = duplicate_counts.get(duplicate_key, 0) + 1
            continue
        seen.update(keys)
        result.matched_queries = list(dict.fromkeys(result.matched_queries + ([result.query] if result.query else [])))
        for key in keys:
            key_to_result[key] = result
        unique.append(result)
    for event in activity:
        event["duplicate_count"] = event.get("duplicate_count", 0) + duplicate_counts.get((event.get("provider", ""), event.get("query")), 0)
    if not activity and duplicate_count:
        activity.append({"provider": "search", "status": "SUCCESS", "duplicate_count": duplicate_count})
    if include_activity:
        from app.services.research_quality import balance_by_query
        return balance_by_query(unique, queries, lambda r: r.matched_queries or [r.query]), activity
    from app.services.research_quality import balance_by_query
    return balance_by_query(unique, queries, lambda r: r.matched_queries or [r.query])
