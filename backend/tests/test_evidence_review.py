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


def test_reviewer_receives_source_assumptions_without_turning_metadata_into_proof():
    record = {**claim(), "evidence_need_id": "comparison", "assumptions": ["Within the sampled population."]}
    text = f"A conditional comparison [[@claim:{record['claim_id']}]]"
    prepared = prepare_evidence_review(text, [record], central_headings=[], draft=text)
    assert prepared["evidence"][0]["assumptions"] == record["assumptions"]
    assert prepared["evidence"][0]["evidence_need_id"] == "comparison"
    assert not evaluate_evidence_reviews(prepared, [])["all_supported"]


def test_missing_unknown_and_duplicate_judgments_cannot_count_as_complete_review():
    text = "## Conclusion\n\nThe proposal requires formal proof and empirical evaluation."
    prepared = prepare_evidence_review(text, [], central_headings=["Conclusion"], draft=text)
    assert not evaluate_evidence_reviews(prepared, [])["coverage_complete"]
    review = EvidenceReview(statement_id=prepared["units"][0]["statement_id"], judgment="SUPPORTED", reason="Bounded statement")
    assert evaluate_evidence_reviews(prepared, [review])["all_supported"]
    assert not evaluate_evidence_reviews(prepared, [review, review])["coverage_complete"]
    assert not evaluate_evidence_reviews(prepared, [review.model_copy(update={"statement_id": "unknown"})])["coverage_complete"]


def test_multiple_evidence_records_for_one_claim_are_kept_and_bounded():
    first = claim()
    second = {**first, "evidence_id": "e2", "source_id": "s2", "evidence_quote": "A conflicting observation."}
    text = f"A qualified statement [[@claim:{first['claim_id']}]]"
    prepared = prepare_evidence_review(text, [first, second], central_headings=[], draft=text)
    assert len(prepared["evidence"]) == 2
    assert {e["source_id"] for e in prepared["evidence"]} == {"s", "s2"}
    limited = prepare_evidence_review(text, [first, second], central_headings=[], draft=text, max_evidence=1)
    assert limited["coverage_findings"]


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


@pytest.mark.parametrize('fault', ['missing', 'invented_quote', 'wrong_source', 'wrong_chunk', 'unrelated_claim', 'whitespace_only'])
def test_supported_verdict_without_source_bound_literal_anchor_cannot_pass_policy3(fault):
    record = claim()
    text = f"## Discussion\n\nThe method works under limited conditions. [[@claim:{record['claim_id']}]]"
    prepared = prepare_evidence_review(text, [record], central_headings=['Discussion'], draft=text, policy_version=3)
    anchor = {'claim_id': record['claim_id'], 'source_id': 's', 'chunk_id': 'c', 'quote': record['evidence_quote']}
    if fault == 'invented_quote': anchor['quote'] = 'This method always outperforms all baselines.'
    if fault == 'wrong_source': anchor['source_id'] = 'another-paper'
    if fault == 'wrong_chunk': anchor['chunk_id'] = 'another-chunk'
    if fault == 'unrelated_claim': anchor['claim_id'] = 'another-claim'
    if fault == 'whitespace_only': anchor['quote'] = ' '
    response = EvidenceReview(statement_id=prepared['units'][0]['statement_id'], judgment='SUPPORTED',
        reason='Overconfident fixture model response.', supporting_claim_ids=[record['claim_id']],
        quote_anchors=[] if fault == 'missing' else [anchor], assumptions_preserved=True)
    result = evaluate_evidence_reviews(prepared, [response])
    assert not result['all_supported'] and not result['coverage_complete']


def test_literal_anchor_is_a_source_correspondence_check_and_retains_historical_policy():
    record = claim()
    text = f"A conditional finding [[@claim:{record['claim_id']}]]"
    response = {'judgment': 'SUPPORTED', 'reason': 'The literal quote supports a bounded finding.',
                'supporting_claim_ids': [record['claim_id']], 'assumptions_preserved': True}
    old = prepare_evidence_review(text, [record], central_headings=[], draft=text, policy_version=2)
    old_review = EvidenceReview(statement_id=old['units'][0]['statement_id'], **response)
    assert evaluate_evidence_reviews(old, [old_review])['all_supported']
    current = prepare_evidence_review(text, [record], central_headings=[], draft=text, policy_version=3)
    current_review = EvidenceReview(statement_id=current['units'][0]['statement_id'], **response, quote_anchors=[
        {'claim_id': record['claim_id'], 'source_id':'s', 'chunk_id':'c', 'quote':'limited comparison'}])
    assert evaluate_evidence_reviews(current, [current_review])['all_supported']


def test_policy3_uncited_scope_statement_can_rely_on_actual_provenance_without_fake_citation():
    text = '## Methods\n\nNo experiment or systematic screening was performed in this narrative review.'
    prepared = prepare_evidence_review(text, [], central_headings=[], draft=text, policy_version=3)
    response = EvidenceReview(statement_id=prepared['units'][0]['statement_id'], judgment='SUPPORTED',
                              reason='Consistent with the supplied execution provenance.')
    assert evaluate_evidence_reviews(prepared, [response])['all_supported']


def test_one_good_anchor_cannot_hide_an_unchecked_second_direct_citation():
    first, second = claim(), claim()
    text = f"Two alleged findings [[@claim:{first['claim_id']}]][[@claim:{second['claim_id']}]]"
    prepared = prepare_evidence_review(text, [first, second], central_headings=[], draft=text, policy_version=3)
    response = EvidenceReview(statement_id=prepared['units'][0]['statement_id'], judgment='SUPPORTED',
        reason='Only the first citation was inspected.', supporting_claim_ids=[first['claim_id']], quote_anchors=[
            {'claim_id':first['claim_id'], 'source_id':'s', 'chunk_id':'c', 'quote':first['evidence_quote']}])
    assert not evaluate_evidence_reviews(prepared, [response])['all_supported']


@pytest.mark.asyncio
async def test_provider_pass_without_required_judgments_requires_review(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fixture")
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: type("LLM", (), {"with_structured_output": lambda *args: object()})())
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", AsyncMock(return_value=nodes.CriticVerdict(verdict="PASS")))
    c = claim()
    state = {"plan": attach_manuscript_contract({}, "REVIEW", "en"), "research_type": "REVIEW", "claims": [c],
             "evidence_need_coverage": {"missing_need_ids": ["causal-comparison"]},
             "draft_report_markdown": complete_manuscript(f"A limited finding [[@claim:{c['claim_id']}]]", language="en")}
    result = await nodes.critic_node(state)
    assert result["critic_verdict"] == "NEEDS_REVIEW"
    assert not result["critic_review_metadata"]["evidence_support_review"]["coverage_complete"]
    assert all("causal-comparison" in call.args[2][0].content
               for call in nodes.invoke_llm_with_budget.await_args_list)
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


def test_resume_keeps_policy2_while_new_plans_require_quote_anchors():
    from app.services.manuscript import manuscript_contract
    historical = manuscript_contract('REVIEW', 'en')
    historical['evidence_review_policy'] = {'version':2, 'scope':'historical snapshot'}
    historical['research_quality_policy'] = {'version':1, 'source_balance':'round_robin_discovery_queries'}
    resumed = attach_manuscript_contract({'manuscript_contract':historical}, 'REVIEW', 'en')
    assert resumed['manuscript_contract'] == historical
    assert manuscript_contract('REVIEW', 'en')['evidence_review_policy']['version'] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", [False, True])
@pytest.mark.parametrize("token_attribute", ["max_tokens", "max_output_tokens"])
async def test_critic_provider_cap_matches_reserved_output_budget(monkeypatch, policy, token_attribute):
    """Reservation alone must not leave a provider free to generate 4096 tokens."""
    from types import SimpleNamespace

    client = SimpleNamespace(**{token_attribute: 4096})
    captured = []
    client.with_structured_output = lambda _: captured.append(getattr(client, token_attribute)) or client
    chain = nodes.BudgetedFallbackLLM([("fixture", client)])
    invoke = AsyncMock(return_value=nodes.CriticVerdict(verdict="PASS"))
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: chain)
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fixture")
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", invoke)
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    plan = attach_manuscript_contract({}, "REVIEW", "en")
    if not policy:
        plan["manuscript_contract"].pop("evidence_review_policy")
    await nodes.critic_node({"plan": plan, "draft_report_markdown": "## Methods\n\nAn exploratory narrative review."})
    expected = 2048 if policy else 768
    assert captured == [expected]
    assert invoke.await_count > 0
    assert all(call.kwargs["output_tokens"] == expected for call in invoke.await_args_list)
