import asyncio
import logging
from typing import List, Dict, Any, Optional
from tavily import AsyncTavilyClient
from pydantic import BaseModel, HttpUrl, Field

from app.core.config import settings

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

    async def search(self, query: str, max_results: int = 5, search_depth: str = "basic") -> List[SearchResult]:
        """Thực hiện tìm kiếm."""
        if not self.client:
            raise ValueError("Tavily client chưa được khởi tạo. Kiểm tra TAVILY_API_KEY.")

        logger.info(f"Đang tìm kiếm: '{query}' (depth={search_depth}, max={max_results})")

        try:
            # Gọi API bất đồng bộ
            response = await self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
                include_domains=None,
                exclude_domains=None
            )

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
            logger.error(f"Lỗi khi tìm kiếm Tavily với query '{query}': {str(e)}")
            return []

async def execute_parallel_searches(queries: List[str], max_results_per_query: int = 3) -> List[SearchResult]:
    """Thực thi nhiều luồng tìm kiếm song song."""
    tool = TavilySearchTool()

    # Tạo danh sách các task bất đồng bộ
    tasks = [
        tool.search(query=q, max_results=max_results_per_query)
        for q in queries
    ]

    # Chạy tất cả cùng lúc bằng asyncio.gather
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    # Gộp và loại bỏ trùng lặp (deduplication) dựa trên URL
    seen_urls = set()
    final_results = []

    for res_list in results_lists:
        if isinstance(res_list, Exception):
            logger.error(f"Một task search song song bị lỗi: {res_list}")
            continue

        for result in res_list:
            url_str = str(result.url)
            if url_str not in seen_urls:
                seen_urls.add(url_str)
                final_results.append(result)

    return final_results
