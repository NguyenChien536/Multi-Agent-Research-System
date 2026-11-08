"""Regressions from a real draft that referenced an absent table and misread MAE bars."""
from copy import deepcopy

import pytest

from app.services.manuscript import manuscript_contract
from app.services.scientific_paper import (
    build_scientific_figures, insert_measured_comparison_table,
    measured_comparison_table, scientific_context, validate_scientific_reporting,
)


def context():
    return {"figure_style_version": 4, "analysis": {
        "status": "COMPLETED", "routine_name": "tabular_regression_v1",
        "manifest": {"test_rows": 24}, "metrics": {
            "baseline": {"mae": 12.338741, "rmse": 14.210697, "r2": -.012568},
            "model": {"mae": 1.335145, "rmse": 1.468646, "r2": .989185}}}}


def codes(text, contract=None, ctx=None, figures=None):
    return {f["code"] for f in validate_scientific_reporting(
        text, contract or manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en"),
        ctx or context(), figures or [])}


@pytest.mark.parametrize("language,heading,label", [("en", "Results", "Table"), ("vi", "Kết quả", "Bảng")])
def test_table_uses_recorded_metrics_once_and_is_inserted_only_in_results(language, heading, label):
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", language)
    text = f"## {heading}\n\n{label} 1 reports the recorded measurements."
    result = insert_measured_comparison_table(text, context(), contract)
    assert "| Ridge | 1.33515 | 1.46865 | 0.989185 |" in result
    assert "| Training-mean baseline | 12.3387 | 14.2107 | -0.012568 |" in result
    assert result.count(f"{label} 1.") == 1
    assert insert_measured_comparison_table(result, context(), contract) == result
    assert "MISSING_TABLE" not in codes(result, contract)
    assert insert_measured_comparison_table("## Discussion\nNo Results yet.", context(), contract) == "## Discussion\nNo Results yet."


@pytest.mark.parametrize("change", ["pending", "missing", "nonfinite", "other_routine", "old_policy", "review"])
def test_table_never_invents_results_or_changes_old_contracts(change):
    ctx = context()
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    if change == "pending": ctx["analysis"]["status"] = "PENDING"
    if change == "missing": del ctx["analysis"]["metrics"]["model"]["rmse"]
    if change == "nonfinite": ctx["analysis"]["metrics"]["model"]["mae"] = float("nan")
    if change == "other_routine": ctx["analysis"]["routine_name"] = "unknown"
    if change == "old_policy": contract["rendering_policy"]["version"] = 1
    if change == "review": contract = manuscript_contract("REVIEW", "en")
    assert measured_comparison_table(ctx, contract) == ""


def test_missing_or_duplicate_numbered_table_is_reported_not_silently_accepted():
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    assert "MISSING_TABLE" in codes("Table 1 presents all measured results.")
    fake = "Table 1. Measured results.\n\nNo actual table follows."
    assert "MISSING_TABLE" in codes(fake)
    assert insert_measured_comparison_table(fake, context(), contract) == fake
    table = measured_comparison_table(context(), contract)
    assert "DUPLICATE_TABLE" in codes(table + "\n\n" + table)
    old = deepcopy(contract); old["rendering_policy"]["version"] = 1
    assert "MISSING_TABLE" not in codes(fake, old)


@pytest.mark.parametrize("text,flagged", [
    ("Figure 1 visualizes the absolute prediction error for each held-out observation.", True),
    ("Figure 1 displays the residual distribution.", True),
    ("Figure 1 compares two aggregate MAE values. It does not show errors for each observation.", False),
    ("Figure 1 shows two aggregate MAE bars; no uncertainty was estimated.", False),
])
def test_two_bar_figure_is_not_interpreted_as_individual_residuals(text, flagged):
    ctx = context(); figures = build_scientific_figures(ctx)
    assert ("FIGURE_SCOPE_MISMATCH" in codes(text + "\n\n[[figure:evaluation]]", ctx=ctx, figures=figures)) == flagged
    assert "two bars are aggregate" in figures[0]["caption"]
    old = {**ctx, "figure_style_version": 3}
    assert "two bars are aggregate" not in build_scientific_figures(old)[0]["caption"]


def test_old_saved_contract_keeps_figure_style_when_exported():
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    contract["rendering_policy"]["version"] = 1
    assert scientific_context({"plan": {"manuscript_contract": contract}})["figure_style_version"] == 3
