import uuid
import unicodedata
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from app.agents import graph as graph_module, nodes
from app.services.manuscript import (
    attach_manuscript_contract, manuscript_contract, manuscript_provenance, validate_manuscript,
)
from tests.manuscript_helpers import complete_manuscript


@pytest.mark.parametrize("research_type", ["REVIEW", "EMPIRICAL_HUMAN", "EMPIRICAL_COMPUTATIONAL"])
@pytest.mark.parametrize("language", ["vi", "en", "fr", "de", "es", "ja", "zh", "ko"])
def test_each_supported_article_type_has_a_valid_localized_structure(research_type, language):
    contract = manuscript_contract(research_type, language)
    assert not validate_manuscript(complete_manuscript("Evidence-backed finding.", research_type, language), contract)
    ids = [item["id"] for item in contract["sections"]]
    assert {"abstract", "keywords", "discussion", "limitations"} <= set(ids)
    assert ("results" in ids) == (research_type != "REVIEW")
    assert ("setup" in ids) == (research_type == "EMPIRICAL_COMPUTATIONAL")


def test_missing_sections_and_list_dominated_body_are_actionable():
    contract = manuscript_contract("REVIEW", "en")
    findings = validate_manuscript("# Topic\n\n## Introduction\n- Point one supplies evidence and interpretation.\n- Point two supplies evidence and interpretation.\n- Point three supplies evidence and interpretation.", contract)
    assert {f["code"] for f in findings} >= {"MISSING_SECTION", "LIST_DOMINATED"}
    assert any("Abstract" in f["message"] for f in findings)


def test_a_list_dominated_discussion_is_rejected_even_in_a_long_prose_article():
    manuscript = complete_manuscript("Evidence grounded in the source. " * 100, language="en")
    manuscript = manuscript.replace("## Discussion\n\n", "## Discussion\n\n1. One approach provides the theoretical basis and evidence for this inference.\n2. Another approach provides a different computational mechanism for the same problem.\n3. Their combination is proposed without an empirical test of the integrated design.\n\n")
    findings = validate_manuscript(manuscript, manuscript_contract("REVIEW", "en"))
    assert any(f["code"] == "ANALYTICAL_PROSE" for f in findings)


@pytest.mark.parametrize("claim", [
    "We conducted a systematic review following PRISMA.",
    "Unlike prior work, we conducted a systematic review following PRISMA.",
    "Nghiên cứu này áp dụng tổng quan tài liệu hệ thống theo chuẩn PRISMA.",
    "We searched PubMed and IEEE Xplore databases for all eligible studies.",
])
def test_unexecuted_methods_are_rejected(claim):
    contract = manuscript_contract("REVIEW", "en")
    manuscript = complete_manuscript("A sourced finding.", language="en")
    manuscript = manuscript.replace("## Literature Search and Scope\n\n", f"## Literature Search and Scope\n\n{claim}\n\n")
    assert any(f["code"].startswith("UNSUPPORTED_") for f in validate_manuscript(manuscript, contract))


@pytest.mark.parametrize("statement", [
    "This is a non-systematic literature review with a limited source set.",
    "We did not conduct a systematic review or claim PRISMA compliance.",
    "We discuss PRISMA as a reporting guideline in the cited literature.",
    "We discuss a prior systematic review that followed PRISMA to motivate this narrative approach.",
    "We used Tavily web search to find publicly accessible IEEE Xplore pages.",
])
def test_limited_scope_and_discussion_of_prior_methods_are_not_false_claims(statement):
    manuscript = complete_manuscript(statement, language="en")
    manuscript = manuscript.replace("## Literature Search and Scope\n\n", f"## Literature Search and Scope\n\n{statement}\n\n")
    assert not validate_manuscript(manuscript, manuscript_contract("REVIEW", "en"))


def test_planned_searches_never_become_executed_provenance():
    state = {"current_queries": ["unexecuted query"], "collected_sources": [{"source_type": "PDF"}]}
    provenance = manuscript_provenance(state)
    assert provenance["uploaded_pdf_count"] == 1
    assert provenance["search_activity_this_run"] == []
    assert provenance["direct_academic_database_search"] is False


def test_unicode_normalization_does_not_reject_localized_headings():
    manuscript = complete_manuscript("A supported finding.", language="vi")
    assert not validate_manuscript(unicodedata.normalize("NFD", manuscript), manuscript_contract("REVIEW", "vi"))


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["vi", "en", "fr", "ja"])
async def test_generated_bibliography_replaces_model_authored_localized_references(monkeypatch, language):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    plan = attach_manuscript_contract({}, "REVIEW", language)
    heading = plan["manuscript_contract"]["references_heading"]
    claim_id = str(uuid.uuid4())
    draft = complete_manuscript(f"A supported claim [[@claim:{claim_id}]].", language=language)
    result = await nodes.post_processor_node({"plan": plan, "draft_report_markdown": draft + f"\n\n## 9. {heading}\n\nInvented reference", "claims": [{"claim_id": claim_id, "evidence_id": "e", "source_tag": "src_01", "source_title": "Verified source"}]})
    assert "Invented reference" not in result["final_report_markdown"]
    assert result["final_report_markdown"].count(f"## {heading}") == 1


@pytest.mark.asyncio
async def test_clustered_citations_preserve_all_supported_claims_and_trailing_prose(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    claims = [{"claim_id": cid, "evidence_id": f"e{index}", "source_id": f"s{index}", "chunk_id": f"c{index}", "source_title": f"Source {index}", "source_tag": f"src_0{index}"} for index, cid in enumerate((first, second), 1)]
    draft = f"Supported conclusion [[@claim:{first}], [@claim:{second}]]. The following interpretation must remain."
    assert not nodes._claim_lineage_findings(draft, claims)
    result = await nodes.post_processor_node({"draft_report_markdown": draft, "claims": claims, "critic_verdict": "PASS"})
    assert "Supported conclusion [1], [2]. The following interpretation must remain." in result["final_report_markdown"]
    assert len(result["citations"]) == 2


@pytest.mark.asyncio
async def test_dangling_citation_never_passes_delivery_or_silently_deletes_following_text(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    draft = "A statement [[@claim:bad-id]]. This sentence must remain.\nAnother [[@claim:unfinished"
    result = await nodes.post_processor_node({"draft_report_markdown": draft, "critic_verdict": "PASS"})
    assert result["status"] == "NEEDS_REVIEW"
    assert "This sentence must remain." in result["final_report_markdown"]
    assert result["citation_validation"]["unresolved_markers"] > 0


@pytest.mark.asyncio
async def test_critic_and_final_delivery_cannot_pass_a_bad_manuscript(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fake")
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: SimpleNamespace(with_structured_output=lambda _: object()))
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", AsyncMock(return_value=nodes.CriticVerdict(verdict="PASS")))
    claim_id = str(uuid.uuid4())
    state = {"plan": attach_manuscript_contract({}, "REVIEW", "en"),
             "draft_report_markdown": f"# Topic\n\n## Introduction\nSupported statement [[@claim:{claim_id}]].",
             "claims": [{"claim_id": claim_id, "evidence_id": "e", "source_id": "s", "chunk_id": "c", "source_tag": "src_01", "source_title": "Source"}]}
    review = await nodes.critic_node(state)
    assert review["critic_verdict"] == "REVISE"
    assert review["critic_review_metadata"]["manuscript_findings"]
    delivered = await nodes.post_processor_node({**state, "critic_verdict": "PASS"})
    assert delivered["status"] == "NEEDS_REVIEW"
    assert delivered["critic_review_metadata"]["status"] == "NEEDS_REVIEW"
    exhausted = await nodes.critic_node({**state, "current_micro_revision": 2})
    assert exhausted["critic_verdict"] == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_editorial_revision_and_contract_survive_graph_interrupt(monkeypatch):
    claim_id = str(uuid.uuid4())
    plan = attach_manuscript_contract({"search_queries": ["matching theory"]}, "REVIEW", "en")
    async def supervisor(state):
        return {"plan": plan}
    async def approval(state):
        interrupt({"kind": "PLAN_APPROVAL"})
        return {"plan_approved": True}
    async def noop(state):
        return {}
    async def analyst(state):
        return {"claims": [{"claim_id": claim_id, "evidence_id": "e", "source_id": "s", "chunk_id": "c", "source_tag": "src_01", "source_title": "Source"}]}
    writes = []
    async def invoke(state, llm, messages, **kwargs):
        if "internal report quality-control" in messages[0].content:
            return nodes.CriticVerdict(verdict="PASS")
        assert "ACTUAL PROVENANCE" in messages[0].content
        assert state["plan"]["manuscript_contract"]["article_type"] == "NARRATIVE_REVIEW"
        writes.append(1)
        content = f"A finding [[@claim:{claim_id}]]."
        return SimpleNamespace(content=complete_manuscript(content, language="en") if len(writes) > 1 else content)
    for name, fn in {"supervisor_node": supervisor, "plan_approval_wait_node": approval, "researcher_node": noop, "curator_node": noop, "analyst_node": analyst}.items():
        monkeypatch.setattr(graph_module, name, fn)
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: SimpleNamespace(with_structured_output=lambda _: object()))
    monkeypatch.setattr(nodes, "get_smart_llm", lambda: object())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fake")
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", invoke)
    graph = graph_module.build_research_graph(InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    paused = await graph.ainvoke({"require_plan_approval": True, "research_type": "REVIEW", "language": "en"}, config=config)
    assert paused["__interrupt__"]
    result = await graph.ainvoke(Command(resume=True), config=config)
    assert result["status"] == "COMPLETED"
    assert len(writes) == 2
    assert result["critic_review_metadata"]["manuscript_findings"] == []
    assert "## References" in result["final_report_markdown"]


@pytest.mark.asyncio
async def test_auto_approved_run_persists_its_plan_and_contract(monkeypatch):
    from sqlalchemy import select
    from app import worker
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.task import ResearchTask, WorkflowRun
    from app.models.report import ReportVersion, ResearchReport
    from app.services import task_dispatcher
    plan = attach_manuscript_contract({"search_queries": ["matching theory"]}, "REVIEW", "en")
    monkeypatch.setattr(worker, "research_graph", SimpleNamespace(ainvoke=AsyncMock(return_value={
        "plan": plan, "plan_version": 1, "status": "COMPLETED", "final_report_markdown": complete_manuscript("A finding.", language="en")
    })))
    monkeypatch.setattr(task_dispatcher, "dispatch_one_outbox_event", AsyncMock())
    async with AsyncSessionLocal() as db:
        user = User(username=f"contract_{uuid.uuid4().hex}", email=f"{uuid.uuid4().hex}@example.com", password_hash="synthetic")
        db.add(user); await db.flush()
        task = ResearchTask(user_id=user.id, title="Contract persistence", research_question="How are manuscript conventions persisted?", status="QUEUED")
        db.add(task); await db.commit(); tid = task.id
    await worker.run_langgraph_workflow(str(tid))
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, tid)
        run = await db.scalar(select(WorkflowRun).where(WorkflowRun.research_task_id == tid))
        version = await db.scalar(select(ReportVersion).join(ResearchReport).where(ResearchReport.research_task_id == tid))
        assert task.plan["manuscript_contract"] == plan["manuscript_contract"]
        assert task.plan_version == run.plan_version == version.plan_version == 1
        assert version.title == "Evidence-grounded research manuscript"
