import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.models.user import User
from app.services.provider_budget import (
    ProviderBudgetExceeded,
    ResearchTaskStopped,
    assert_task_active,
    reserve_provider_call,
    settle_provider_call,
)


async def create_running_task(**budget_overrides):
    user_id = uuid.uuid4()
    task_id = uuid.uuid4()
    budget = {
        "max_cost_usd": 2.0,
        "max_llm_calls": 40,
        "max_input_tokens": 100_000,
        "max_output_tokens": 50_000,
        "timeout_seconds": 900,
        **budget_overrides,
    }
    async with AsyncSessionLocal() as db:
        user = User(
            id=user_id,
            username=f"budget_{user_id.hex[:12]}",
            email=f"{user_id.hex}@example.com",
            password_hash="test-only",
        )
        db.add(user)
        await db.flush()
        db.add(ResearchTask(
            id=task_id,
            user_id=user_id,
            title="Provider budget test",
            research_question="Verify provider call limits safely",
            status="RUNNING",
            attempt_number=1,
            worker_lease_until=datetime.now(timezone.utc) + timedelta(minutes=5),
            budget_config=budget,
        ))
        await db.commit()
    return task_id, user_id


async def delete_test_user(user_id):
    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user:
            await db.delete(user)
            await db.commit()


@pytest.mark.asyncio
async def test_provider_attempt_limit_is_atomic_under_concurrency():
    task_id, user_id = await create_running_task(max_llm_calls=1)
    try:
        results = await asyncio.gather(*[
            reserve_provider_call(
                task_id=task_id,
                attempt_number=1,
                kind="llm",
                model="gemini-3.5-flash-lite",
                input_tokens=100,
                output_tokens=4096,
            )
            for _ in range(2)
        ], return_exceptions=True)
        assert sum(isinstance(item, str) for item in results) == 1
        assert sum(isinstance(item, ProviderBudgetExceeded) for item in results) == 1
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_cost_limit_blocks_call_before_creating_reservation():
    task_id, user_id = await create_running_task(max_cost_usd=0.001)
    try:
        with pytest.raises(ProviderBudgetExceeded, match="cost budget"):
            await reserve_provider_call(
                task_id=task_id,
                attempt_number=1,
                kind="llm",
                model="gpt-4o",
                input_tokens=10,
                output_tokens=4096,
            )
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_cancelled_or_stale_attempt_cannot_reserve_a_provider_call():
    task_id, user_id = await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            task.status = "CANCELLED"
            await db.commit()
        with pytest.raises(ResearchTaskStopped):
            await reserve_provider_call(
                task_id=task_id,
                attempt_number=1,
                kind="llm",
                model="gemini-3.5-flash-lite",
                input_tokens=1,
                output_tokens=4096,
            )
        with pytest.raises(ResearchTaskStopped):
            await reserve_provider_call(
                task_id=task_id,
                attempt_number=2,
                kind="llm",
                model="gemini-3.5-flash-lite",
                input_tokens=1,
                output_tokens=4096,
            )
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_active_time_budget_blocks_provider_call():
    task_id, user_id = await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            config = dict(task.budget_config)
            config["_provider_usage"] = {
                "llm_calls": 0, "search_calls": 0, "embedding_calls": 0,
                "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                "active_seconds": 0.0,
                "active_since": (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat(),
                "reservations": {},
            }
            task.budget_config = config
            await db.commit()
        with pytest.raises(ProviderBudgetExceeded, match="time budget"):
            await reserve_provider_call(
                task_id=task_id,
                attempt_number=1,
                kind="llm",
                model="gemini-3.5-flash-lite",
                input_tokens=1,
                output_tokens=4096,
            )
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_expired_worker_lease_blocks_provider_call():
    task_id, user_id = await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            task.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
        with pytest.raises(ResearchTaskStopped, match="lease expired"):
            await reserve_provider_call(
                task_id=task_id,
                attempt_number=1,
                kind="llm",
                model="gemini-3.5-flash-lite",
                input_tokens=1,
                output_tokens=4096,
            )
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_expired_worker_lease_blocks_later_side_effects():
    task_id, user_id = await create_running_task()
    try:
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            task.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            await db.commit()
        with pytest.raises(ResearchTaskStopped, match="lease expired"):
            await assert_task_active(task_id, 1)
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_search_cost_is_reserved_before_tavily_is_called(monkeypatch):
    from app.core.config import settings
    from app.tools.search import TavilySearchTool

    task_id, user_id = await create_running_task(max_cost_usd=0.005)
    try:
        class FakeTavilyClient:
            called = False

            async def search(self, **_kwargs):
                self.called = True
                return {"results": []}

        tool = TavilySearchTool(api_key="test-key")
        tool.client = FakeTavilyClient()
        monkeypatch.setattr(settings, "TAVILY_REQUEST_COST_USD", 0.01)
        with pytest.raises(ProviderBudgetExceeded, match="cost budget"):
            await tool.search(
                "budget test",
                budget_context={"task_id": str(task_id), "attempt_number": 1},
            )
        assert tool.client.called is False
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_embedding_budget_does_not_deadlock_new_source_insert():
    from app.core.config import settings
    from app.models.source import ResearchSource
    from app.tools.embedder import EmbedderTool

    task_id, user_id = await create_running_task()
    try:
        class FakeEmbeddings:
            async def aembed_documents(self, texts):
                return [[0.0] * settings.EMBEDDING_DIMENSION for _ in texts]

        embedder = EmbedderTool()
        embedder.embeddings = FakeEmbeddings()
        embedder.model_name = "models/gemini-embedding-2"
        async with AsyncSessionLocal() as db:
            source = ResearchSource(
                research_task_id=task_id,
                source_tag="src_budget",
                title="Budget test source",
                url="https://example.com/budget-test",
                content_snippet="A short source with enough text to generate one vector chunk.",
            )
            db.add(source)
            await db.flush()
            chunks = await asyncio.wait_for(
                embedder.embed_and_store(
                    db=db,
                    task_id=task_id,
                    source_id=source.id,
                    text_content="A short source with enough text to generate one vector chunk.",
                    budget_context={"task_id": str(task_id), "attempt_number": 1},
                ),
                timeout=5,
            )
            assert chunks == 1
            await db.commit()
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            usage = task.budget_config["_provider_usage"]
            assert usage["embedding_calls"] == 1
            assert usage["reservations"] == {}
    finally:
        await delete_test_user(user_id)


@pytest.mark.asyncio
async def test_failed_or_uncertain_provider_attempt_keeps_its_reservation():
    task_id, user_id = await create_running_task(max_llm_calls=1)
    try:
        reservation = await reserve_provider_call(
            task_id=task_id,
            attempt_number=1,
            kind="llm",
            model="gemini-3.5-flash-lite",
            input_tokens=100,
            output_tokens=4096,
        )
        await settle_provider_call(
            task_id=task_id,
            reservation_id=reservation,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0,
            succeeded=False,
        )
        with pytest.raises(ProviderBudgetExceeded, match="LLM call limit"):
            await reserve_provider_call(
                task_id=task_id,
                attempt_number=1,
                kind="llm",
                model="gemini-3.5-flash-lite",
                input_tokens=1,
                output_tokens=4096,
            )
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            usage = task.budget_config["_provider_usage"]
            assert usage["llm_calls"] == 1
            assert usage["output_tokens"] == 4096, usage
            assert usage["reservations"] == {}, usage
    finally:
        await delete_test_user(user_id)


def test_client_budget_schema_enforces_the_product_hard_caps():
    from pydantic import ValidationError
    from app.schemas.task import BudgetConfigSchema

    assert BudgetConfigSchema().max_llm_calls == 40
    assert BudgetConfigSchema().timeout_seconds == 900
    with pytest.raises(ValidationError):
        BudgetConfigSchema(max_cost_usd=20)
    with pytest.raises(ValidationError):
        BudgetConfigSchema(max_llm_calls=200)
    with pytest.raises(ValidationError):
        BudgetConfigSchema(timeout_seconds=1800)


@pytest.mark.asyncio
async def test_each_fallback_attempt_is_reserved_and_counted(monkeypatch):
    from app.agents.nodes import BudgetedFallbackLLM, invoke_llm_with_budget

    task_id, user_id = await create_running_task(max_llm_calls=2)
    try:
        class FailingModel:
            async def ainvoke(self, _messages):
                raise RuntimeError("provider unavailable")

        class WorkingModel:
            async def ainvoke(self, _messages):
                return SimpleNamespace(
                    content="done",
                    usage_metadata={"input_tokens": 10, "output_tokens": 2},
                )

        model = BudgetedFallbackLLM([
            ("gemini-3.5-flash-lite", FailingModel()),
            ("gemini-3.5-flash", WorkingModel()),
        ])
        response = await invoke_llm_with_budget(
            {
                "task_id": str(task_id),
                "attempt_number": 1,
                "enforce_provider_budget": True,
            },
            model,
            [SimpleNamespace(content="A short prompt")],
            model_name="gemini-3.5-flash-lite",
            output_tokens=4096,
        )
        assert response.content == "done"
        async with AsyncSessionLocal() as db:
            task = await db.get(ResearchTask, task_id)
            usage = task.budget_config["_provider_usage"]
            assert usage["llm_calls"] == 2, usage
            assert usage["reservations"] == {}, usage
    finally:
        await delete_test_user(user_id)
