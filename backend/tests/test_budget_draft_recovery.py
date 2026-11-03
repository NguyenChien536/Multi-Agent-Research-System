from types import SimpleNamespace
import uuid

import pytest

from app import worker
from app.services import provider_budget
from app.services.provider_budget import ProviderBudgetExceeded, ResearchTaskStopped


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [None, "empty", "task", "run", "attempt", "uncheckpointed", "cancelled"])
async def test_only_current_owned_complete_checkpoint_can_recover(monkeypatch, invalid):
    task = SimpleNamespace(id=uuid.uuid4())
    run = SimpleNamespace(id=uuid.uuid4(), checkpoint_thread_id=str(uuid.uuid4()))
    saved = {"task_id": str(task.id), "workflow_run_id": str(run.id), "attempt_number": 1,
             "draft_report_markdown": "# Saved draft\n\nAn unfinished review needs verification.",
             "critic_review_metadata": {"status": "PASSED", "verdict": "PASS"}}
    if invalid == "empty": saved["draft_report_markdown"] = ""
    if invalid == "task": saved["task_id"] = str(uuid.uuid4())
    if invalid == "run": saved["workflow_run_id"] = str(uuid.uuid4())
    if invalid == "attempt": saved["attempt_number"] = 0

    class Graph:
        checkpointer = None if invalid == "uncheckpointed" else object()

        async def ainvoke(self, *_args, **_kwargs):
            raise ProviderBudgetExceeded("Input-token cap")

        async def aget_state(self, config):
            assert config["configurable"]["thread_id"] == run.checkpoint_thread_id
            return SimpleNamespace(values=saved, next=(), tasks=())

    async def active(*_args):
        if invalid == "cancelled": raise ResearchTaskStopped("Owner cancelled")

    monkeypatch.setattr(provider_budget, "assert_task_active", active)
    if invalid is not None:
        with pytest.raises(ResearchTaskStopped if invalid == "cancelled" else ProviderBudgetExceeded):
            await worker._invoke_checkpointed_graph(Graph(), {"attempt_number": 1}, task, run, None)
    else:
        # Uses the real deterministic citation formatter, with no provider client.
        result, _ = await worker._invoke_checkpointed_graph(Graph(), {"attempt_number": 1}, task, run, None)
        assert result["status"] == "NEEDS_REVIEW"
        assert "Saved draft" in result["final_report_markdown"]
        assert result["critic_review_metadata"]["status"] == "NEEDS_REVIEW"
        assert result["critic_review_metadata"]["draft_recovery"]["review_incomplete"] is True
        assert result["citations"] == []


@pytest.mark.asyncio
async def test_cancellation_during_deterministic_finalization_is_not_published(monkeypatch):
    task, run = SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4(), checkpoint_thread_id="run")
    saved = {"task_id": str(task.id), "workflow_run_id": str(run.id), "attempt_number": 1,
             "draft_report_markdown": "# Draft\nSaved text"}
    calls = 0

    async def stopped(*_args): raise ProviderBudgetExceeded("cap")
    async def snapshot(*_args): return SimpleNamespace(values=saved)
    async def active(*_args):
        nonlocal calls
        calls += 1
        if calls == 2: raise ResearchTaskStopped("cancelled during finalization")
    monkeypatch.setattr(worker, "_invoke_checkpointed_graph_unchecked", stopped)
    monkeypatch.setattr(provider_budget, "assert_task_active", active)
    with pytest.raises(ResearchTaskStopped):
        await worker._invoke_checkpointed_graph(SimpleNamespace(checkpointer=True, aget_state=snapshot),
                                                {"attempt_number": 1}, task, run, None)
