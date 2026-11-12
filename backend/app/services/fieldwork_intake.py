"""Bounded validation of user-supplied evidence, not scientific verification."""

import csv
import hashlib
import io
import math
import statistics
from collections import Counter
from pathlib import Path

MAX_RESULT_BYTES = 5 * 1024 * 1024
MAX_RESULT_ROWS = 20_000
MAX_RESULT_COLUMNS = 30
RESULT_TYPES = {".csv": "USER_DATA_CSV", ".txt": "USER_DATA_TEXT"}


def frozen_csv_statistics(evidence: dict | None) -> dict | None:
    """Recheck arithmetic from a complete, hash-matching frozen CSV excerpt.

    Historical reports lack the new statistics field. Never read a later task's
    mutable upload or infer counts from a truncated excerpt to fill that gap.
    """
    evidence = evidence or {}
    if evidence.get('csv_descriptive_statistics'):
        return evidence['csv_descriptive_statistics']
    text = evidence.get('text_excerpt')
    if evidence.get('export_type') != 'USER_DATA_CSV' or evidence.get('excerpt_truncated') or not isinstance(text, str):
        return None
    raw = text.encode('utf-8')
    if hashlib.sha256(raw).hexdigest() != evidence.get('sha256_hash') or len(raw) != evidence.get('file_size_bytes'):
        return None
    try:
        return validate_fieldwork_result('snapshot.csv', raw)['csv_descriptive_statistics']
    except ValueError:
        return None


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
    descriptive = None
    if suffix == ".csv":
        try:
            reader = csv.reader(io.StringIO(text), strict=True)
            headers = next(reader)
            normalized = [header.strip().casefold() for header in headers]
            if (not normalized or len(headers) > MAX_RESULT_COLUMNS
                    or not all(normalized) or len(set(normalized)) != len(headers)):
                raise ValueError("CSV cần 1–30 cột, tên cột không trống và không trùng.")
            row_count = 0
            cells = [[] for _ in headers]
            for row in reader:
                if not row or not any(cell.strip() for cell in row):
                    continue
                if len(row) != len(headers):
                    raise ValueError("Số cột trong các dòng CSV không khớp tiêu đề.")
                row_count += 1
                if row_count > MAX_RESULT_ROWS:
                    raise ValueError("CSV vượt quá 20.000 dòng dữ liệu.")
                for index, cell in enumerate(row):
                    cells[index].append(cell.strip())
            if not row_count:
                raise ValueError("CSV chưa có dòng dữ liệu.")
            columns = {}
            for header, column in zip(headers, cells):
                populated = [value for value in column if value]
                if not populated:
                    continue
                try:
                    values = [float(value) for value in populated]
                    if not all(math.isfinite(value) for value in values):
                        continue
                    mean = statistics.mean(values)
                    sample_sd = statistics.stdev(values) if len(values) > 1 else None
                    population_sd = statistics.pstdev(values)
                    if not all(math.isfinite(value) for value in (mean, population_sd, sample_sd or 0)):
                        continue
                except (ValueError, OverflowError):
                    continue  # Text/mixed/non-finite columns are not silently coerced.
                counts = Counter(values)
                columns[header] = {
                    'count': len(values), 'missing_count': row_count - len(values),
                    'minimum': min(values), 'maximum': max(values), 'mean': mean,
                    'sample_sd': sample_sd, 'sample_sd_ddof': 1, 'population_sd': population_sd,
                    'value_counts': {str(value): counts[value] for value in sorted(counts)} if len(counts) <= 20 else None,
                    'frequencies_omitted': len(counts) > 20,
                }
            descriptive = {'version': 1, 'rows_count': row_count, 'columns': columns,
                           'scope': 'Arithmetic over uploaded CSV cells only; not verification of fieldwork, construct validity, sampling or causality.'}
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
        "csv_descriptive_statistics": descriptive,
    }
