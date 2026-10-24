import asyncio
import logging
from typing import List, Dict, Any, Optional
from tavily import AsyncTavilyClient
from pydantic import BaseModel, HttpUrl, Field

from app.core.config import settings
from app.services.provider_budget import (
    ProviderBudgetExceeded,
    ResearchTaskStopped,
    assert_task_active,
    reserve_provider_call,
    settle_provider_call,
)

logger = logging.getLogger(__name__)

class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    content: str
    score: float = Field(default=0.0)
    published_date: Optional[str] = None

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
        budget_context: dict[str, Any] | None = None,
    ) -> List[SearchResult]:
        """Thực hiện tìm kiếm."""
        if not self.client:
            raise ValueError("Tavily client chưa được khởi tạo. Kiểm tra TAVILY_API_KEY.")

        logger.info(f"Đang tìm kiếm: '{query}' (depth={search_depth}, max={max_results})")

        reservation_id = None
        if budget_context:
            reservation_id = await reserve_provider_call(
                task_id=budget_context["task_id"],
                attempt_number=budget_context["attempt_number"],
                kind="search",
                fixed_cost_usd=settings.TAVILY_REQUEST_COST_USD,
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
                include_domains=None,
                exclude_domains=None
            )

            if reservation_id:
                await settle_provider_call(
                    task_id=budget_context["task_id"], reservation_id=reservation_id,
                    input_tokens=0, output_tokens=0,
                    cost_usd=settings.TAVILY_REQUEST_COST_USD, succeeded=True,
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
                    published_date=item.get("published_date")
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
            return []

async def execute_parallel_searches(
    queries: List[str], max_results_per_query: int = 3,
    budget_context: dict[str, Any] | None = None,
) -> List[SearchResult]:
    """Thực thi nhiều luồng tìm kiếm song song."""
    tool = TavilySearchTool()

    # Tạo danh sách các task bất đồng bộ
    tasks = [
        tool.search(query=q, max_results=max_results_per_query, budget_context=budget_context)
        for q in queries
    ]

    # Chạy tất cả cùng lúc bằng asyncio.gather
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    # Gộp và loại bỏ trùng lặp (deduplication) dựa trên URL
    seen_urls = set()
    final_results = []

    for res_list in results_lists:
        if isinstance(res_list, Exception):
            if isinstance(res_list, (ResearchTaskStopped, ProviderBudgetExceeded)):
                raise res_list
            logger.error(f"Một task search song song bị lỗi: {res_list}")
            continue

        for result in res_list:
            url_str = str(result.url)
            if url_str not in seen_urls:
                seen_urls.add(url_str)
                final_results.append(result)

    return final_results
