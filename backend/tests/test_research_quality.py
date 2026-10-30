import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.research_quality import balance_by_query, query_coverage, canonicalize_quote_markers, unique_quote_claims, inject_search_ledger
from app.services.evidence_review import prepare_evidence_review, evaluate_evidence_reviews, EvidenceReview
from app.services.manuscript import attach_manuscript_contract
from app.tools.search_models import SearchResult


def test_first_query_cannot_consume_the_entire_candidate_budget():
    candidates = [SearchResult(title=f"{q} {i}", url=f"https://example.org/{q}/{i}", query=q)
                  for q in ("matching", "optimizer", "fairness") for i in range(8)]
    balanced = balance_by_query(candidates, ["matching", "optimizer", "fairness"], lambda r: [r.query])
    assert [r.query for r in balanced[:3]] == ["matching", "optimizer", "fairness"]
    assert len({str(r.url) for r in balanced}) == len(candidates)


@pytest.mark.asyncio
async def test_balancing_survives_fetch_failures_and_keeps_discovery_queries(monkeypatch):
    from app.agents import nodes
    from app.tools import search, scraper
    candidates = [SearchResult(title=f"{q} {i}", url=f"https://example.org/{q}/{i}", query=q,
                               source_type="PAPER", content="An indexed abstract with useful limited content. " * 3)
                  for q in ("matching", "optimizer", "fairness") for i in range(8)]
    monkeypatch.setattr(search, "execute_parallel_searches", AsyncMock(return_value=(candidates, [])))
    monkeypatch.setattr(scraper, "fetch_urls_parallel", AsyncMock(return_value={}))
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    state = {"delta_queries": ["matching", "optimizer", "fairness"], "max_sources": 3}
    result = await nodes.researcher_node(state)
    assert {s["query"] for s in result["collected_sources"]} == set(state["delta_queries"])
    assert all(s["discovery_queries"] == [s["query"]] for s in result["collected_sources"])


def test_query_coverage_reports_missing_discovery_queries():
    source = {"discovery_queries": ["matching"], "db_id": "s1"}
    coverage = query_coverage({"plan": {"search_queries": ["matching", "optimizer"]}, "collected_sources": [source]})
    assert coverage["missing_queries"] == ["optimizer"]


@pytest.mark.asyncio
async def test_unfetched_candidates_are_not_marked_as_visited(monkeypatch):
    from app.agents import nodes
    from app.tools import search, scraper
    candidates = [SearchResult(title=f"Paper {i}", url=f"https://example.org/{i}", query="q", doi=f"10.1234/{i}") for i in range(8)]
    monkeypatch.setattr(search, "execute_parallel_searches", AsyncMock(return_value=(candidates, [])))
    async def fetch(urls, **kwargs):
        return {url: "Retrieved text" for url in urls}
    monkeypatch.setattr(scraper, "fetch_urls_parallel", fetch)
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    result = await nodes.researcher_node({"delta_queries": ["q"], "max_sources": 1})
    assert len(result["collected_sources"]) == 1
    assert "doi:10.1234/7" not in result["visited_urls"]


def test_translated_claims_of_the_same_quote_do_not_duplicate_citations():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    claims = [{"claim_id": a, "source_id": "s", "evidence_quote": "one quote"},
              {"claim_id": b, "source_id": "s", "evidence_quote": "one   quote"}]
    assert len(unique_quote_claims(claims)) == 1
    assert canonicalize_quote_markers(f"Finding [[@claim:{a}]], [[@claim:{b}]]", claims).count("[[@claim:") == 1


def test_positive_reviewer_cannot_clear_guarantees_from_abstract_only():
    cid = str(uuid.uuid4())
    text = f"## Discussion\n\nThe hybrid guarantees stability under true preferences [[@claim:{cid}]]."
    claims = [{"claim_id": cid, "evidence_id": "e", "source_id": "s", "chunk_id": "c",
               "text_scope": "ABSTRACT", "evidence_quote": "Random proposal selection balances ex ante opportunities."}]
    p = prepare_evidence_review(text, claims, central_headings=["Discussion"], draft=text, policy_version=2)
    reviews = [EvidenceReview(statement_id=u["statement_id"], judgment="SUPPORTED", reason="Fixture false positive",
                              supporting_claim_ids=[cid], assumptions_preserved=True) for u in p["units"]]
    result = evaluate_evidence_reviews(p, reviews)
    assert result["coverage_complete"] and not result["all_supported"]
    assert result["substantive_findings"]


def test_uncited_optimizer_paragraph_is_included_and_support_ids_are_checked():
    text = "## Optimization\n\nThe optimizer returns globally Pareto-optimal recruitment solutions."
    p = prepare_evidence_review(text, [], central_headings=[], draft=text, policy_version=2)
    assert len(p["units"]) == 1 and p["substantive_findings"]
    review = EvidenceReview(statement_id=p["units"][0]["statement_id"], judgment="SUPPORTED", reason="unsupported fixture",
                            supporting_claim_ids=["invented"], assumptions_preserved=True)
    assert not evaluate_evidence_reviews(p, [review])["coverage_complete"]


def test_search_ledger_preserves_figures_and_is_idempotent():
    state = {"language": "en", "plan": attach_manuscript_contract({}, "REVIEW", "en"), "search_activity": [
        {"provider": "OpenAlex", "query": "optimizer", "status": "SUCCESS", "candidate_count": 8,
         "accepted_count": 2, "completed_at": "2026-10-30T00:00:00Z", "filters": {"per_page": 8}}]}
    draft = "## Literature Search and Scope\n\nAn exploratory narrative search.\n\n[[figure:workflow]]\n\n## Discussion\n\nBounded findings."
    result = inject_search_ledger(draft, state)
    assert "[[figure:workflow]]" in result and "optimizer" in result and "2026-10-30" in result
    assert inject_search_ledger(result, state) == result


def test_historical_contract_is_not_injected_with_a_new_ledger():
    state = {"plan": {"manuscript_contract": {"version": 3}}, "search_activity": [{"query": "q"}]}
    assert inject_search_ledger("Old manuscript", state) == "Old manuscript"


def test_many_short_paragraphs_are_all_reviewed_in_bounded_batches():
    from app.services.research_quality import bounded_quality_batches
    body = "\n\n".join(f"Controlled paragraph number {i}." for i in range(30))
    batches = bounded_quality_batches([("Analysis", body)])
    plans = [prepare_evidence_review(text, [], central_headings=[], draft=body, policy_version=2) for _, text in batches]
    assert sum(len(p["units"]) for p in plans) == 30
    assert all(len(p["units"]) <= 12 and not p["coverage_findings"] for p in plans)


@pytest.mark.asyncio
@pytest.mark.parametrize("verified", [False, True])
async def test_pdf_candidate_requires_a_verified_pdf_response(monkeypatch, verified):
    from app.agents import nodes
    from app.tools import search, scraper
    candidate = SearchResult(title="Paper", url="https://example.org/paper", full_text_url="https://example.org/paper.pdf", source_type="PAPER", query="q")
    content = scraper.ExtractedText("Actual parsed PDF text", "FULL_TEXT") if verified else "An HTML landing page returned by a PDF URL"
    monkeypatch.setattr(search, "execute_parallel_searches", AsyncMock(return_value=([candidate], [])))
    monkeypatch.setattr(scraper, "fetch_urls_parallel", AsyncMock(return_value={str(candidate.full_text_url): content}))
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    result = await nodes.researcher_node({"delta_queries": ["q"], "max_sources": 3})
    assert result["collected_sources"][0]["text_scope"] == ("FULL_TEXT" if verified else "LANDING_PAGE")


def test_negative_guarantee_statement_and_table_header_are_not_strong_assertions():
    from app.services.research_quality import guarantee_risks
    assert not guarantee_risks("The optimizer lacks stability guarantees.")
    assert not guarantee_risks("| Method | Stability Guarantee |")
    assert not guarantee_risks("Integrating these guarantees presents a compelling research direction.")


@pytest.mark.parametrize("locale", ["en", "vi", "fr", "de", "es", "ja", "zh", "ko"])
def test_localized_ledger_keeps_manuscript_language_and_does_not_duplicate(locale):
    from app.services.research_quality import LEDGER_LABELS
    plan = attach_manuscript_contract({}, "REVIEW", locale)
    methods = next(s["heading"] for s in plan["manuscript_contract"]["sections"] if s["id"] == "review_methods")
    state = {"language": locale, "plan": plan, "search_activity": [{"provider": "OpenAlex", "query": "q", "status": "SUCCESS"}]}
    draft = f"## {methods}\n\nRecorded method.\n\n## End\n\nEnd."
    output = inject_search_ledger(draft, state)
    assert LEDGER_LABELS[locale][0] in output
    assert inject_search_ledger(output, state) == output
