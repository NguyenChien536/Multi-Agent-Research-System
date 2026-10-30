import hashlib
import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.evidence_review import prepare_evidence_review, evaluate_evidence_reviews, EvidenceReview, audit_matches_draft
from app.services.manuscript import attach_manuscript_contract
from app.agents import nodes
from tests.manuscript_helpers import complete_manuscript


def claim():
    return {"claim_id": str(uuid.uuid4()), "claim": "A limited comparison was reported.",
            "evidence_id": "e", "source_id": "s", "chunk_id": "c", "text_scope": "ABSTRACT",
            "evidence_quote": "A limited comparison was reported."}


def test_cited_evidence_after_the_first_fifty_records_is_selected():
    claims = [claim() for _ in range(60)]
    text = f"## Discussion\n\nA result under specific assumptions. [[@claim:{claims[-1]['claim_id']}]]"
    prepared = prepare_evidence_review(text, claims, central_headings=["Discussion"], draft=text)
    assert [c["claim_id"] for c in prepared["evidence"]] == [claims[-1]["claim_id"]]
    assert prepared["evidence"][0]["text_scope"] == "ABSTRACT"


def test_missing_unknown_and_duplicate_judgments_cannot_count_as_complete_review():
    text = "## Conclusion\n\nThe proposal requires formal proof and empirical evaluation."
    prepared = prepare_evidence_review(text, [], central_headings=["Conclusion"], draft=text)
    assert not evaluate_evidence_reviews(prepared, [])["coverage_complete"]
    review = EvidenceReview(statement_id=prepared["units"][0]["statement_id"], judgment="SUPPORTED", reason="Bounded statement")
    assert evaluate_evidence_reviews(prepared, [review])["all_supported"]
    assert not evaluate_evidence_reviews(prepared, [review, review])["coverage_complete"]
    assert not evaluate_evidence_reviews(prepared, [review.model_copy(update={"statement_id": "unknown"})])["coverage_complete"]


def test_context_overflow_and_partial_support_cannot_pass():
    c = claim()
    text = f"## Results\n\n{'Very long text ' * 400}[[@claim:{c['claim_id']}]]"
    prepared = prepare_evidence_review(text, [c], central_headings=[], draft=text)
    reviewed = [EvidenceReview(statement_id=u["statement_id"], judgment="SUPPORTED", reason="test") for u in prepared["units"]]
    assert not evaluate_evidence_reviews(prepared, reviewed)["all_supported"]
    shorter = prepare_evidence_review(f"A strong claim [[@claim:{c['claim_id']}]]", [c], central_headings=[], draft=text)
    partial = EvidenceReview(statement_id=shorter["units"][0]["statement_id"], judgment="PARTIAL", reason="Evidence only supports a weaker conclusion")
    result = evaluate_evidence_reviews(shorter, [partial])
    assert result["coverage_complete"] and not result["all_supported"]


def test_review_is_bound_to_the_exact_draft():
    draft = "A conditional finding."
    metadata = {"evidence_support_review": {"draft_sha256": hashlib.sha256(draft.encode()).hexdigest(),
                                           "coverage_complete": True, "all_supported": True}}
    assert audit_matches_draft(metadata, draft)
    assert not audit_matches_draft(metadata, draft + " A stronger conclusion.")


@pytest.mark.asyncio
async def test_provider_pass_without_required_judgments_requires_review(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fixture")
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: type("LLM", (), {"with_structured_output": lambda *args: object()})())
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", AsyncMock(return_value=nodes.CriticVerdict(verdict="PASS")))
    c = claim()
    state = {"plan": attach_manuscript_contract({}, "REVIEW", "en"), "research_type": "REVIEW", "claims": [c],
             "draft_report_markdown": complete_manuscript(f"A limited finding [[@claim:{c['claim_id']}]]", language="en")}
    result = await nodes.critic_node(state)
    assert result["critic_verdict"] == "NEEDS_REVIEW"
    assert not result["critic_review_metadata"]["evidence_support_review"]["coverage_complete"]
    delivered = await nodes.post_processor_node({**state, **result, "critic_verdict": "PASS"})
    assert delivered["critic_review_metadata"]["status"] == "NEEDS_REVIEW"


def test_historical_contract_does_not_require_new_review_policy():
    from app.services.manuscript import manuscript_contract
    historical = manuscript_contract("REVIEW", "en")
    historical.pop("evidence_review_policy")
    resumed = attach_manuscript_contract({"manuscript_contract": historical}, "REVIEW", "en")
    assert "evidence_review_policy" not in resumed["manuscript_contract"]
    assert resumed["manuscript_contract"] == historical
    assert resumed["manuscript_contract"] is not historical
