import base64
import io
import json
import math
import uuid
import zipfile

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.models.report import ResearchReport, ReportVersion
from app.services.manuscript import manuscript_contract, validate_manuscript, writer_claim_context, normalize_claim_markers
from app.services.publication_export import build_publication_bundle
from app.services.scientific_paper import build_scientific_figures, validate_scientific_reporting, materialize_figures
from tests.manuscript_helpers import complete_manuscript
from tests.test_report_versions import _register_and_login


def measured_context():
    return {"analysis": {"status": "COMPLETED", "metrics": {"baseline": {"mae": 3.0}, "model": {"mae": 1.5}},
                         "manifest": {"test_rows": 12, "parameters": {"seed": 42}}},
            "statistical_significance_tested": False}


def test_v2_requires_related_work_and_a_research_argument():
    contract = manuscript_contract("REVIEW", "en")
    assert "related_work" in [item["id"] for item in contract["sections"]]
    text = complete_manuscript("A sourced finding.", language="en")
    assert not validate_manuscript(text, contract)
    # A feature description cannot stand in for a research question and gap.
    intro = text.split("## Introduction")[1].split("## Related Work")[0]
    bad = text.replace(intro, "\n\nThe software provides authentication, search and reporting for its users.\n\n")
    codes = {f["code"] for f in validate_manuscript(bad, contract)}
    assert {"RESEARCH_QUESTION", "RESEARCH_GAP", "CONTRIBUTIONS"} <= codes


def test_figures_are_built_from_measured_outputs_and_label_their_limits():
    figures = build_scientific_figures(measured_context(), {"available_source_count": 3})
    assert [f["kind"] for f in figures] == ["conceptual", "measured"]
    assert figures[1]["data"] == {"baseline_mae": 3.0, "ridge_mae": 1.5}
    assert "no confidence intervals" in figures[1]["caption"]
    assert "1.5" in figures[1]["svg"]
    assert "statistical_significance_tested" not in figures[1]["data"]
    assert not build_scientific_figures({}, {})
    context = measured_context(); context["analysis"]["metrics"]["model"]["mae"] = math.nan
    with pytest.raises(ValueError):
        build_scientific_figures(context, {})


def test_scientific_gates_require_baseline_and_interpretation_not_promotional_claims():
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    figs = build_scientific_figures(measured_context(), {})
    bad = "Our method is significantly better and achieves perfect accuracy.\n\n[[figure:evaluation]]"
    codes = {f["code"] for f in validate_scientific_reporting(bad, contract, {}, figs)}
    assert {"BASELINE_MISSING", "FIGURE_UNEXPLAINED", "UNSUPPORTED_SIGNIFICANCE", "UNSUPPORTED_SUPERLATIVE"} <= codes
    honest = "Figure 1 reports two measured MAE values on the same held-out synthetic cases; this limited comparison does not establish statistical significance.\n\n[[figure:evaluation]]"
    assert not validate_scientific_reporting(honest, contract, measured_context(), figs)


def test_numeric_results_and_generalization_are_checked_against_the_run():
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    text = "## Results\n\nRidge MAE = 99.0 and our approach is universally superior.\n\n| model | score |\n|---|---|\n| Ridge | 99 |"
    codes = {f["code"] for f in validate_scientific_reporting(text, contract, measured_context(), [])}
    assert {"METRIC_MISMATCH", "UNSUPPORTED_GENERALIZATION", "TABLE_UNEXPLAINED"} <= codes


def test_uncited_related_work_cannot_pass_when_grounded_claims_are_available():
    context = {"grounded_claim_count": 1}
    findings = validate_scientific_reporting(complete_manuscript("Uncited overview.", language="en"), manuscript_contract("REVIEW", "en"), context, [])
    assert any(f["code"] == "UNCITED_RESEARCH_CONTEXT" for f in findings)


def test_a_negative_clause_does_not_hide_an_unsupported_positive_claim():
    findings = validate_scientific_reporting("No baseline was evaluated; our method is significantly better.", manuscript_contract("REVIEW", "en"), {}, [])
    assert any(f["code"] == "UNSUPPORTED_SIGNIFICANCE" for f in findings)


def test_writer_receives_one_citation_identity_and_caption_is_not_interpretation():
    claim_id, evidence_id = str(uuid.uuid4()), str(uuid.uuid4())
    context = writer_claim_context([{"claim_id":claim_id,"evidence_id":evidence_id,"source_id":str(uuid.uuid4()),"claim":"A grounded result.","evidence_quote":"The original supporting passage."}])
    assert context[0]["citation_marker"] == f"[[@claim:{claim_id}]]"
    assert context[0]["claim"] == "A grounded result."
    assert context[0]["evidence_quote"] == "The original supporting passage."
    assert evidence_id not in json.dumps(context)
    figs = build_scientific_figures(measured_context(), {})
    findings = validate_scientific_reporting("*Figure 1: This is a long caption with many words but it is not an explanatory analytical paragraph.*\n\n[[figure:evaluation]]", manuscript_contract("EMPIRICAL_COMPUTATIONAL","en"), measured_context(), figs)
    assert any(f["code"] == "FIGURE_UNEXPLAINED" for f in findings)


def test_explicit_narrative_disclaimers_are_not_systematic_review_claims():
    text=complete_manuscript("A sourced finding.",language="en")
    text=text.replace("## Literature Search and Scope\n", "## Literature Search and Scope\n\nThis is a narrative review rather than a systematic meta-analysis. The methodology explicitly avoids claiming PRISMA-compliant screening protocols.\n")
    assert not any(f["code"] == "UNSUPPORTED_METHOD" for f in validate_manuscript(text, manuscript_contract("REVIEW","en")))


def test_a_fabricated_chart_url_cannot_be_delivered_as_a_figure():
    findings = validate_scientific_reporting("![Accuracy experiment](https://example.com/invented-results.png)", manuscript_contract("REVIEW","en"), {}, [])
    assert any(f["code"] == "UNKNOWN_FIGURE" for f in findings)


def test_grouped_claim_markers_preserve_each_identity_and_unknowns_still_fail():
    from app.agents.nodes import _claim_lineage_findings
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    text = f"A comparison [[@claim:{first}, @claim:{second}]]."
    normalized = normalize_claim_markers(text)
    assert f"[[@claim:{first}]][[@claim:{second}]]" in normalized
    claim = {"claim_id":first,"evidence_id":"e1","source_id":"s1","chunk_id":"c1"}
    findings = _claim_lineage_findings(text, [claim])
    assert len(findings) == 1 and second in findings[0]
    malformed = f"[[@claim:{first}, @claim:truncated]]"
    assert normalize_claim_markers(malformed) == malformed
    assert _claim_lineage_findings(malformed, [claim])


@pytest.mark.parametrize("template,document_class", [("IEEE_CONFERENCE", "IEEEtran"), ("ACM_SIGCONF", "acmart")])
def test_publication_source_uses_official_class_measured_figures_and_escaped_text(template, document_class):
    context = measured_context(); figures = build_scientific_figures(context, {})
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    draft = complete_manuscript("A result [1].\n\nFigure 1 compares the measured baseline and model errors on the held-out observations; it does not estimate uncertainty.\n\n[[figure:evaluation]]", "EMPIRICAL_COMPUTATIONAL", "en")
    md = materialize_figures(draft, figures) + "\n\n" + r"$\input{/etc/passwd}$"
    data, manifest = build_publication_bundle(r"A title \write18{bad}", md,
        {"manuscript_contract": contract, "scientific_context": context, "scientific_figures": figures, "status": "NEEDS_REVIEW"},
        [{"source_id": "s1", "source_title": "Known source", "citation_label": "[1]"}], template, version_id="v1", version_number=1)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        tex = archive.read("main.tex").decode()
        assert "{" + document_class + "}" in tex
        assert r"\input{/etc/passwd}" not in tex
        assert r"\write18{bad}" not in tex
        assert r"\cite{ref1}" in tex
        assert "figures/evaluation.tex" in archive.namelist()
        assert json.loads(archive.read("figures/evaluation.json"))["ridge_mae"] == 1.5
        assert all(not name.startswith(("/", "..")) for name in archive.namelist())
        assert json.loads(archive.read("provenance.json"))["report_version_id"] == "v1"
    assert manifest["review_status"] == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_publication_api_is_owner_scoped_and_version_pinned():
    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner = await _register_and_login(client, f"publication_owner_{suffix}")
        other = await _register_and_login(client, f"publication_other_{suffix}")
        response = await client.post("/api/v1/research", headers=owner, json={"title": "Publication version test", "research_question": "How can publication exports preserve their source version?"})
        tid = uuid.UUID(response.json()["id"])
        async with AsyncSessionLocal() as db:
            report = ResearchReport(research_task_id=tid); db.add(report); await db.flush()
            first = ReportVersion(report_id=report.id, version_number=1, title="Original title", content_markdown=complete_manuscript("Original evidence.", language="en"))
            later = ReportVersion(report_id=report.id, version_number=2, title="Later title", content_markdown="# Later content")
            db.add_all([first, later]); await db.commit(); first_id = first.id
        url = f"/api/v1/research/{tid}/report/versions/1/publication"
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=other)).status_code == 404
        assert (await client.get(url + "?template=UNKNOWN", headers=owner)).status_code == 422
        response = await client.get(url + "?template=IEEE_CONFERENCE", headers=owner)
        assert response.status_code == 200, response.text
        assert "no-store" in response.headers["cache-control"]
        result = response.json(); assert result["report_version_id"] == str(first_id)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(result["archive_base64"]))) as archive:
            tex = archive.read("main.tex").decode()
            assert "Original title" in tex and "Later title" not in tex
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, tid); task.status = "DELETING"; await db.commit()
        assert (await client.get(url, headers=owner)).status_code == 404
