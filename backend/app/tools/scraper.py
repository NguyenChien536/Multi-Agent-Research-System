import asyncio
import logging
import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse, urlunsplit, urljoin

import httpx
import trafilatura

logger = logging.getLogger(__name__)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3


class ExtractedText(str):
    """String-compatible extraction result with the verified response format."""
    def __new__(cls, value: str, text_scope: str):
        result = super().__new__(cls, value)
        result.text_scope = text_scope
        return result

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

    @staticmethod
    def _assert_public_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address, label: str) -> None:
        """Raise SSRFError if ip_obj resolves to a non-public address.

        Handles IPv4-mapped IPv6 addresses (::ffff:127.0.0.1 etc.) by unwrapping
        them to their underlying IPv4 form before applying is_global.
        """
        # Unwrap IPv4-mapped / IPv4-compatible IPv6 addresses (e.g. ::ffff:10.0.0.1)
        effective: ipaddress.IPv4Address | ipaddress.IPv6Address = ip_obj
        if isinstance(ip_obj, ipaddress.IPv6Address):
            if ip_obj.ipv4_mapped is not None:
                effective = ip_obj.ipv4_mapped
            elif ip_obj.sixtofour is not None:
                effective = ip_obj.sixtofour

        # Explicitly block the any/unspecified address (0.0.0.0 / ::) regardless of
        # is_global's behaviour across Python minor versions.
        if effective.is_unspecified or effective.is_loopback or effective.is_link_local:
            raise SSRFError(f"Bị chặn truy cập địa chỉ IP không public: {ip_obj} ({label})")

        if not effective.is_global:
            raise SSRFError(f"Bị chặn truy cập địa chỉ IP không public: {ip_obj} ({label})")



    async def _validated_target(self, url: str) -> tuple[str, str, dict[str, str]]:
        """Validate and pin a public destination so the HTTP client cannot re-resolve DNS."""
        parsed = urlparse(url)

        if parsed.scheme not in ["http", "https"]:
            raise SSRFError(f"Schema không được phép: {parsed.scheme}")
        hostname = parsed.hostname
        if not hostname:
            raise SSRFError("URL không có hostname")
        if parsed.username is not None or parsed.password is not None:
            raise SSRFError("URL có thông tin đăng nhập không được phép")
        try:
            port = parsed.port
        except ValueError as exc:
            raise SSRFError("URL có cổng không hợp lệ") from exc

        if hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"]:
            raise SSRFError(f"Bị chặn truy cập localhost: {hostname}")

        try:
            ip_literal = ipaddress.ip_address(hostname)
            self._assert_public_ip(ip_literal, hostname)
            connect_ip = str(ip_literal)
            host_header = f"[{hostname}]" if isinstance(ip_literal, ipaddress.IPv6Address) else hostname
            sni_hostname = None
        except ValueError:
            resolved_ips = await self._resolve_ips(hostname)
            if not resolved_ips:
                raise SSRFError(f"Hostname không phân giải ra địa chỉ IP: {hostname}")
            for ip_str in resolved_ips:
                self._assert_public_ip(ipaddress.ip_address(ip_str), hostname)
            # The request URL uses the checked IP literal, preventing the HTTP
            # client from resolving the original hostname a second time.
            # Prefer IPv4 on hosts without an IPv6 route (common in Docker).
            connect_ip = sorted(resolved_ips, key=lambda ip: (":" in ip, ip))[0]
            host_header = hostname.encode("idna").decode("ascii")
            sni_hostname = host_header if parsed.scheme == "https" else None

        authority = f"[{connect_ip}]" if ":" in connect_ip else connect_ip
        host_authority = host_header
        if port is not None:
            authority = f"{authority}:{port}"
            host_authority = f"{host_authority}:{port}"
        pinned_url = urlunsplit((parsed.scheme, authority, parsed.path or "/", parsed.query, ""))
        extensions = {"sni_hostname": sni_hostname} if sni_hostname else {}
        return pinned_url, host_authority, extensions

    async def _check_ssrf(self, url: str) -> None:
        """Compatibility helper for callers/tests that only need validation."""
        await self._validated_target(url)

    @staticmethod
    def _hostname_for_log(url: str) -> str:
        try:
            return urlparse(url).hostname or "<invalid>"
        except ValueError:
            return "<invalid>"


    async def fetch_and_extract(self, url: str) -> Optional[str]:
        """Tải trang HTML và trích xuất nội dung chính (bỏ quảng cáo, menu)."""
        try:
            # Connect to the exact IP that passed validation. Disable environment
            # proxies because they would resolve/route the original host elsewhere.
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                current_url = url
                seen = set()
                for hop in range(MAX_REDIRECTS + 1):
                    if current_url in seen:
                        raise ValueError("Redirect loop")
                    seen.add(current_url)
                    pinned_url, host_header, extensions = await self._validated_target(current_url)
                    async with client.stream(
                        "GET", pinned_url,
                        headers={**self.headers, "Host": host_header}, extensions=extensions,
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location") or response.headers.get("Location")
                            if not location or hop == MAX_REDIRECTS:
                                raise ValueError("Invalid redirect or redirect limit reached")
                            current_url = urljoin(current_url, location)
                            # Every redirect destination is independently resolved,
                            # checked and IP-pinned before another request is sent.
                            continue
                        response.raise_for_status()
                        content_length = response.headers.get("content-length")
                        if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
                            raise ValueError("Trang web vượt quá giới hạn dung lượng tải xuống")
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                                raise ValueError("Trang web vượt quá giới hạn dung lượng tải xuống")
                            body.extend(chunk)
                        try:
                            html_content = body.decode(response.encoding or "utf-8", errors="replace")
                        except LookupError:
                            html_content = body.decode("utf-8", errors="replace")
                        break

            # Search providers also return public academic PDFs. Never decode
            # their binary bytes as HTML; use the same bounded parser as uploads.
            if bytes(body[:5]) == b"%PDF-":
                from app.services.pdf_parser import extract_text_from_pdf
                parsed_pdf = await asyncio.to_thread(extract_text_from_pdf, bytes(body))
                return ExtractedText(parsed_pdf["text"], "FULL_TEXT")
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
                logger.warning("Không trích xuất được văn bản từ host %s", self._hostname_for_log(url))
                return None

            return ExtractedText(extracted_text, "WEB_PAGE")

        except SSRFError as e:
            logger.error("SSRF alert for host %s: %s", self._hostname_for_log(url), str(e))
            return None
        except ValueError as e:
            logger.warning("Rejected page from host %s: %s", self._hostname_for_log(url), str(e))
            return None
        except httpx.HTTPError as e:
            logger.warning("HTTP error while fetching host %s (%s): %s", self._hostname_for_log(url), type(e).__name__, str(e))
            return None
        except Exception as e:
            logger.error("Unexpected scraper error for host %s (%s): %s", self._hostname_for_log(url), type(e).__name__, str(e))
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
