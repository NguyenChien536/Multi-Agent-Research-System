# backend/tests/test_execution_evidence.py
from __future__ import annotations

import copy
import pytest

from app.services.execution_evidence import (
    FACT_ID,
    FACT_SCOPE,
    execution_procedure_fact,
)


@pytest.fixture
def valid_context() -> dict:
    return {
        "analysis": {
            "analysis_run_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
            "status": "COMPLETED",
            "routine_name": "tabular_regression_v1",
            "reproducibility_status": "PASSED",
            "manifest": {
                "parameters": {
                    "seed": 42,
                    "target_column": "sales",
                },
                "dataset_rows": 60,
                "train_rows": 48,
                "test_rows": 12,
            },
        }
    }


@pytest.mark.parametrize(
    "paragraph",
    [
        "The train/test partition is deterministic using seed=42 for repeatable allocation.",
        "A fixed partition was generated with seed 42 to ensure repeatable split.",
        "Using seed:42, the routine produced a deterministic split of the dataset.",
        "Quy trình phân chia tập dữ liệu được xác định cố định với seed 42 để đảm bảo lặp lại.",
        "Thực hiện phân bổ dữ liệu có tính xác định với seed: 42.",
        "Phép phân chia là lặp lại nhờ seed of 42.",
    ],
)
def test_positive_actual_seed_procedure_en_vi(paragraph: str, valid_context: dict) -> None:
    res = execution_procedure_fact(paragraph, valid_context)
    assert res is not None
    assert res["fact_id"] == FACT_ID
    assert res["value"] == 42
    assert res["analysis_run_id"] == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
    assert res["scope"] == FACT_SCOPE


@pytest.mark.parametrize(
    "paragraph",
    [
        "Deterministic split generated with seed 7.",
        "Repeatable partition using seed=123 instead of default.",
        "Quy trình phân chia xác định với seed 99.",
        "Deterministic partition with seed 42 and secondary seed 43.",
    ],
)
def test_reject_mismatched_seed(paragraph: str, valid_context: dict) -> None:
    assert execution_procedure_fact(paragraph, valid_context) is None


@pytest.mark.parametrize(
    "claim_addition",
    [
        " It guarantees stability across runs.",
        " It ensures stable matching for all datasets.",
        " The procedure significantly outperforms other models.",
        " This ensures strategy-proofness in evaluation.",
        " The split achieves Pareto optimal allocations.",
        " It proves causality between variables.",
        " The result has high statistical significance.",
        " Yields superior accuracy compared to alternatives.",
        " Works always on every dataset.",
        " Provides universal anonymity and privacy.",
        " Đảm bảo tính ổn định và công bằng xã hội.",
        " Chứng minh mối quan hệ nhân quả tuyệt đối.",
        " Bảo vệ quyền riêng tư và bảo mật dữ liệu.",
        " Đạt độ chính xác vượt trội tốt nhất.",
    ],
)
def test_reject_scientific_or_privacy_claims(claim_addition: str, valid_context: dict) -> None:
    paragraph = f"Deterministic partition with seed=42.{claim_addition}"
    assert execution_procedure_fact(paragraph, valid_context) is None


@pytest.mark.parametrize(
    "patch",
    [
        {"status": "FAILED"},
        {"status": "RUNNING"},
        {"reproducibility_status": "FAILED"},
        {"reproducibility_status": "PENDING"},
        {"routine_name": "unsupported_routine_v2"},
        {"analysis_run_id": ""},
        {"analysis_run_id": None},
    ],
)
def test_reject_invalid_analysis_metadata(patch: dict, valid_context: dict) -> None:
    ctx = copy.deepcopy(valid_context)
    ctx["analysis"].update(patch)
    paragraph = "Deterministic partition with seed=42."
    assert execution_procedure_fact(paragraph, ctx) is None


@pytest.mark.parametrize(
    "bad_seed",
    [
        True,
        False,
        "42",
        42.0,
        None,
    ],
)
def test_reject_non_integer_seeds(bad_seed: object, valid_context: dict) -> None:
    ctx = copy.deepcopy(valid_context)
    ctx["analysis"]["manifest"]["parameters"]["seed"] = bad_seed
    paragraph = "Deterministic partition with seed=42."
    assert execution_procedure_fact(paragraph, ctx) is None


def test_reject_overlong_paragraph(valid_context: dict) -> None:
    filler = "deterministic partition " * 35
    paragraph = f"seed=42 {filler}"
    assert len(paragraph) > 700
    assert execution_procedure_fact(paragraph, valid_context) is None


def test_immutability_of_inputs(valid_context: dict) -> None:
    paragraph = "The deterministic partition was configured with seed=42."
    ctx_copy = copy.deepcopy(valid_context)

    res = execution_procedure_fact(paragraph, valid_context)
    assert res is not None
    assert valid_context == ctx_copy
