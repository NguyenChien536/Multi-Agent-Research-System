"""Bounded validation of user-supplied evidence, not scientific verification."""

import csv
import hashlib
import io
from pathlib import Path

MAX_RESULT_BYTES = 5 * 1024 * 1024
MAX_RESULT_ROWS = 20_000
MAX_RESULT_COLUMNS = 30
RESULT_TYPES = {".csv": "USER_DATA_CSV", ".txt": "USER_DATA_TEXT"}


def validate_fieldwork_result(filename: str, content: bytes) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in RESULT_TYPES:
        raise ValueError("Kết quả thực địa phải là CSV hoặc TXT UTF-8.")
    if not content or len(content) > MAX_RESULT_BYTES:
        raise ValueError("Tệp kết quả phải có dữ liệu và không vượt quá 5 MiB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Tệp kết quả phải dùng mã hóa UTF-8.") from exc
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        raise ValueError("Tệp chứa ký tự điều khiển hoặc dữ liệu nhị phân.")
    if not text.strip():
        raise ValueError("Tệp kết quả trống.")

    row_count = None
    if suffix == ".csv":
        try:
            reader = csv.reader(io.StringIO(text), strict=True)
            headers = next(reader)
            normalized = [header.strip().casefold() for header in headers]
            if (not normalized or len(headers) > MAX_RESULT_COLUMNS
                    or not all(normalized) or len(set(normalized)) != len(headers)):
                raise ValueError("CSV cần 1–30 cột, tên cột không trống và không trùng.")
            row_count = 0
            for row in reader:
                if not row or not any(cell.strip() for cell in row):
                    continue
                if len(row) != len(headers):
                    raise ValueError("Số cột trong các dòng CSV không khớp tiêu đề.")
                row_count += 1
                if row_count > MAX_RESULT_ROWS:
                    raise ValueError("CSV vượt quá 20.000 dòng dữ liệu.")
            if not row_count:
                raise ValueError("CSV chưa có dòng dữ liệu.")
        except (csv.Error, StopIteration) as exc:
            raise ValueError("Không thể đọc cấu trúc CSV.") from exc

    return {
        "export_type": RESULT_TYPES[suffix],
        "sha256_hash": hashlib.sha256(content).hexdigest(),
        "file_size_bytes": len(content),
        "rows_count": row_count,
        "text_excerpt": text[:12_000],
        "excerpt_truncated": len(text) > 12_000,
        "verification_status": "USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED",
    }
