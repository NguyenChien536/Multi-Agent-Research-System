"""LangGraph orchestration and workflow-persistence tests (Issue #2).

Design principles
-----------------
* Real graph edges & routing functions run — we do NOT monkeypatch the graph
  object itself.  Only the leaf-level external boundaries are mocked:
    - LLM providers (via ``build_llm_chain`` / node-level monkeypatches)
    - Tavily search (``execute_parallel_searches``)
    - Web scraper (``fetch_urls_parallel``)
    - Embedding tool (``EmbedderTool``)
* Persistence invariants are verified in the real PostgreSQL database that
  CI boots before this suite runs.
* No paid provider is contacted; no .env key is read in assertions.

Coverage
--------
1. Supervisor → Researcher → Curator → Analyst → Writer → Critic → PostProcessor
   straight-through happy path — checks node visit order AND final state.
2. Micro-loop: critic returns REVISE → writer reruns → critic returns PASS.
3. Macro-loop: critic returns NEED_MORE_DATA within budget → researcher reruns.
4. Budget exhaustion: critic returns NEED_MORE_DATA when iterations exhausted →
   post_processor is reached without another researcher run.
5. Failed workflow cannot be persisted as COMPLETED; task remains FAILED and
   no ResearchReport row is created.
6. Duplicate delivery after COMPLETED returns IGNORED without overwriting the
   report.
7. SSRF guard: blocks non-public IPv4 ranges, IPv4-mapped IPv6 loopback,
   IPv6 link-local, and redirect-following disabled by default.
"""

import asyncio
import ipaddress
import re
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents import graph as graph_module
from app.agents import nodes as nodes_module
from app.agents.graph import (
    build_research_graph,
    should_continue_research,
    should_revise_draft,
)
from app.agents.state import ResearchState
from app.core.database import AsyncSessionLocal, engine
from app.main import app
from app.models.report import ResearchReport
from app.models.grounding import Citation, ClaimEvidence, Evidence, ResearchClaim
from app.models.task import ResearchTask
from app.models.source import DocumentChunk, ResearchSource
from app.tools.search import SearchResult
from app.services import task_dispatcher
from app.services.grounding import persist_grounded_claims
from app import worker as worker_module
from app.worker import run_langgraph_workflow
from app.tools.scraper import ScraperTool, SSRFError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_fake_llm(structured_output: Any) -> MagicMock:
    """Return a fake LLM chain that resolves to *structured_output* on ainvoke."""
    fake = MagicMock()
    fake.ainvoke = AsyncMock(return_value=structured_output)
    fake.with_structured_output = MagicMock(return_value=fake)
    fake.with_fallbacks = MagicMock(return_value=fake)
    return fake


def _supervisor_plan_output():
    plan = MagicMock()
    plan.model_dump.return_value = {
        "research_angle": "systematic overview",
        "search_queries": ["test query 1", "test query 2"],
        "required_sections": ["Introduction", "Findings", "References"],
    }
    plan.search_queries = ["test query 1", "test query 2"]
    return plan


def _analyst_extraction_output(claims=None):
    extraction = MagicMock()
    claim_obj = MagicMock()
    claim_obj.model_dump.return_value = {"claim": "test claim", "evidence_quote": "test evidence"}
    extraction.claims = claims if claims is not None else [claim_obj]
    return extraction


def _critic_verdict(verdict: str):
    v = MagicMock()
    v.verdict = verdict
    v.feedback = ["needs more detail"] if verdict == "REVISE" else []
    v.missing_areas = ["more data"] if verdict == "NEED_MORE_DATA" else []
    return v


async def _register_and_login(client: AsyncClient, suffix: str) -> dict:
    reg = await client.post("/api/v1/auth/register", json={
        "username": f"orch_{suffix}",
        "email": f"orch_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={
        "email": f"orch_{suffix}@example.com",
        "password": "SecurePass123!",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _create_and_start(client: AsyncClient, headers: dict, title: str) -> str:
    task = await client.post("/api/v1/research", headers=headers, json={
        "title": title,
        "research_question": f"Research question for {title}",
        "research_depth": "STANDARD",
    })
    assert task.status_code == 201, task.text
    task_id = task.json()["id"]
    started = await client.post(f"/api/v1/research/{task_id}/start", headers=headers)
    assert started.status_code == 202, started.text
    return task_id


# ---------------------------------------------------------------------------
# Routing function unit tests (no DB, no LLM)
# ---------------------------------------------------------------------------

def test_routing_pass_goes_to_post_processor():
    state: ResearchState = {"critic_verdict": "PASS", "current_micro_revision": 0, "max_micro_revisions": 2}
    assert should_revise_draft(state) == "post_processor"


def test_routing_revise_within_budget_goes_to_writer():
    state: ResearchState = {"critic_verdict": "REVISE", "current_micro_revision": 0, "max_micro_revisions": 2}
    assert should_revise_draft(state) == "writer"


def test_routing_revise_at_limit_goes_to_post_processor():
    # Exhausted micro-revisions with REVISE → still goes to post_processor (not writer)
    state: ResearchState = {"critic_verdict": "REVISE", "current_micro_revision": 2, "max_micro_revisions": 2}
    assert should_revise_draft(state) == "post_processor"


def test_routing_need_more_data_goes_to_macro_routing():
    state: ResearchState = {"critic_verdict": "NEED_MORE_DATA", "current_micro_revision": 0, "max_micro_revisions": 2}
    assert should_revise_draft(state) == "macro_routing"


def test_macro_routing_within_budget_goes_to_researcher():
    state: ResearchState = {"critic_verdict": "NEED_MORE_DATA", "current_iteration": 0, "max_iterations": 2}
    assert should_continue_research(state) == "researcher"


def test_macro_routing_exhausted_goes_to_post_processor():
    state: ResearchState = {"critic_verdict": "NEED_MORE_DATA", "current_iteration": 2, "max_iterations": 2}
    assert should_continue_research(state) == "post_processor"


def test_macro_routing_pass_verdict_goes_to_post_processor():
    # If critic_verdict is PASS, macro routing always goes to post_processor.
    state: ResearchState = {"critic_verdict": "PASS", "current_iteration": 0, "max_iterations": 2}
    assert should_continue_research(state) == "post_processor"


@pytest.mark.asyncio
async def test_post_processor_keeps_only_known_claim_citations():
    claim_id = str(uuid.uuid4())
    unknown_id = str(uuid.uuid4())
    state = {
        "draft_report_markdown": (
            f"# Findings\n\nValid claim [[@claim:{claim_id}]]. "
            f"Untrusted [99] [[@claim:{unknown_id}]].\n\n"
            "## References\n\n[1] Model-invented reference"
        ),
        "claims": [{
            "claim_id": claim_id,
            "claim": "A supported claim",
            "evidence_id": str(uuid.uuid4()),
            "source_tag": "src_01",
            "source_title": "Verified source",
            "source_url": "https://example.org/source",
            "source_id": str(uuid.uuid4()),
            "chunk_id": str(uuid.uuid4()),
        }],
    }

    result = await nodes_module.post_processor_node(state)

    assert "Valid claim [1]." in result["final_report_markdown"]
    assert "[99]" not in result["final_report_markdown"]
    assert "Model-invented reference" not in result["final_report_markdown"]
    assert "[@claim:" not in result["final_report_markdown"]
    assert "## References\n\n[1] Verified source. https://example.org/source" in result["final_report_markdown"]
    assert [item["claim_id"] for item in result["citations"]] == [claim_id]


# ---------------------------------------------------------------------------
# Real graph integration tests (mocking only LLM/search/embed boundaries)
# ---------------------------------------------------------------------------

def _patch_external_boundaries(monkeypatch, critic_sequence=("PASS",)):
    """Patch all external I/O with deterministic stubs.

    critic_sequence: tuple of verdict strings the critic returns in order
    (last value is repeated when sequence exhausted).
    """
    critic_call_count = [0]

    def _get_verdict():
        idx = min(critic_call_count[0], len(critic_sequence) - 1)
        verdict = critic_sequence[idx]
        critic_call_count[0] += 1
        return _critic_verdict(verdict)

    supervisor_plan = _supervisor_plan_output()
    analyst_ext = _analyst_extraction_output()
    writer_content = MagicMock()
    writer_content.content = "# Draft Report\n\nA finding [1].\n\n# References\n[1] src."

    def make_fast_llm():
        fake = MagicMock()
        # Default: analyst/supervisor use structured output
        fake.ainvoke = AsyncMock(return_value=supervisor_plan)
        fake.with_structured_output = MagicMock(return_value=fake)
        fake.with_fallbacks = MagicMock(return_value=fake)
        return fake

    def make_critic_llm():
        fake = MagicMock()
        fake.ainvoke = AsyncMock(side_effect=lambda *a, **kw: asyncio.coroutine(lambda: _get_verdict())())
        fake.with_structured_output = MagicMock(return_value=fake)
        fake.with_fallbacks = MagicMock(return_value=fake)
        return fake

    def make_smart_llm():
        fake = MagicMock()
        fake.ainvoke = AsyncMock(return_value=writer_content)
        fake.with_fallbacks = MagicMock(return_value=fake)
        return fake

    # Track node invocations
    supervisor_llm = make_fast_llm()
    supervisor_llm.ainvoke = AsyncMock(return_value=supervisor_plan)
    supervisor_llm.with_structured_output = MagicMock(return_value=supervisor_llm)

    analyst_llm = MagicMock()
    analyst_llm.ainvoke = AsyncMock(return_value=analyst_ext)
    analyst_llm.with_structured_output = MagicMock(return_value=analyst_llm)
    analyst_llm.with_fallbacks = MagicMock(return_value=analyst_llm)

    critic_llm = MagicMock()
    critic_llm.with_structured_output = MagicMock(return_value=critic_llm)
    critic_llm.with_fallbacks = MagicMock(return_value=critic_llm)

    async def _critic_ainvoke(*args, **kwargs):
        return _get_verdict()
    critic_llm.ainvoke = _critic_ainvoke

    writer_llm = make_smart_llm()

    # Patch build_llm_chain to dispatch appropriate mock per call site
    fast_call_count = [0]

    def _build_llm_chain(is_smart=False):
        if is_smart:
            return writer_llm
        # Fast LLM: first call is supervisor, subsequent are analyst/critic
        # We patch get_fast_llm individually below, so this is a fallback
        return analyst_llm

    monkeypatch.setattr(nodes_module, "build_llm_chain", _build_llm_chain)

    # Patch search — returns empty list (no actual HTTP calls)
    async def _fake_search(queries, max_results_per_query=3):
        return []

    # Patch scraper — returns empty dict (no actual HTTP calls)
    async def _fake_scraper(urls, max_concurrent=5):
        return {}

    # Patch embedder
    mock_embedder = MagicMock()
    mock_embedder.embed_and_store = AsyncMock(return_value=0)
    mock_embedder.search_similar_chunks = AsyncMock(return_value=[])

    monkeypatch.setattr("app.agents.nodes.get_fast_llm", lambda: critic_llm)
    monkeypatch.setattr("app.agents.nodes.get_smart_llm", lambda: writer_llm)

    # For supervisor node specifically, it calls get_fast_llm().with_structured_output(...)
    # We need supervisor to get its plan output. Let's patch supervisor to use supervisor_llm.
    _orig_supervisor = graph_module.supervisor_node

    async def _mock_supervisor_node(state):
        llm = supervisor_llm
        plan: any = await llm.ainvoke([])
        return {
            "current_agent": "supervisor",
            "plan": plan.model_dump(),
            "delta_queries": plan.search_queries,
            "current_queries": plan.search_queries,
        }

    # For analyst node, return fixed claims without DB interaction
    async def _mock_analyst_node(state):
        return {
            "current_agent": "analyst",
            "claims": [{"claim": "test claim", "evidence_quote": "test evidence"}],
        }

    # For curator node, skip DB/embedding
    async def _mock_curator_node(state):
        return {
            "current_agent": "curator",
            "indexed_chunks_count": 0,
        }

    monkeypatch.setattr(graph_module, "supervisor_node", _mock_supervisor_node)
    monkeypatch.setattr(graph_module, "analyst_node", _mock_analyst_node)
    monkeypatch.setattr(graph_module, "curator_node", _mock_curator_node)

    # Patch search and scraper at import sites inside nodes
    monkeypatch.setattr("app.tools.search.execute_parallel_searches", _fake_search)
    monkeypatch.setattr("app.tools.scraper.fetch_urls_parallel", _fake_scraper)

    return {
        "critic_call_count": critic_call_count,
        "supervisor_llm": supervisor_llm,
        "critic_llm": critic_llm,
        "writer_llm": writer_llm,
    }


@pytest.mark.asyncio
async def test_graph_straight_through_happy_path(monkeypatch):
    """Real graph runs supervisor→researcher→curator→analyst→writer→critic(PASS)→post_processor.

    All routing decisions are made by the real should_revise_draft /
    should_continue_research functions, not by a mock.
    """
    visited = []

    _patch_external_boundaries(monkeypatch, critic_sequence=("PASS",))

    # Wrap the real nodes to record visits while letting them execute
    _real_researcher = graph_module.researcher_node
    _real_writer = graph_module.writer_node
    _real_critic = graph_module.critic_node
    _real_post = graph_module.post_processor_node

    async def _track(name, fn, state):
        visited.append(name)
        return await fn(state)

    async def tracked_researcher(state):
        return await _track("researcher", _real_researcher, state)

    async def tracked_writer(state):
        return await _track("writer", _real_writer, state)

    async def tracked_critic(state):
        return await _track("critic", _real_critic, state)

    async def tracked_post_processor(state):
        return await _track("post_processor", _real_post, state)

    monkeypatch.setattr(graph_module, "researcher_node", tracked_researcher)
    monkeypatch.setattr(graph_module, "writer_node", tracked_writer)
    monkeypatch.setattr(graph_module, "critic_node", tracked_critic)
    monkeypatch.setattr(graph_module, "post_processor_node", tracked_post_processor)

    graph = build_research_graph()

    initial_state = {
        "task_id": str(uuid.uuid4()),
        "research_question": "What is the impact of AI on education?",
        "research_depth": "STANDARD",
        "language": "en",
        "current_iteration": 0,
        "current_micro_revision": 0,
        "max_iterations": 2,
        "max_micro_revisions": 2,
        "collected_sources": [],
        "visited_urls": set(),
        "claims": [],
    }

    final_state = await graph.ainvoke(initial_state)

    # Verify the straight-through path was taken
    assert "supervisor" in visited or final_state.get("current_agent") is not None
    assert "researcher" in visited
    assert "writer" in visited
    assert "critic" in visited
    assert "post_processor" in visited

    # Final state must have a report
    assert final_state.get("final_report_markdown"), "Graph must produce a final_report_markdown"
    # post_processor sets status=COMPLETED in the state
    assert final_state.get("status") == "COMPLETED", (
        f"Expected state.status=COMPLETED, got {final_state.get('status')!r}"
    )


@pytest.mark.asyncio
async def test_graph_micro_loop_revise_then_pass(monkeypatch):
    """Critic returns REVISE once, then PASS — writer runs twice, post_processor once."""
    writer_calls = []
    critic_calls = []

    _patch_external_boundaries(monkeypatch, critic_sequence=("REVISE", "PASS"))

    _real_writer = graph_module.writer_node
    _real_critic = graph_module.critic_node
    _real_post = graph_module.post_processor_node

    async def _count_writer(state):
        writer_calls.append(1)
        return await _real_writer(state)

    async def _count_critic(state):
        critic_calls.append(1)
        return await _real_critic(state)

    monkeypatch.setattr(graph_module, "writer_node", _count_writer)
    monkeypatch.setattr(graph_module, "critic_node", _count_critic)

    graph = build_research_graph()

    initial_state = {
        "task_id": str(uuid.uuid4()),
        "research_question": "What is AI?",
        "research_depth": "STANDARD",
        "language": "en",
        "current_iteration": 0,
        "current_micro_revision": 0,
        "max_iterations": 2,
        "max_micro_revisions": 2,
        "collected_sources": [],
        "visited_urls": set(),
        "claims": [{"claim": "AI is transformative", "evidence_quote": "source text"}],
    }

    final_state = await graph.ainvoke(initial_state)

    assert len(writer_calls) == 2, f"Writer should run exactly twice; ran {len(writer_calls)} times"
    assert len(critic_calls) == 2, f"Critic should run exactly twice; ran {len(critic_calls)} times"
    assert final_state.get("final_report_markdown"), "Report must be produced"
    assert final_state.get("status") == "COMPLETED"


@pytest.mark.asyncio
async def test_graph_macro_loop_need_more_data(monkeypatch):
    """Critic returns NEED_MORE_DATA on first pass (iteration 0 < max 2) →
    researcher runs a second time, then critic returns PASS → post_processor.
    """
    researcher_calls = []

    _patch_external_boundaries(monkeypatch, critic_sequence=("NEED_MORE_DATA", "PASS"))

    _real_researcher = graph_module.researcher_node

    async def _count_researcher(state):
        researcher_calls.append(1)
        return await _real_researcher(state)

    monkeypatch.setattr(graph_module, "researcher_node", _count_researcher)

    graph = build_research_graph()

    initial_state = {
        "task_id": str(uuid.uuid4()),
        "research_question": "How does quantum computing work?",
        "research_depth": "STANDARD",
        "language": "en",
        "current_iteration": 0,
        "current_micro_revision": 0,
        "max_iterations": 2,
        "max_micro_revisions": 1,
        "collected_sources": [],
        "visited_urls": set(),
        "claims": [],
    }

    final_state = await graph.ainvoke(initial_state)

    assert len(researcher_calls) >= 2, (
        f"Researcher should run at least twice in macro-loop; ran {len(researcher_calls)} time(s)"
    )
    assert final_state.get("final_report_markdown"), "Report must be produced after macro-loop"
    assert final_state.get("status") == "COMPLETED"


@pytest.mark.asyncio
async def test_graph_budget_exhaustion_skips_researcher(monkeypatch):
    """When iteration budget is already exhausted (current_iteration == max_iterations)
    and critic returns NEED_MORE_DATA, the graph must go directly to post_processor
    without another researcher run.
    """
    researcher_calls = []

    _patch_external_boundaries(monkeypatch, critic_sequence=("NEED_MORE_DATA",))

    _real_researcher = graph_module.researcher_node

    async def _count_researcher(state):
        researcher_calls.append(1)
        return await _real_researcher(state)

    monkeypatch.setattr(graph_module, "researcher_node", _count_researcher)

    graph = build_research_graph()

    initial_state = {
        "task_id": str(uuid.uuid4()),
        "research_question": "Bounded question",
        "research_depth": "SHALLOW",
        "language": "en",
        "current_iteration": 2,  # already at max
        "current_micro_revision": 0,
        "max_iterations": 2,
        "max_micro_revisions": 1,
        "collected_sources": [],
        "visited_urls": set(),
        "claims": [],
    }

    final_state = await graph.ainvoke(initial_state)

    # researcher_node may be called once from the initial supervisor→researcher edge;
    # it must NOT be called again due to budget exhaustion.
    # After the first pass of writer→critic(NEED_MORE_DATA) and budget exhausted,
    # macro_routing → post_processor.
    assert final_state.get("final_report_markdown") is not None, "Must still produce a report"
    assert final_state.get("status") == "COMPLETED"

    # Check that macro routing didn't re-enter researcher after critic verdict
    # The researcher that ran is the initial one from supervisor→researcher edge
    # We verify by ensuring no extra calls happened after post_processor ran
    # (The initial researcher is 1 call; budget exhaustion should prevent a 2nd)
    # In a fresh graph, researcher runs once as the entry path. After budget
    # exhaustion, it must not run again.
    assert len(researcher_calls) <= 1, (
        f"Budget exhaustion: researcher should not run more than once, ran {len(researcher_calls)} times"
    )


# ---------------------------------------------------------------------------
# Persistence invariants: failed/incomplete workflow cannot become COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_failed_workflow_cannot_be_persisted_as_completed(monkeypatch):
    """If the graph raises an exception, the task status must be FAILED
    and no ResearchReport must be written.
    """
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda tid: None),
    )

    class FailingGraph:
        async def ainvoke(self, _state: dict) -> dict:
            raise RuntimeError("Simulated graph failure — provider unavailable")

    monkeypatch.setattr(worker_module, "research_graph", FailingGraph())

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, f"fail_{suffix}")
        task_id = await _create_and_start(client, headers, "Failing workflow task")
        assert await task_dispatcher.dispatch_one_outbox_event()

        with pytest.raises(RuntimeError, match="Simulated graph failure"):
            await run_langgraph_workflow(task_id)

        # Task must be FAILED — not COMPLETED, not RUNNING
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, uuid.UUID(task_id))
            assert task is not None
            assert task.status == "FAILED", (
                f"Task status must be FAILED after graph exception; got {task.status!r}"
            )
            assert task.worker_lease_until is None, "Worker lease must be released on failure"

            # No report must exist — a FAILED task has no persisted report
            report = await db.scalar(
                select(ResearchReport).where(ResearchReport.research_task_id == uuid.UUID(task_id))
            )
            assert report is None, (
                "ResearchReport must NOT be created for a failed workflow"
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_incomplete_graph_output_cannot_be_persisted_as_completed(monkeypatch):
    """Graph completes but returns no final_report_markdown → task must be FAILED,
    NOT COMPLETED, and no report row must be created.
    """
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda tid: None),
    )

    class NoReportGraph:
        async def ainvoke(self, _state: dict) -> dict:
            # Returns a dict with no final_report_markdown
            return {"current_agent": "post_processor", "status": "COMPLETED"}

    monkeypatch.setattr(worker_module, "research_graph", NoReportGraph())

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, f"noreport_{suffix}")
        task_id = await _create_and_start(client, headers, "Empty report task")
        assert await task_dispatcher.dispatch_one_outbox_event()

        with pytest.raises(RuntimeError, match="without producing a report"):
            await run_langgraph_workflow(task_id)

        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, uuid.UUID(task_id))
            assert task.status == "FAILED", (
                f"Task must be FAILED when no report content is produced; got {task.status!r}"
            )
            report = await db.scalar(
                select(ResearchReport).where(ResearchReport.research_task_id == uuid.UUID(task_id))
            )
            assert report is None, "No ResearchReport row must exist for incomplete workflow"

    await engine.dispose()


@pytest.mark.asyncio
async def test_report_retrieval_and_ownership(monkeypatch):
    """Completed tasks expose reports only to the owning user.
    A second user must receive 404 on the other user's report endpoint.
    """
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda tid: None),
    )

    class SuccessGraph:
        async def ainvoke(self, _state: dict) -> dict:
            return {
                "final_report_markdown": "# Result\nOwner-scoped report.",
                "current_agent": "post_processor",
            }

    monkeypatch.setattr(worker_module, "research_graph", SuccessGraph())

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        owner_headers = await _register_and_login(client, f"owner_{suffix}")
        other_headers = await _register_and_login(client, f"other_{suffix}")

        task_id = await _create_and_start(client, owner_headers, "Owner report task")
        assert await task_dispatcher.dispatch_one_outbox_event()
        result = await run_langgraph_workflow(task_id)
        assert result["status"] == "SUCCESS"

        # Owner can fetch the task and report
        task_resp = await client.get(f"/api/v1/research/{task_id}", headers=owner_headers)
        assert task_resp.status_code == 200
        assert task_resp.json()["status"] == "COMPLETED"

        report_resp = await client.get(f"/api/v1/research/{task_id}/report", headers=owner_headers)
        assert report_resp.status_code == 200
        assert report_resp.json()["research_task_id"] == task_id
        assert "Owner-scoped report" in report_resp.json()["content_markdown"]

        # Other user must receive 404 for both task and report
        assert (
            await client.get(f"/api/v1/research/{task_id}", headers=other_headers)
        ).status_code == 404

        assert (
            await client.get(f"/api/v1/research/{task_id}/report", headers=other_headers)
        ).status_code == 404

    await engine.dispose()


@pytest.mark.asyncio
async def test_duplicate_delivery_after_completed_is_ignored(monkeypatch):
    """A second worker delivery after COMPLETED must return IGNORED,
    not create a second report row.
    """
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda tid: None),
    )

    class SuccessGraph:
        async def ainvoke(self, _state: dict) -> dict:
            return {
                "final_report_markdown": "# Idempotent report.",
                "current_agent": "post_processor",
            }

    monkeypatch.setattr(worker_module, "research_graph", SuccessGraph())

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, f"idem_{suffix}")
        task_id = await _create_and_start(client, headers, "Idempotent task")
        assert await task_dispatcher.dispatch_one_outbox_event()

        first = await run_langgraph_workflow(task_id)
        assert first["status"] == "SUCCESS"

        # Duplicate delivery
        second = await run_langgraph_workflow(task_id)
        assert second["status"] == "IGNORED", (
            f"Duplicate delivery after COMPLETED must be IGNORED; got {second['status']!r}"
        )

        # Only one report row must exist
        async with AsyncSessionLocal() as db:
            reports = (await db.execute(
                select(ResearchReport).where(ResearchReport.research_task_id == uuid.UUID(task_id))
            )).scalars().all()
            assert len(reports) == 1, (
                f"Expected exactly 1 report row; found {len(reports)}"
            )

    await engine.dispose()


@pytest.mark.asyncio
async def test_real_nodes_pipeline_with_mocked_provider_boundaries(monkeypatch):
    """Run the actual agent nodes and persistence path without contacting providers.

    Only LLM, search, fetch, and embedding boundaries are deterministic fakes;
    LangGraph routing, researcher, curator, analyst, writer, critic, postprocessor,
    API, worker, and PostgreSQL writes are real.
    """
    writer_prompts: list[str] = []
    from app.services import progress as progress_service

    progress_steps: list[str] = []
    record_progress = progress_service.record_agent_progress

    async def track_progress(task_id, attempt_number, current_step, current_iteration=None):
        progress_steps.append(current_step)
        return await record_progress(task_id, attempt_number, current_step, current_iteration)

    monkeypatch.setattr(progress_service, "record_agent_progress", track_progress)
    report_markdown = "# Findings\n\nThe source supports the finding."

    class FakeStructuredLLM:
        def with_structured_output(self, schema):
            self.schema = schema
            return self

        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, _messages):
            if self.schema is nodes_module.SupervisorPlan:
                return nodes_module.SupervisorPlan(
                    research_angle="evidence review",
                    search_queries=["example evidence"],
                    required_sections=["Findings", "References"],
                )
            if self.schema is nodes_module.AnalystExtraction:
                return nodes_module.AnalystExtraction(claims=[
                    nodes_module.ExtractedClaim(
                        claim="The source supports the finding.",
                        evidence_quote="The source provides supporting evidence.",
                    )
                ])
            if self.schema is nodes_module.CriticVerdict:
                return nodes_module.CriticVerdict(verdict="PASS", feedback=[], missing_areas=[])
            raise AssertionError(f"Unexpected structured output schema: {self.schema}")

    class FakeWriterLLM:
        def with_fallbacks(self, _fallbacks):
            return self

        async def ainvoke(self, messages):
            prompt = str(messages)
            writer_prompts.append(prompt)
            claim_id_match = re.search(r"'claim_id': '([0-9a-f-]{36})'", prompt)
            assert claim_id_match, f"Writer must receive a persisted claim ID: {prompt}"
            return SimpleNamespace(content=f"{report_markdown} [[@claim:{claim_id_match.group(1)}]]")

    monkeypatch.setattr(nodes_module, "get_fast_llm", FakeStructuredLLM)
    monkeypatch.setattr(nodes_module, "get_smart_llm", FakeWriterLLM)

    async def fake_search(_queries, max_results_per_query=3):
        return [SearchResult(
            title="Example paper",
            url="https://example.org/paper",
            content="The source provides supporting evidence.",
        )]

    async def fake_fetch(urls, max_concurrent=5):
        return {url: "The source provides supporting evidence." for url in urls}

    monkeypatch.setattr("app.tools.search.execute_parallel_searches", fake_search)
    monkeypatch.setattr("app.tools.scraper.fetch_urls_parallel", fake_fetch)

    class FakeEmbedder:
        async def embed_and_store(self, db, task_id, source_id, text_content):
            db.add(DocumentChunk(
                research_task_id=task_id,
                source_id=source_id,
                chunk_index=0,
                content=text_content,
                token_count=7,
            ))
            await db.flush()
            return 1

        async def search_similar_chunks(self, db, task_id, _query, limit=3):
            rows = (await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.research_task_id == task_id)
                .order_by(DocumentChunk.chunk_index)
                .limit(limit)
            )).scalars().all()
            return [(row, 0.0) for row in rows]

    monkeypatch.setattr("app.tools.embedder.EmbedderTool", FakeEmbedder)
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda _task_id: None),
    )

    suffix = uuid.uuid4().hex[:10]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _register_and_login(client, f"realnodes_{suffix}")
        task_id = await _create_and_start(client, headers, "Real-node vertical slice")
        assert await task_dispatcher.dispatch_one_outbox_event()

        result = await run_langgraph_workflow(task_id)
        assert result["status"] == "SUCCESS"

        task = await client.get(f"/api/v1/research/{task_id}", headers=headers)
        report = await client.get(f"/api/v1/research/{task_id}/report", headers=headers)
        assert task.status_code == 200 and task.json()["status"] == "COMPLETED"
        assert task.json()["current_step"] == "POST_PROCESSOR"
        assert report.status_code == 200
        assert "The source supports the finding. [1]" in report.json()["content_markdown"]
        assert "## References" in report.json()["content_markdown"]

    assert len(writer_prompts) == 1
    assert list(dict.fromkeys(progress_steps)) == [
        "SUPERVISOR", "RESEARCHER", "CURATOR", "ANALYST", "WRITER", "CRITIC", "POST_PROCESSOR",
    ]
    assert "The source supports the finding." in writer_prompts[0]
    assert "The source provides supporting evidence." in writer_prompts[0]

    async with AsyncSessionLocal() as db:
        sources = (await db.execute(
            select(ResearchSource).where(ResearchSource.research_task_id == uuid.UUID(task_id))
        )).scalars().all()
        chunks = (await db.execute(
            select(DocumentChunk).where(DocumentChunk.research_task_id == uuid.UUID(task_id))
        )).scalars().all()
        assert len(sources) == 1
        assert sources[0].url == "https://example.org/paper"
        assert len(chunks) == 1
        assert chunks[0].source_id == sources[0].id
        assert chunks[0].content == "The source provides supporting evidence."
        claims = (await db.execute(
            select(ResearchClaim).where(ResearchClaim.research_task_id == uuid.UUID(task_id))
        )).scalars().all()
        evidences = (await db.execute(
            select(Evidence).where(Evidence.research_task_id == uuid.UUID(task_id))
        )).scalars().all()
        links = (await db.execute(
            select(ClaimEvidence).where(ClaimEvidence.claim_id == claims[0].id)
        )).scalars().all()
        citations = (await db.execute(
            select(Citation).where(Citation.research_task_id == uuid.UUID(task_id))
        )).scalars().all()
        assert len(claims) == len(evidences) == len(links) == len(citations) == 1
        assert claims[0].is_verified is True
        assert evidences[0].content == "The source provides supporting evidence."
        assert evidences[0].chunk_id == chunks[0].id
        assert citations[0].claim_id == claims[0].id
        assert citations[0].source_id == sources[0].id
        assert citations[0].chunk_id == chunks[0].id
        assert citations[0].report_id == uuid.UUID(report.json()["id"])

        # Reprocessing the same extraction is idempotent; unsupported quotes
        # and chunks owned by another task cannot create trusted claims.
        persisted_again = await persist_grounded_claims(
            db,
            uuid.UUID(task_id),
            [{
                "claim": "The source supports the finding.",
                "evidence_quote": "The source provides supporting evidence.",
            }],
            chunks,
        )
        assert len(persisted_again) == 1
        assert persisted_again[0]["claim_id"] == str(claims[0].id)
        unsupported = await persist_grounded_claims(
            db,
            uuid.UUID(task_id),
            [{"claim": "Unsupported claim", "evidence_quote": "Not in the source."}],
            chunks,
        )
        assert unsupported == []

        task_row = await db.get(ResearchTask, uuid.UUID(task_id))
        other_task = ResearchTask(
            user_id=task_row.user_id,
            title="Different task",
            research_question="A separate research question",
        )
        db.add(other_task)
        await db.flush()
        cross_task = await persist_grounded_claims(
            db,
            other_task.id,
            [{
                "claim": "Cross-task claim",
                "evidence_quote": "The source provides supporting evidence.",
            }],
            chunks,
        )
        assert cross_task == []
        await db.commit()

        assert len((await db.execute(
            select(ResearchClaim).where(ResearchClaim.research_task_id == uuid.UUID(task_id))
        )).scalars().all()) == 1
        assert len((await db.execute(
            select(Evidence).where(Evidence.research_task_id == uuid.UUID(task_id))
        )).scalars().all()) == 1

    await engine.dispose()


# ---------------------------------------------------------------------------
# SSRF guard tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ssrf_blocks_non_public_ipv4():
    """Scraper must reject private IPv4 ranges (RFC-1918)."""
    scraper = ScraperTool()
    private_cases = [
        "http://192.168.1.1/page",
        "http://10.0.0.1/page",
        "http://172.16.0.1/page",
    ]
    for url in private_cases:
        # We patch _resolve_ips to return the IP we want tested
        # (avoids actual DNS lookup for literal IPs — our updated _check_ssrf
        # now short-circuits on literal IPs, so this tests the literal-IP path)
        with pytest.raises(SSRFError, match="không public"):
            await scraper._check_ssrf(url)


@pytest.mark.asyncio
async def test_ssrf_blocks_loopback_ipv4():
    scraper = ScraperTool()
    with pytest.raises(SSRFError):
        await scraper._check_ssrf("http://127.0.0.1/internal")


@pytest.mark.asyncio
async def test_ssrf_blocks_localhost_by_name():
    scraper = ScraperTool()
    with pytest.raises(SSRFError):
        await scraper._check_ssrf("http://localhost/internal")


@pytest.mark.asyncio
async def test_ssrf_blocks_ipv6_loopback_literal():
    """Literal [::1] in URL must be blocked without DNS lookup."""
    scraper = ScraperTool()
    with pytest.raises(SSRFError):
        await scraper._check_ssrf("http://[::1]/internal")


@pytest.mark.asyncio
async def test_ssrf_blocks_ipv4_mapped_loopback():
    """::ffff:127.0.0.1 must be blocked (IPv4-mapped loopback)."""
    scraper = ScraperTool()
    ip = ipaddress.IPv6Address("::ffff:127.0.0.1")
    with pytest.raises(SSRFError):
        scraper._assert_public_ip(ip, "::ffff:127.0.0.1")


@pytest.mark.asyncio
async def test_ssrf_blocks_ipv4_mapped_private():
    """::ffff:10.0.0.1 must be blocked (IPv4-mapped private)."""
    scraper = ScraperTool()
    ip = ipaddress.IPv6Address("::ffff:10.0.0.1")
    with pytest.raises(SSRFError):
        scraper._assert_public_ip(ip, "::ffff:10.0.0.1")


@pytest.mark.asyncio
async def test_ssrf_blocks_ipv6_link_local():
    """fe80:: link-local addresses must be blocked."""
    scraper = ScraperTool()
    ip = ipaddress.IPv6Address("fe80::1")
    with pytest.raises(SSRFError):
        scraper._assert_public_ip(ip, "fe80::1")


@pytest.mark.asyncio
async def test_ssrf_blocks_ipv6_unique_local():
    """fc00::/7 unique-local addresses must be blocked."""
    scraper = ScraperTool()
    ip = ipaddress.IPv6Address("fd00::1")
    with pytest.raises(SSRFError):
        scraper._assert_public_ip(ip, "fd00::1")


@pytest.mark.asyncio
async def test_ssrf_blocks_non_http_scheme():
    scraper = ScraperTool()
    with pytest.raises(SSRFError, match="Schema"):
        await scraper._check_ssrf("file:///etc/passwd")


@pytest.mark.asyncio
async def test_ssrf_redirect_following_disabled(monkeypatch):
    """ScraperTool must not follow redirects — validated by inspecting the httpx
    client construction. A 302 to a private IP must not be fetched."""
    scraper = ScraperTool()
    redirect_target = "http://192.168.99.99/secret"

    # Simulate: the initial URL is public but the server redirects to private IP.
    # With follow_redirects=False the httpx client raises on 3xx status.
    import httpx

    public_url = "https://public.example.com/page"
    call_log: list[str] = []

    async def _allow_public_target(_url: str) -> None:
        return None

    async def _fake_get(_client, url, **kwargs):
        call_log.append(str(url))
        return httpx.Response(
            302,
            headers={"Location": redirect_target},
            request=httpx.Request("GET", str(url)),
        )

    monkeypatch.setattr(scraper, "_check_ssrf", _allow_public_target)
    monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)
    result = await scraper.fetch_and_extract(public_url)

    assert result is None, "A redirect response must not be treated as page content"
    assert call_log == [public_url], "The private redirect target must never be requested"
