from tests.manuscript_helpers import supported_critic_response
import io
import json
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree

import pytest

from app.agents import nodes
from app.services.academic_writing import writing_brief, writing_guidance
from app.services.manuscript import manuscript_contract, attach_manuscript_contract
from app.services.references import format_reference, reference_identity, reference_suffixes, reference_metadata_notes
from app.services.publication_export import build_publication_bundle
from app.services.scientific_paper import build_scientific_figures, materialize_figures, scientific_context, validate_scientific_reporting
from tests.manuscript_helpers import complete_manuscript
from tests.test_publication import measured_context


@pytest.mark.parametrize("kind,expected,absent", [
    ("REVIEW", "synthesis", "setup"),
    ("EMPIRICAL_COMPUTATIONAL", "setup", "review_methods"),
    ("EMPIRICAL_HUMAN", "results", "setup"),
])
def test_brief_matches_the_article_method_and_does_not_supply_research_evidence(kind, expected, absent):
    contract = manuscript_contract(kind, "vi")
    brief = contract["writing_brief"]
    assert contract["version"] == 3
    assert expected in brief["section_goals"] and absent not in brief["section_goals"]
    assert "reference_identity" in " ".join(brief["review_criteria"])
    assert "http" not in json.dumps(brief) and "STORM" not in json.dumps(brief)
    brief["section_goals"].clear()
    assert writing_brief(contract["article_type"])["section_goals"]  # No global mutation.
    assert writing_guidance({"version": 2}) == ""  # No silent upgrade of frozen contracts.


@pytest.mark.asyncio
async def test_writer_and_critic_use_the_same_frozen_brief(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fixture")
    monkeypatch.setattr(nodes, "get_smart_llm", lambda: object())
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: SimpleNamespace(with_structured_output=lambda _: object()))
    prompts = []
    async def invoke(state, llm, messages, **kwargs):
        prompts.append(messages[0].content)
        if "internal report quality-control" in messages[0].content:
            return supported_critic_response(messages)
        return SimpleNamespace(content=complete_manuscript("A bounded interpretation.", language="en"))
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", invoke)
    plan = attach_manuscript_contract({}, "REVIEW", "en")
    plan["manuscript_contract"]["writing_brief"]["paragraph_rule"] = "FROZEN_PROFILE_SENTINEL"
    state = {"plan": plan, "language": "en", "research_type": "REVIEW"}
    written = await nodes.writer_node(state)
    reviewed = await nodes.critic_node({**state, **written})
    assert all("FROZEN_PROFILE_SENTINEL" in prompt for prompt in prompts)
    assert reviewed["critic_review_metadata"]["manuscript_contract"]["writing_brief"] == plan["manuscript_contract"]["writing_brief"]
    assert "Do not mark unseen sections" in prompts[-1]


def test_ieee_preserves_known_author_and_year_without_inventing_venue_or_access_date():
    source = {"source_title": "A grounded paper", "source_author": "A. Researcher", "publication_date": "2024-04-02", "source_url": "https://example.org/paper"}
    label, text = format_reference(source, 2, "IEEE")
    assert label == "[2]" and all(value in text for value in ("A. Researcher", "2024", "A grounded paper", "https://example.org/paper"))
    assert "Accessed" not in text and "DOI" not in text
    label, text = format_reference({"source_title": "Undated source"}, 1, "APA")
    assert label == "(Undated source, n.d.)"
    assert reference_metadata_notes([{"source_title": "Undated source"}])[0]["missing"] == ["author", "publication_year", "url"]


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["APA", "HARVARD"])
async def test_colliding_author_year_sources_keep_distinct_labels_lineage_and_export(style, monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    claims = [{"claim_id": str(uuid.uuid4()), "source_id": str(uuid.uuid4()), "evidence_id": str(uuid.uuid4()),
               "source_author": "Same Author", "source_title": f"Study {index}", "publication_date": "2024", "source_url": f"https://example.org/{index}"} for index in range(2)]
    draft = "# Comparison\n\n" + " ".join(f"Supported finding [[@claim:{item['claim_id']}]]." for item in claims)
    result = await nodes.post_processor_node({"claims": claims, "citation_style": style, "draft_report_markdown": draft})
    assert {c["citation_label"] for c in result["citations"]} == {"(Same Author, 2024a)", "(Same Author, 2024b)"}
    assert "Study 0" in result["final_report_markdown"] and "Study 1" in result["final_report_markdown"]
    data, _ = build_publication_bundle("Comparison", result["final_report_markdown"], result["critic_review_metadata"], result["citations"], "IEEE_CONFERENCE", version_id="v1", version_number=1)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        tex = archive.read("main.tex").decode()
        assert r"\cite{ref1}" in tex and r"\cite{ref2}" in tex
        assert len(json.loads(archive.read("references.json"))) == 2


def test_disambiguation_handles_truncated_labels_and_many_sources_without_collision():
    items = [{"source_id": str(i), "source_author": "A" * 470 + str(i), "publication_date": "2024"} for i in range(28)]
    suffixes = reference_suffixes(items + [items[0]], "APA")
    labels = [format_reference(item, i, "APA", suffix=suffixes[reference_identity(item)])[0] for i, item in enumerate(items)]
    assert len(set(labels)) == 28 and labels[-1].endswith("2024ab)")
    assert reference_suffixes(items, "IEEE") == {}


def test_ambiguous_historical_labels_are_not_silently_exported_to_the_wrong_source():
    with pytest.raises(ValueError, match="Ambiguous"):
        build_publication_bundle("Old article", "# Old article\n\nA claim (Author, 2024).", {},
            [{"source_id": "one", "citation_label": "(Author, 2024)"}, {"source_id": "two", "citation_label": "(Author, 2024)"}],
            "IEEE_CONFERENCE", version_id="old", version_number=1)


@pytest.mark.parametrize("values", [(3.0, 1.5), (1.0, 4.0), (0.0, 0.0), (1e-200, 2e-200)])
def test_new_plot_has_zero_based_ticks_accessible_data_and_no_invented_uncertainty(values):
    context = measured_context(); context["figure_style_version"] = 2
    context["analysis"]["metrics"]["baseline"]["mae"], context["analysis"]["metrics"]["model"]["mae"] = values
    figure = build_scientific_figures(context, {})[0]
    root = ElementTree.fromstring(figure["svg"])
    assert root.attrib["aria-labelledby"] == "evaluation-title evaluation-desc"
    assert "MAE (target units)" in figure["svg"] and "uncertainty not estimated" in figure["svg"]
    assert "ytick={0,0.25,0.5,0.75,1}" in figure["latex"]
    assert figure["data"] == {"baseline_mae": values[0], "ridge_mae": values[1]}
    assert "no confidence intervals" in figure["caption"]


def test_figure_policy_and_legacy_bundle_preserve_frozen_appearance_and_measurements():
    legacy = measured_context()
    figures = build_scientific_figures(legacy, {})
    assert "style_version" not in figures[0]
    assert scientific_context({"plan": {"manuscript_contract": {"version": 2}}})["figure_style_version"] == 1
    assert scientific_context({"plan": attach_manuscript_contract({}, "REVIEW", "en")})["figure_style_version"] == 2
    data, _ = build_publication_bundle("Historical article", "![Figure 1](figures/evaluation.svg)", {"scientific_context": legacy, "scientific_figures": figures}, [], "ACM_SIGCONF", version_id="old", version_number=1)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.read("figures/evaluation.svg").decode() == figures[0]["svg"]
        assert r"\Description{" in archive.read("main.tex").decode()


def test_figure_number_order_and_duplicate_assets_are_checked_for_new_contracts():
    figures = build_scientific_figures({**measured_context(), "figure_style_version": 2}, {"available_source_count": 3})
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    text = "[[figure:evaluation]]\n\n[[figure:workflow]]\n\n[[figure:workflow]]"
    assert {"FIGURE_ORDER", "DUPLICATE_FIGURE"} <= {f["code"] for f in validate_scientific_reporting(text, contract, measured_context(), figures)}


def test_metric_check_reads_the_whole_scientific_notation_value():
    context = measured_context(); context["analysis"]["metrics"]["model"]["mae"] = .00015
    contract = manuscript_contract("EMPIRICAL_COMPUTATIONAL", "en")
    honest = validate_scientific_reporting("## Results\n\nRidge MAE = 1.5e-4.", contract, context, [])
    assert not any(f["code"] == "METRIC_MISMATCH" for f in honest)
    wrong = validate_scientific_reporting("## Results\n\nRidge MAE = 1.5e+4.", contract, context, [])
    assert any(f["code"] == "METRIC_MISMATCH" for f in wrong)


def test_specific_table_caption_survives_publication_export_as_a_caption_not_duplicate_prose():
    text = "# Study\n\n## Results\n\nTable 1 compares held-out errors; only one split was evaluated.\n\nTable 1. Baseline and Ridge on the same held-out rows\n\n| Method | MAE |\n|---|---|\n| Baseline | 3 |\n| Ridge | 1.5 |"
    data, _ = build_publication_bundle("Study", text, {}, [], "IEEE_CONFERENCE", version_id="v", version_number=1)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        tex = archive.read("main.tex").decode()
        assert r"\caption{Baseline and Ridge on the same held-out rows}" in tex
        assert tex.count("Baseline and Ridge on the same held-out rows") == 1
        assert "Table 1 compares held-out errors" in tex
