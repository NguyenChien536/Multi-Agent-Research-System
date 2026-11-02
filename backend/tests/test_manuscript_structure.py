"""Hierarchy/regression fixtures test software, not article quality or novelty."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents import nodes
from app.services.academic_writing import writing_guidance
from app.services.manuscript import attach_manuscript_contract, manuscript_contract, validate_manuscript
from app.services.manuscript_structure import review_sections, validate_hierarchy
from tests.manuscript_helpers import complete_manuscript, supported_critic_response


@pytest.mark.parametrize("kind,required,absent", [
    ("REVIEW", {"review_methods", "synthesis"}, {"methods", "setup", "results"}),
    ("EMPIRICAL_COMPUTATIONAL", {"methods", "setup", "results"}, {"review_methods", "synthesis"}),
    ("EMPIRICAL_HUMAN", {"methods", "results"}, {"setup", "review_methods", "synthesis"}),
])
@pytest.mark.parametrize("language", ["en", "vi", "ja"])
def test_each_genre_has_its_own_frozen_hierarchy_without_a_one_topic_template(kind, required, absent, language):
    contract = manuscript_contract(kind, language)
    policy = contract["structure_policy"]
    assert required <= policy["sections"].keys()
    assert not absent & policy["sections"].keys()
    text = complete_manuscript("The controlled observations have limited scope.", kind, language)
    assert not validate_hierarchy(text, contract)
    assert "exemplar" in writing_guidance(contract)
    assert "Gale" not in str(policy) and "NSGA" not in str(policy)


@pytest.mark.parametrize("topic", ["Education outcomes", "Workplace retention", "Resource allocation"])
def test_topic_specific_children_are_reviewed_once_and_parent_is_not_an_empty_passage(topic):
    first, second = "Observed patterns and their limits.", "Conflicting evidence and open questions."
    text = f"# {topic}\n\n## Synthesis\n\n### {topic}: observed patterns\n\n{first}\n\n### {topic}: competing explanations\n\n{second}"
    sections = review_sections(text)
    assert len(sections) == 2
    assert [body for _, body in sections] == [first, second]
    assert all(name.startswith("Synthesis / ") for name, _ in sections)
    assert "(No section body.)" not in str(sections)


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_code_examples_cannot_create_fake_manuscript_sections(fence):
    text = f"# Title\n\n## Analysis\n\nActual paragraph.\n\n{fence}markdown\n### Fake section\nFake evidence.\n{fence}\n\nActual final paragraph."
    combined = str(review_sections(text))
    assert "Fake section" not in combined and "Fake evidence" not in combined
    assert "Actual paragraph" in combined and "Actual final paragraph" in combined


@pytest.mark.parametrize("code", [
    "  ```markdown\n### Fake heading\n  ```",  # Indented fences.
    "```markdown\n### Fake heading\n`````",   # Longer closing fence, EOF.
    "~~~markdown\n### Fake heading\n~~~~~",   # Tilde fence.
    "```markdown\n### Fake heading",          # Unclosed fence.
    "```markdown\n### Fake heading\n~~~",    # Other marker does not close it.
])
def test_valid_and_unclosed_code_fences_never_create_fake_sections(code):
    assert "Fake heading" not in str(review_sections("# Real title\n\n## Body\n\nActual text.\n\n" + code))
    text = "# Real title\n\n" + code + "\n## Introduction\nFake introduction body."
    codes = {f["code"] for f in validate_manuscript(text, manuscript_contract("REVIEW", "en"))}
    assert "MISSING_SECTION" in codes


def test_empty_real_subsection_is_flagged_even_when_parent_has_populated_children():
    contract = manuscript_contract("REVIEW", "en")
    findings = validate_hierarchy("# Topic\n\n## Thematic Synthesis\n\n### Empty analytical subsection\n\n### Actual evidence\n\nA documented limited finding.", contract)
    assert any(f["code"] == "EMPTY_SUBSECTION" for f in findings)
    assert not any("Thematic Synthesis" in f["message"] and f["code"] == "EMPTY_SUBSECTION" for f in findings)


def test_headings_alone_do_not_satisfy_substantive_hierarchy_and_missing_levels_are_detected():
    contract = manuscript_contract("REVIEW", "en")
    text = "# Topic\n\n## Thematic Synthesis\n\n" + "Available evidence remains limited. " * 20 + "\n\n#### Jumped level\n\nShort."
    codes = {f["code"] for f in validate_hierarchy(text, contract)}
    assert {"HEADING_DEPTH", "SUBSECTION_STRUCTURE"} <= codes
    text = "# Topic\n\n## Thematic Synthesis\n\n" + "Evidence supports only a bounded inference. " * 12
    text += "\n\n### Topic one\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n### Topic two\n\nShort."
    assert "UNDEVELOPED_SUBSECTION" in {f["code"] for f in validate_hierarchy(text, contract)}


def test_search_ledger_does_not_force_fragmentation_or_count_as_an_analytical_subsection():
    contract = manuscript_contract("REVIEW", "en")
    text = "# Topic\n\n## Literature Search and Scope\n\nA compact documented narrative search.\n\n### Recorded search activity\n\n" + "| technical metadata | " * 100
    assert not validate_hierarchy(text, contract)


def test_subsection_containing_only_a_ledger_is_still_empty():
    text = "# Topic\n\n## Thematic Synthesis\n\n### Empty wrapper\n\n#### Recorded search activity\n\n| technical | metadata |"
    findings = validate_hierarchy(text, manuscript_contract("REVIEW", "en"))
    assert any(f["code"] == "EMPTY_SUBSECTION" and "Empty wrapper" in f["message"] for f in findings)


def test_citation_marker_lengths_do_not_substitute_for_subsection_argument():
    text = "# Topic\n\n## Thematic Synthesis\n\n### Findings\n\n" + "[[@claim:00000000-0000-0000-0000-000000000001]]" * 10
    assert "UNDEVELOPED_SUBSECTION" in {f["code"] for f in validate_hierarchy(text, manuscript_contract("REVIEW", "en"))}


def test_historical_contract_does_not_silently_gain_new_hierarchy_rules():
    frozen = attach_manuscript_contract({}, "REVIEW", "en")
    frozen["manuscript_contract"]["version"] = 3
    frozen["manuscript_contract"].pop("structure_policy")
    frozen["manuscript_contract"]["writing_brief"]["version"] = 1
    copied = attach_manuscript_contract(frozen, "REVIEW", "en")
    assert "structure_policy" not in copied["manuscript_contract"]
    assert copied["manuscript_contract"]["writing_brief"]["version"] == 1
    assert not validate_hierarchy("# Historic paper\n\n## Thematic Synthesis\n\nAn older body.", copied["manuscript_contract"])


@pytest.mark.asyncio
async def test_critic_receives_real_nested_body_instead_of_title_or_container_placeholders(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fixture")
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: SimpleNamespace(with_structured_output=lambda _: object()))
    prompts = []
    async def invoke(state, llm, messages, **kwargs):
        prompts.append(messages[0].content)
        return supported_critic_response(messages)
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", invoke)
    state = {"language": "en", "research_type": "REVIEW", "plan": attach_manuscript_contract({}, "REVIEW", "en"),
             "draft_report_markdown": complete_manuscript("The controlled finding has limited scope.", language="en")}
    result = await nodes.critic_node(state)
    audit = result["critic_review_metadata"]["evidence_support_review"]
    passages = [p["passage"] for batch in audit["batches"] for p in batch["passages"]]
    assert passages and all(p != "(No section body.)" for p in passages)
    assert any("controlled finding" in p for p in passages)
    assert all("(No section body.)" not in prompt for prompt in prompts)


@pytest.mark.asyncio
async def test_writer_receives_outline_as_provisional_and_records_context_diagnostics(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    record = AsyncMock()
    monkeypatch.setattr(nodes, "record_agent_run", record)
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fixture")
    monkeypatch.setattr(nodes, "get_smart_llm", lambda: object())
    async def invoke(state, llm, messages, **kwargs):
        assert "OUTLINE_SENTINEL" in messages[0].content
        assert "provisional" in messages[0].content.lower()
        return SimpleNamespace(content=complete_manuscript("A controlled finding.", language="en"),
            response_metadata={"finish_reason": "STOP", "model_name": "fixture-snapshot"})
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", invoke)
    state = {"language": "en", "research_type": "REVIEW", "plan": attach_manuscript_contract({"section_outline": [
        {"section_id": "synthesis", "subsection_titles": ["OUTLINE_SENTINEL", "Evidence limits"],
         "purpose": "Compare available supported explanations."}]}, "REVIEW", "en")}
    await nodes.writer_node(state)
    summary = record.call_args.kwargs
    assert summary["input_summary"]["prompt_characters"] > 0
    assert summary["input_summary"]["requested_output_tokens"] == 8192
    assert summary["input_summary"]["evidence_sources"] == 0
    assert summary["output_summary"]["reported_model"] == "fixture-snapshot"
    assert summary["output_summary"]["truncated"] is False


@pytest.mark.asyncio
async def test_consecutive_same_source_labels_are_collapsed_without_losing_claim_lineage(monkeypatch):
    import uuid
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    source_id = str(uuid.uuid4())
    claims = [{"claim_id": str(uuid.uuid4()), "evidence_id": str(uuid.uuid4()),
               "source_id": source_id, "source_title": "One supported source"} for _ in range(2)]
    draft = "A joint finding " + "".join(f"[[@claim:{c['claim_id']}]]" for c in claims) + ". The following text must remain."
    result = await nodes.post_processor_node({"draft_report_markdown": draft, "claims": claims})
    assert "A joint finding [1]. The following text must remain." in result["final_report_markdown"]
    assert "[1][1]" not in result["final_report_markdown"]
    assert {c["claim_id"] for c in result["citations"]} == {c["claim_id"] for c in claims}
