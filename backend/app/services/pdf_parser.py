import io
import logging
from typing import Dict, Any, Optional
from pypdf import PdfReader

from app.core.config import settings

logger = logging.getLogger(__name__)


class PdfValidationError(Exception):
    """Lỗi kiểm tra tính hợp lệ của tài liệu PDF."""
    pass


class PdfSizeLimitError(PdfValidationError):
    """Lỗi dung lượng vượt quá giới hạn cho phép."""
    pass


class PdfPageLimitError(PdfValidationError):
    """Lỗi số trang vượt quá giới hạn cho phép."""
    pass


class PdfOcrRequiredError(PdfValidationError):
    """Lỗi tài liệu là file scan / hình ảnh không có văn bản có thể trích xuất."""
    pass


def validate_pdf_bytes(content: bytes) -> None:
    """Kiểm tra chữ ký số học (magic bytes) và dung lượng tệp PDF."""
    # 1. Kiểm tra kích thước
    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise PdfSizeLimitError(f"Dung lượng file vượt quá giới hạn cho phép (tối đa {max_mb} MiB).")

    # 2. Kiểm tra chữ ký %PDF- trong 1024 bytes đầu tiên
    header = content[:1024]
    if b"%PDF-" not in header:
        raise PdfValidationError("Định dạng file không hợp lệ. Chỉ chấp nhận tài liệu PDF chuẩn.")


def extract_text_from_pdf(content: bytes) -> Dict[str, Any]:
    """
    Trích xuất văn bản từ tệp PDF bằng pypdf.
    Tuân thủ các giới hạn:
    - Kích thước <= 10 MiB
    - Số trang <= 100 trang
    - Không hỗ trợ OCR: nếu không trích xuất được text, báo lỗi rõ ràng hướng dẫn người dùng.
    """
    validate_pdf_bytes(content)

    try:
        reader = PdfReader(io.BytesIO(content))
    except Exception as exc:
        logger.warning("Lỗi phân tích cú pháp PDF: %s", exc)
        raise PdfValidationError(f"Không thể đọc file PDF. File có thể bị hỏng hoặc có mật khẩu bảo vệ: {exc}")

    # 1. Kiểm tra số trang
    page_count = len(reader.pages)
    if page_count == 0:
        raise PdfValidationError("Tài liệu PDF không có trang nào.")

    if page_count > settings.MAX_PDF_PAGES:
        raise PdfPageLimitError(
            f"Tài liệu PDF vượt quá giới hạn số trang cho phép (tối đa {settings.MAX_PDF_PAGES} trang, tệp có {page_count} trang)."
        )

    # 2. Trích xuất text từng trang
    extracted_pages = []
    total_chars = 0

    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            page_text = page_text.strip()
            if page_text:
                extracted_pages.append(f"--- [Trang {idx + 1}] ---\n{page_text}")
                total_chars += len(page_text)
        except Exception as page_exc:
            logger.warning("Lỗi trích xuất trang %d: %s", idx + 1, page_exc)

    full_text = "\n\n".join(extracted_pages).strip()

    # 3. Kiểm tra nếu file scan / không có selectable text
    if not full_text or total_chars < 30:
        raise PdfOcrRequiredError(
            "Tài liệu PDF không có nội dung văn bản (có thể là file scan hoặc hình ảnh thuần túy). "
            "Hệ thống hiện tại không hỗ trợ OCR, vui lòng tải lên tài liệu PDF dạng văn bản có thể chọn được (selectable text)."
        )

    # 4. Trích xuất metadata tiêu đề nếu có
    title: Optional[str] = None
    author: Optional[str] = None
    if reader.metadata:
        title = reader.metadata.title
        author = reader.metadata.author

    return {
        "text": full_text,
        "page_count": page_count,
        "char_count": total_chars,
        "title": title,
        "author": author,
    }
