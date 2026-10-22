import csv
import hashlib
import io
import math
import random
from typing import Any, Dict, List, Optional, Tuple

MAX_DATASET_ROWS = 10_000
MAX_DATASET_COLUMNS = 51  # target + at most 50 features


class ExperimentError(Exception):
    """Base exception for experiment routine errors."""
    pass


class InvalidInputError(ExperimentError):
    """Raised when CSV format, target, or feature columns are invalid."""
    pass


class TargetLeakageError(ExperimentError):
    """Raised when target column is present in feature list or invalid leakage is detected."""
    pass


def parse_csv_dataset(csv_text: str) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse CSV text into column headers and rows with type inference."""
    if not csv_text or not csv_text.strip():
        raise InvalidInputError("CSV dataset is empty")

    # UTF-8 CSV exports from spreadsheet tools commonly include a BOM.
    f = io.StringIO(csv_text.lstrip("\ufeff").strip(), newline="")
    reader = csv.reader(f)
    try:
        header = next(reader)
    except StopIteration:
        raise InvalidInputError("CSV dataset has no rows")

    header = [col.strip() for col in header]
    if not header or any(len(c) == 0 for c in header):
        raise InvalidInputError("CSV header is invalid or has empty column names")
    normalized_headers = [column.casefold() for column in header]
    if len(set(normalized_headers)) != len(normalized_headers):
        raise InvalidInputError("CSV header contains duplicate column names")
    if len(header) > MAX_DATASET_COLUMNS:
        raise InvalidInputError(
            f"Dataset has {len(header)} columns; maximum supported is {MAX_DATASET_COLUMNS} "
            "(one target and up to 50 features)"
        )

    rows: List[Dict[str, Any]] = []
    for row_idx, raw_row in enumerate(reader, start=1):
        if not raw_row or all(len(c.strip()) == 0 for c in raw_row):
            continue
        if len(raw_row) != len(header):
            raise InvalidInputError(
                f"Row {row_idx} column count ({len(raw_row)}) does not match header ({len(header)})"
            )
        row_dict: Dict[str, Any] = {}
        for col_name, val in zip(header, raw_row):
            v_str = val.strip()
            if v_str == "" or v_str.lower() in ("nan", "null", "none"):
                row_dict[col_name] = None
            else:
                try:
                    numeric_value = float(v_str)
                except ValueError:
                    row_dict[col_name] = v_str
                else:
                    if not math.isfinite(numeric_value):
                        raise InvalidInputError(
                            f"Row {row_idx} column '{col_name}' contains a non-finite numeric value"
                        )
                    row_dict[col_name] = numeric_value
        rows.append(row_dict)
        if len(rows) > MAX_DATASET_ROWS:
            raise InvalidInputError(f"Dataset exceeds the maximum of {MAX_DATASET_ROWS} rows")

    if len(rows) < 10:
        raise InvalidInputError(f"Dataset has only {len(rows)} rows; minimum 10 rows required for 80/20 train/test evaluation")

    return header, rows


def cholesky_solve(A: List[List[float]], b: List[float]) -> List[float]:
    """Solve A w = b for symmetric positive definite matrix A using Cholesky decomposition."""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                val = A[i][i] - s
                if val <= 0:
                    val = 1e-12
                L[i][j] = math.sqrt(val)
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]

    # Forward substitution: L z = b
    z = [0.0] * n
    for i in range(n):
        s = sum(L[i][k] * z[k] for k in range(i))
        z[i] = (b[i] - s) / L[i][i]

    # Backward substitution: L^T x = z
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = sum(L[k][i] * x[k] for k in range(i + 1, n))
        x[i] = (z[i] - s) / L[i][i]

    return x


def run_tabular_regression_v1(
    csv_text: str,
    target_column: Optional[str] = None,
    feature_columns: Optional[List[str]] = None,
    alpha: float = 1.0,
    test_size: float = 0.2,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Execute tabular_regression_v1 routine according to Phase 5 specification:
    - Profiles numeric CSV
    - Train-only fit preprocessing (mean, standard deviation)
    - Mean baseline vs Ridge(alpha=1.0)
    - Deterministic 80/20 train/test split with fixed seed
    - Produces manifest, metrics, chart data, and reproducibility documentation.
    """
    input_checksum = hashlib.sha256(csv_text.strip().encode("utf-8")).hexdigest()
    headers, rows = parse_csv_dataset(csv_text)

    try:
        alpha = float(alpha)
        test_size = float(test_size)
    except (TypeError, ValueError) as exc:
        raise InvalidInputError("alpha and test_size must be numeric") from exc
    if not math.isfinite(alpha) or alpha <= 0:
        raise InvalidInputError("alpha must be a finite number greater than zero")
    if not math.isfinite(test_size) or not 0.0 < test_size < 1.0:
        raise InvalidInputError("test_size must be a finite value strictly between 0 and 1")
    if type(seed) is not int:
        raise InvalidInputError("seed must be an integer")

    # 1. Determine numeric columns
    numeric_cols = []
    for col in headers:
        values = [r[col] for r in rows if r[col] is not None]
        if values and all(isinstance(v, (int, float)) for v in values):
            numeric_cols.append(col)

    if len(numeric_cols) < 2:
        raise InvalidInputError("Dataset must have at least 2 numeric columns (1 target + 1 or more features)")

    # 2. Select target column
    if target_column:
        if target_column not in headers:
            raise InvalidInputError(f"Specified target column '{target_column}' not found in CSV headers")
        if target_column not in numeric_cols:
            raise InvalidInputError(f"Specified target column '{target_column}' is not numeric")
        target_col = target_column
    else:
        target_col = numeric_cols[-1]

    # 3. Select feature columns & guard against target leakage
    if feature_columns is not None:
        if len({column.casefold() for column in feature_columns}) != len(feature_columns):
            raise InvalidInputError("Feature columns must not contain duplicates")
        for f in feature_columns:
            if f not in headers:
                raise InvalidInputError(f"Specified feature column '{f}' not found in CSV headers")
            if f not in numeric_cols:
                raise InvalidInputError(f"Specified feature column '{f}' is not numeric")
            if f == target_col:
                raise TargetLeakageError(f"Target column '{target_col}' cannot be included in feature columns")
        feat_cols = list(feature_columns)
    else:
        feat_cols = [c for c in numeric_cols if c != target_col]

    if not feat_cols:
        raise InvalidInputError("No valid feature columns available after excluding target")

    # 4. Filter complete numeric cases for target and features
    clean_data = []
    for r in rows:
        t_val = r[target_col]
        if t_val is None or not math.isfinite(t_val):
            continue
        f_vals = [r[c] for c in feat_cols]
        if any(v is None or not math.isfinite(v) for v in f_vals):
            continue
        clean_data.append((f_vals, t_val))

    if len(clean_data) < 10:
        raise InvalidInputError(
            f"After dropping missing/non-finite values, only {len(clean_data)} valid rows remain (minimum 10 required)"
        )

    # 5. Deterministic train/test split (seed=42, 80/20)
    indices = list(range(len(clean_data)))
    rng = random.Random(seed)
    rng.shuffle(indices)

    train_count = int(len(clean_data) * (1.0 - test_size))
    if train_count < 2 or len(clean_data) - train_count < 2:
        raise InvalidInputError("Train and test partitions must each contain at least 2 valid rows")
    train_indices = indices[:train_count]
    test_indices = indices[train_count:]

    X_train = [clean_data[i][0] for i in train_indices]
    y_train = [clean_data[i][1] for i in train_indices]
    X_test = [clean_data[i][0] for i in test_indices]
    y_test = [clean_data[i][1] for i in test_indices]

    n_train = len(X_train)
    n_test = len(X_test)
    p = len(feat_cols)

    # 6. Preprocessing: Fit statistics TRAIN-ONLY (no data leakage!)
    means = [sum(X_train[i][j] for i in range(n_train)) / n_train for j in range(p)]
    stds = []
    for j in range(p):
        var = sum((X_train[i][j] - means[j]) ** 2 for i in range(n_train)) / n_train
        std = math.sqrt(var)
        stds.append(std if std > 1e-12 else 1.0)

    y_train_mean = sum(y_train) / n_train

    # Transform train
    X_train_std = [[(X_train[i][j] - means[j]) / stds[j] for j in range(p)] for i in range(n_train)]
    y_train_centered = [y_train[i] - y_train_mean for i in range(n_train)]

    # Transform test using TRAIN parameters
    X_test_std = [[(X_test[i][j] - means[j]) / stds[j] for j in range(p)] for i in range(n_test)]

    # 7. Ridge Regression Model: Solve (X_train_std^T X_train_std + alpha * I) w = X_train_std^T y_train_centered
    XtX = [[0.0] * p for _ in range(p)]
    for j1 in range(p):
        for j2 in range(p):
            XtX[j1][j2] = sum(X_train_std[i][j1] * X_train_std[i][j2] for i in range(n_train))
        XtX[j1][j1] += alpha

    Xty = [sum(X_train_std[i][j] * y_train_centered[i] for i in range(n_train)) for j in range(p)]
    weights = cholesky_solve(XtX, Xty)

    # 8. Predictions
    # Ridge predictions: y_pred = y_train_mean + X_test_std * w
    y_pred_ridge = [y_train_mean + sum(X_test_std[i][j] * weights[j] for j in range(p)) for i in range(n_test)]
    # Mean baseline predictions: constant y_train_mean
    y_pred_baseline = [y_train_mean for _ in range(n_test)]

    # 9. Compute Metrics
    # Baseline
    base_mae = sum(abs(y_test[i] - y_pred_baseline[i]) for i in range(n_test)) / n_test
    base_rmse = math.sqrt(sum((y_test[i] - y_pred_baseline[i]) ** 2 for i in range(n_test)) / n_test)

    # Ridge
    ridge_mae = sum(abs(y_test[i] - y_pred_ridge[i]) for i in range(n_test)) / n_test
    ridge_rmse = math.sqrt(sum((y_test[i] - y_pred_ridge[i]) ** 2 for i in range(n_test)) / n_test)

    y_test_mean = sum(y_test) / n_test
    ss_tot = sum((y_test[i] - y_test_mean) ** 2 for i in range(n_test))
    base_ss_res = sum((y_test[i] - y_pred_baseline[i]) ** 2 for i in range(n_test))
    ss_res = sum((y_test[i] - y_pred_ridge[i]) ** 2 for i in range(n_test))
    # Match the common finite R² convention for a constant held-out target:
    # return 0.0 because R² is undefined when total variance is zero.
    base_r2 = 1.0 - (base_ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    ridge_r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

    delta_mae = ridge_mae - base_mae
    delta_rmse = ridge_rmse - base_rmse

    # 10. Observation verdict
    # Strictly adheres to scientific integrity: if ridge does not beat baseline, it is NO_IMPROVEMENT
    verdict = "IMPROVEMENT" if ridge_mae < base_mae else "NO_IMPROVEMENT"

    manifest = {
        "manifest_version": "1.0",
        "routine_name": "tabular_regression_v1",
        "routine_version": "1.0.0",
        "input_checksum": input_checksum,
        "dataset_rows": len(rows),
        "valid_rows": len(clean_data),
        "train_rows": n_train,
        "test_rows": n_test,
        "target_column": target_col,
        "feature_columns": feat_cols,
        "parameters": {
            "alpha": alpha,
            "test_size": test_size,
            "seed": seed,
            "fit_intercept": True,
            "standardize": True,
        },
    }

    metrics = {
        "baseline": {
            "model_type": "MeanBaseline",
            "mae": round(base_mae, 6),
            "rmse": round(base_rmse, 6),
            "r2": round(base_r2, 6),
        },
        "model": {
            "model_type": "RidgeRegression",
            "alpha": alpha,
            "mae": round(ridge_mae, 6),
            "rmse": round(ridge_rmse, 6),
            "r2": round(ridge_r2, 6),
        },
        "comparison": {
            "primary_metric": "MAE",
            "delta_mae": round(delta_mae, 6),
            "delta_rmse": round(delta_rmse, 6),
            "verdict": verdict,
            "pct_improvement": round(((base_mae - ridge_mae) / base_mae) * 100, 2) if base_mae > 1e-12 else 0.0,
        },
        "coefficients": {
            col: round(w, 6) for col, w in zip(feat_cols, weights)
        },
        "intercept": round(y_train_mean, 6),
    }

    raw_metrics = {
        "baseline": {"mae": base_mae, "rmse": base_rmse, "r2": base_r2},
        "model": {"mae": ridge_mae, "rmse": ridge_rmse, "r2": ridge_r2},
    }

    chart_data = {
        "samples": [
            {
                "index": i + 1,
                "actual": round(y_test[i], 4),
                "predicted_ridge": round(y_pred_ridge[i], 4),
                "predicted_baseline": round(y_pred_baseline[i], 4),
                "residual_ridge": round(y_test[i] - y_pred_ridge[i], 4),
            }
            for i in range(min(50, n_test))
        ]
    }

    readme_markdown = f"""# Hướng dẫn tái lập thực nghiệm (Reproducibility Protocol)

- **Routine**: `tabular_regression_v1` (Phiên bản: 1.0.0)
- **Thuật toán**: Ridge Regression ($\\alpha = {alpha}$) so sánh với Mean Baseline
- **Checksum tập dữ liệu đầu vào (SHA256)**: `{input_checksum}`
- **Cấu hình phân chia**: Split 80/20, `seed = {seed}` (Mẫu huấn luyện: {n_train}, Mẫu kiểm thử: {n_test})
- **Biến mục tiêu (Target)**: `{target_col}`
- **Tập biến đặc trưng (Features)**: {", ".join(f"`{c}`" for c in feat_cols)}

## Kết quả đo lường đối chứng

| Mô hình | MAE (Chính) | RMSE (Phụ) | $R^2$ |
| :--- | :--- | :--- | :--- |
| **Mean Baseline** | `{base_mae:.6f}` | `{base_rmse:.6f}` | `{base_r2:.6f}` |
| **Ridge Regression** | `{ridge_mae:.6f}` | `{ridge_rmse:.6f}` | `{ridge_r2:.6f}` |
| **Chênh lệch (Delta)** | `{delta_mae:+.6f}` | `{delta_rmse:+.6f}` | — |

**Kết luận khoa học**: `{verdict}` ({'Ridge regression cải thiện sai số so với baseline' if verdict == 'IMPROVEMENT' else 'Ridge regression không vượt trội hơn nghiệm trung bình đơn giản'}).

## Quy trình tiền xử lý bảo vệ tính trung thực (Leakage Prevention)
- Chuẩn hóa (Z-score standard deviation) và tính giá trị trung bình **chỉ thực hiện trên tập Train**.
- Tập Test hoàn toàn được chuẩn hóa dựa theo giá trị $\\mu$ và $\\sigma$ đã học từ tập Train, tuyệt đối không rò rỉ phân phối (Data Leakage).
"""

    return {
        "status": "COMPLETED",
        "input_checksum": input_checksum,
        "manifest": manifest,
        "metrics": metrics,
        # Kept separate so API/report artifacts remain rounded while the
        # repeatability check compares full-precision calculation results.
        "raw_metrics": raw_metrics,
        "chart_data": chart_data,
        "readme_markdown": readme_markdown,
        "verdict": verdict,
    }


def verify_repeatability(
    csv_text: str,
    original_result: Dict[str, Any],
    tolerance: float = 1e-8,
    relative_tolerance: float = 1e-6,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Reruns the exact routine with identical manifest and input.
    Verifies repeatability tolerance (abs <= 1e-8 or rel <= 1e-6).
    """
    manifest = original_result.get("manifest", {})
    input_checksum = hashlib.sha256(csv_text.strip().encode("utf-8")).hexdigest()
    if original_result.get("input_checksum") != input_checksum:
        return False, {
            "status": "FAILED",
            "reason": "INPUT_CHECKSUM_MISMATCH",
            "expected_checksum": original_result.get("input_checksum"),
            "actual_checksum": input_checksum,
            "tolerance": tolerance,
            "relative_tolerance": relative_tolerance,
        }
    if manifest.get("input_checksum") != input_checksum:
        return False, {
            "status": "FAILED",
            "reason": "MANIFEST_CHECKSUM_MISMATCH",
            "tolerance": tolerance,
            "relative_tolerance": relative_tolerance,
        }
    if (
        not math.isfinite(tolerance)
        or tolerance < 0
        or not math.isfinite(relative_tolerance)
        or relative_tolerance < 0
    ):
        raise InvalidInputError("Repeatability tolerances must be finite non-negative numbers")
    params = manifest.get("parameters", {})
    target_col = manifest.get("target_column")
    feat_cols = manifest.get("feature_columns")

    rerun_result = run_tabular_regression_v1(
        csv_text=csv_text,
        target_column=target_col,
        feature_columns=feat_cols,
        alpha=params.get("alpha", 1.0),
        test_size=params.get("test_size", 0.2),
        seed=params.get("seed", 42),
    )

    if rerun_result.get("manifest") != manifest:
        return False, {
            "status": "FAILED",
            "reason": "MANIFEST_MISMATCH",
            "tolerance": tolerance,
            "relative_tolerance": relative_tolerance,
        }

    original_metrics = original_result.get("raw_metrics")
    rerun_metrics = rerun_result.get("raw_metrics")
    if not isinstance(original_metrics, dict) or not isinstance(rerun_metrics, dict):
        return False, {
            "status": "FAILED",
            "reason": "RAW_METRICS_MISSING",
            "tolerance": tolerance,
            "relative_tolerance": relative_tolerance,
        }

    diffs: Dict[str, float] = {}
    comparisons: Dict[str, bool] = {}
    for group in ("baseline", "model"):
        for metric in ("mae", "rmse", "r2"):
            original_value = original_metrics.get(group, {}).get(metric)
            rerun_value = rerun_metrics.get(group, {}).get(metric)
            if (
                not isinstance(original_value, (int, float))
                or not isinstance(rerun_value, (int, float))
                or not math.isfinite(original_value)
                or not math.isfinite(rerun_value)
            ):
                return False, {
                    "status": "FAILED",
                    "reason": "INVALID_RAW_METRIC",
                    "metric": f"{group}.{metric}",
                    "tolerance": tolerance,
                    "relative_tolerance": relative_tolerance,
                }
            key = f"{group}.{metric}"
            diff = abs(original_value - rerun_value)
            relative_limit = relative_tolerance * max(abs(original_value), abs(rerun_value))
            diffs[key] = diff
            comparisons[key] = diff <= tolerance or diff <= relative_limit

    passed = all(comparisons.values())

    diff_report = {
        "differences": diffs,
        "comparisons": comparisons,
        # Retain the former public keys for clients while the canonical report
        # now includes baseline and model metrics at full precision.
        "diff_mae": diffs.get("model.mae"),
        "diff_rmse": diffs.get("model.rmse"),
        "diff_r2": diffs.get("model.r2"),
        "tolerance": tolerance,
        "relative_tolerance": relative_tolerance,
        "status": "PASSED" if passed else "FAILED",
    }

    return passed, diff_report
