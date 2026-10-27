"""Regression coverage for stuck jobs and configuration loss (issue #59)."""
import asyncio
import itertools
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
from sqlalchemy import select, text

from app import worker
from app.agents import graph as graph_module, nodes
from app.core.database import AsyncSessionLocal, engine
from app.models.task import ResearchTask, WorkflowRun
from app.models.report import ResearchReport, ReportVersion
from app.models.user import User
from app.services import task_dispatcher, worker_runtime
from app.services.provider_budget import pause_budget_config
from app.tools.scraper import ScraperTool


async def create_task(**config):
    async with AsyncSessionLocal() as db:
        user = User(username=f"runtime_{uuid.uuid4().hex}", email=f"{uuid.uuid4().hex}@example.com", password_hash="test")
        db.add(user)
        await db.flush()
        task = ResearchTask(user_id=user.id, title="Runtime recovery", research_question="How can research jobs recover?", status="QUEUED", **config)
        db.add(task)
        await db.commit()
        return task.id


def test_sync_jobs_reuse_one_loop_and_database_pool():
    async def query():
        async with AsyncSessionLocal() as db:
            assert await db.scalar(text("SELECT 1")) == 1
        return asyncio.get_running_loop()
    try:
        first = worker_runtime.run_worker_coroutine(query())
        assert worker_runtime.run_worker_coroutine(query()) is first
        assert worker_runtime.run_worker_coroutine(query()) is first
    finally:
        worker_runtime.close_worker_runtime()


def test_sequential_celery_entries_finish_without_cross_loop_connections(monkeypatch):
    monkeypatch.setattr(worker, "research_graph", SimpleNamespace(ainvoke=AsyncMock(return_value={"final_report_markdown": "# Verified", "status": "COMPLETED"})))
    monkeypatch.setattr(task_dispatcher, "dispatch_one_outbox_event", AsyncMock())
    monkeypatch.setattr(worker.execute_research_workflow, "update_state", lambda **_: None)
    try:
        first = worker_runtime.run_worker_coroutine(create_task())
        second = worker_runtime.run_worker_coroutine(create_task())
        assert worker.execute_research_workflow.run(str(first))["status"] == "SUCCESS"
        assert worker.execute_research_workflow.run(str(second))["status"] == "SUCCESS"
        assert worker.execute_research_workflow.run(str(first))["status"] == "IGNORED"
    finally:
        worker_runtime.close_worker_runtime()


@pytest.mark.asyncio
async def test_bootstrap_failure_releases_claim_and_marks_run_failed(monkeypatch):
    task_id = await create_task()
    monkeypatch.setattr(worker, "_ensure_checkpoint_schema", AsyncMock(side_effect=ImportError("missing checkpointer")))
    with pytest.raises(ImportError):
        await worker.run_langgraph_workflow(str(task_id))
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, task_id)
        run = await db.scalar(select(WorkflowRun).where(WorkflowRun.research_task_id == task_id))
        assert task.status == run.status == "FAILED"
        assert task.worker_lease_until is None
        assert (task.budget_config["_provider_usage"])["active_since"] is None


@pytest.mark.asyncio
async def test_worker_recovery_is_bounded(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "WORKER_MAX_RECOVERIES", 1)
    task_id = await create_task()
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, task_id)
        task.status = "RUNNING"
        task.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        task.budget_config = {"_worker_recoveries": 1}
        await db.commit()
    await task_dispatcher.recover_expired_worker_claims()
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, task_id)
        assert task.status == "FAILED"
        assert task.current_step == "RECOVERY_LIMIT"
        assert task.worker_lease_until is None


@pytest.mark.asyncio
async def test_concurrent_checkpoint_initialization_is_serialized(monkeypatch):
    monkeypatch.setattr(worker, "_CHECKPOINT_SCHEMA_READY", False)
    await asyncio.gather(worker._ensure_checkpoint_schema(), worker._ensure_checkpoint_schema())
    assert worker._CHECKPOINT_SCHEMA_READY


@pytest.mark.asyncio
async def test_workflow_deadline_releases_slot(monkeypatch):
    task_id = await create_task()
    async def stalled(state):
        await asyncio.Event().wait()
    monkeypatch.setattr(worker, "research_graph", SimpleNamespace(ainvoke=stalled))
    monkeypatch.setattr("app.services.provider_budget.remaining_active_seconds", AsyncMock(return_value=0.01))
    monkeypatch.setattr(task_dispatcher, "dispatch_one_outbox_event", AsyncMock())
    with pytest.raises(RuntimeError, match="Research workflow failed"):
        await worker.run_langgraph_workflow(str(task_id))
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, task_id)
        assert task.status == "FAILED" and task.worker_lease_until is None


@pytest.mark.asyncio
async def test_retry_keeps_previous_report_version(monkeypatch):
    task_id = await create_task()
    fake_graph = SimpleNamespace(ainvoke=AsyncMock(return_value={"final_report_markdown": "# First", "status": "NEEDS_REVIEW"}))
    monkeypatch.setattr(worker, "research_graph", fake_graph)
    monkeypatch.setattr(task_dispatcher, "dispatch_one_outbox_event", AsyncMock())
    await worker.run_langgraph_workflow(str(task_id))
    async with AsyncSessionLocal() as db:
        task = await db.get(ResearchTask, task_id)
        task.status = "QUEUED"
        await db.commit()
    fake_graph.ainvoke.return_value = {"final_report_markdown": "# Second", "status": "COMPLETED"}
    await worker.run_langgraph_workflow(str(task_id))
    async with AsyncSessionLocal() as db:
        report = await db.scalar(select(ResearchReport).where(ResearchReport.research_task_id == task_id))
        versions = (await db.scalars(select(ReportVersion).where(ReportVersion.report_id == report.id).order_by(ReportVersion.version_number))).all()
        assert [(v.version_number, v.content_markdown) for v in versions] == [(1, "# First"), (2, "# Second")]


@pytest.mark.asyncio
@pytest.mark.parametrize("depth,length,style,approval,language", list(itertools.product(
    ["SHALLOW", "STANDARD", "DEEP"], ["SHORT", "MEDIUM", "LONG"], ["IEEE", "APA", "HARVARD"], [False, True], ["vi", "en"])))
async def test_configuration_matrix_survives_graph_and_approval(monkeypatch, depth, length, style, approval, language):
    config_fields = dict(research_depth=depth, report_length=length, citation_style=style, require_plan_approval=approval,
                         language=language, max_sources=3, enforce_provider_budget=True, dataset_artifact_id="dataset")
    claim_id = str(uuid.uuid4())
    async def supervisor(state):
        assert all(state[k] == v for k, v in config_fields.items())
        return {"plan": {"required_sections": ["Findings"]}, "plan_approved": False}
    async def approve(state):
        interrupt({"kind": "PLAN_APPROVAL"})
        return {"plan_approved": True}
    async def noop(state):
        return {}
    async def analyst(state):
        return {"claims": [{"claim_id": claim_id, "evidence_id": "e1", "source_id": "s1", "chunk_id": "c1", "source_title": "Verified title", "source_url": "https://example.org", "source_tag": "src_01"}]}
    async def critic(state):
        return {"critic_verdict": "PASS"}
    async def invoke(state, llm, messages, **kwargs):
        assert {"SHORT": 4096, "MEDIUM": 8192, "LONG": 12288}[length] == kwargs["output_tokens"]
        assert length in messages[0].content and style in messages[0].content
        return SimpleNamespace(content=f"# Findings\nSupported [[@claim:{claim_id}]].")
    for name, fn in {"supervisor_node": supervisor, "plan_approval_wait_node": approve, "researcher_node": noop,
                     "curator_node": noop, "analyst_node": analyst, "critic_node": critic}.items():
        monkeypatch.setattr(graph_module, name, fn)
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_smart_llm", lambda: object())
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fake")
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", invoke)
    graph = graph_module.build_research_graph(InMemorySaver())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = await graph.ainvoke({**config_fields, "research_type": "REVIEW"}, config=config)
    if approval:
        assert result["__interrupt__"]
        result = await graph.ainvoke(Command(resume={"approved": True}), config=config)
    assert result["status"] == "COMPLETED"
    assert result["citations"][0]["citation_label"] == ("[1]" if style == "IEEE" else "(Verified title, n.d.)")
    assert "## References" in result["final_report_markdown"]


@pytest.mark.asyncio
async def test_https_sni_is_text_and_private_redirect_is_never_requested(monkeypatch):
    scraper = ScraperTool()
    monkeypatch.setattr(scraper, "_resolve_ips", AsyncMock(return_value={"93.184.216.34"}))
    pinned, host, extensions = await scraper._validated_target("https://example.org/start")
    assert extensions == {"sni_hostname": "example.org"}
    calls = []
    def respond(request):
        calls.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/next"})
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
    original_client = httpx.AsyncClient
    monkeypatch.setattr("app.tools.scraper.httpx.AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs))
    assert await scraper.fetch_and_extract("https://example.org/start") is None
    assert calls == ["https://93.184.216.34/start", "https://93.184.216.34/next"]


def test_idle_time_after_completion_does_not_consume_retry_budget():
    start = datetime.now(timezone.utc) - timedelta(hours=10)
    frozen = pause_budget_config({"_provider_usage": {"active_since": start.isoformat(), "active_seconds": 10}}, now=start + timedelta(seconds=30))
    assert frozen["_provider_usage"]["active_seconds"] == 40
    assert frozen["_provider_usage"]["active_since"] is None


@pytest.mark.asyncio
async def test_source_limit_is_enforced_across_iterations(monkeypatch):
    from app.tools.search import SearchResult
    fake_search = AsyncMock(return_value=[SearchResult(title=f"Source {i}", url=f"https://example.org/{i}", content="excerpt") for i in range(6)])
    async def fetch(urls, **_):
        return {url: "Verified page content" for url in urls}
    monkeypatch.setattr("app.tools.search.execute_parallel_searches", fake_search)
    monkeypatch.setattr("app.tools.scraper.fetch_urls_parallel", fetch)
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    existing = [{"source_tag": "src_01"}, {"source_tag": "src_02"}]
    result = await nodes.researcher_node({"max_sources": 3, "collected_sources": existing, "delta_queries": ["query"]})
    assert len(result["collected_sources"]) == 1
    assert result["collected_sources"][0]["source_tag"] == "src_03"
    fake_search.reset_mock()
    await nodes.researcher_node({"max_sources": 3, "collected_sources": existing + result["collected_sources"], "delta_queries": ["query"]})
    fake_search.assert_not_awaited()


@pytest.mark.asyncio
async def test_unresponsive_provider_is_bounded(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "PROVIDER_CALL_TIMEOUT_SECONDS", 0.01)
    async def stalled(*args, **kwargs):
        await asyncio.Event().wait()
    llm = nodes.BudgetedFallbackLLM([("unresponsive", SimpleNamespace(ainvoke=stalled))])
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(llm.ainvoke([]), timeout=1)


@pytest.mark.asyncio
async def test_truncated_writer_output_cannot_pass_even_when_model_says_pass(monkeypatch):
    fake_llm = SimpleNamespace(with_structured_output=lambda _: object())
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    monkeypatch.setattr(nodes, "get_fast_llm", lambda: fake_llm)
    monkeypatch.setattr(nodes, "get_smart_llm", lambda: fake_llm)
    monkeypatch.setattr(nodes, "get_active_model_name", lambda **_: "fake")
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", AsyncMock(return_value=SimpleNamespace(
        content="# Introduction\nPartial [[@claim:unfinished", response_metadata={"finish_reason": "MAX_TOKENS"})))
    written = await nodes.writer_node({"report_length": "SHORT"})
    assert written["draft_truncated"]
    monkeypatch.setattr(nodes, "invoke_llm_with_budget", AsyncMock(return_value=nodes.CriticVerdict(verdict="PASS")))
    reviewed = await nodes.critic_node(written)
    assert reviewed["critic_verdict"] == "REVISE"
    delivered = await nodes.post_processor_node({**written, "critic_verdict": "PASS"})
    assert delivered["status"] == "NEEDS_REVIEW"
    assert "[[@claim:" not in delivered["final_report_markdown"]


@pytest.mark.asyncio
async def test_report_without_any_grounded_citations_needs_review(monkeypatch):
    monkeypatch.setattr(nodes, "_record_progress", AsyncMock())
    monkeypatch.setattr(nodes, "record_agent_run", AsyncMock())
    result = await nodes.post_processor_node({"draft_report_markdown": "Unsupported draft", "critic_verdict": "PASS", "enforce_provider_budget": True})
    assert result["status"] == "NEEDS_REVIEW"
    assert result["critic_review_metadata"]["status"] == "NEEDS_REVIEW"
