import asyncio
import logging
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional

import httpx
import trafilatura

logger = logging.getLogger(__name__)

class SSRFError(Exception):
    """Lỗi khi phát hiện URL có dấu hiệu SSRF."""
    pass

class ScraperTool:
    """Công cụ cào nội dung web an toàn (Async + SSRF Guard)."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Multi-Agent Research System/2.2.0 (Academic Research Bot)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def _resolve_ips(self, hostname: str) -> set[str]:
        """Phân giải mọi địa chỉ IP của hostname để kiểm tra an toàn."""
        loop = asyncio.get_running_loop()
        try:
            addr_info = await loop.getaddrinfo(
                hostname,
                None,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
            return {item[4][0] for item in addr_info}
        except socket.gaierror:
            raise SSRFError(f"Không thể phân giải hostname: {hostname}")

    async def _check_ssrf(self, url: str) -> None:
        """Kiểm tra URL để ngăn chặn SSRF."""
        parsed = urlparse(url)

        # 1. Chặn schema nguy hiểm
        if parsed.scheme not in ["http", "https"]:
            raise SSRFError(f"Schema không được phép: {parsed.scheme}")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFError("URL không có hostname")

        # 2. Chặn localhost bằng text
        if hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0"]:
            raise SSRFError(f"Bị chặn truy cập localhost: {hostname}")

        # 3. Phân giải DNS và chặn IP private/reserved
        resolved_ips = await self._resolve_ips(hostname)
        for ip_str in resolved_ips:
            ip_obj = ipaddress.ip_address(ip_str)
            if not ip_obj.is_global:
                raise SSRFError(f"Bị chặn truy cập địa chỉ IP không public: {ip_str} ({hostname})")

    async def fetch_and_extract(self, url: str) -> Optional[str]:
        """Tải trang HTML và trích xuất nội dung chính (bỏ quảng cáo, menu)."""
        try:
            # Bước 1: Kiểm tra bảo mật
            await self._check_ssrf(url)

            # Bước 2: Tải HTML bằng httpx (Bất đồng bộ)
            # Không tự follow redirect để tránh URL public chuyển hướng sang địa chỉ nội bộ.
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                html_content = response.text

            # Bước 3: Trích xuất nội dung bằng trafilatura (Đồng bộ, nhưng chạy rất nhanh)
            # Nếu HTML quá lớn, có thể cân nhắc run_in_executor
            extracted_text = trafilatura.extract(
                html_content,
                include_links=False,
                include_images=False,
                include_tables=True,
                no_fallback=False
            )

            if not extracted_text:
                logger.warning(f"Không trích xuất được văn bản từ: {url}")
                return None

            return extracted_text

        except SSRFError as e:
            logger.error(f"SSRF Alert - URL {url}: {str(e)}")
            return None
        except httpx.HTTPError as e:
            logger.warning(f"Lỗi HTTP khi tải {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Lỗi không xác định khi cào {url}: {str(e)}")
            return None

async def fetch_urls_parallel(urls: list[str], max_concurrent: int = 5) -> dict[str, str]:
    """Cào nhiều URL cùng lúc có giới hạn số luồng (Semaphore)."""
    scraper = ScraperTool()
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def fetch_with_sema(url: str):
        async with semaphore:
            content = await scraper.fetch_and_extract(url)
            if content:
                results[url] = content

    tasks = [fetch_with_sema(url) for url in urls]
    await asyncio.gather(*tasks)

    return results
