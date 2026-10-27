"""Bounded recovery for broker messages that no worker claimed."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.models.user import User
from app.services import task_dispatcher


async def create_dispatched_task(dispatched_at: datetime) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    suffix = uuid.uuid4().hex
    async with AsyncSessionLocal() as session:
        async with session.begin():
            user = User(
                username=f"dispatch_{suffix}",
                email=f"dispatch_{suffix}@example.com",
                password_hash="test-only-hash",
            )
            session.add(user)
            await session.flush()
            task = ResearchTask(
                user_id=user.id,
                title="Dispatch recovery test",
                research_question="Can a stale dispatch be recovered safely?",
                status="QUEUED",
            )
            session.add(task)
            await session.flush()
            event = TaskDispatchOutbox(
                research_task_id=task.id,
                event_type="START_RESEARCH",
                attempts=1,
                dispatched_at=dispatched_at,
            )
            session.add(event)
            await session.flush()
            return user.id, task.id, event.id


async def load_event(event_id: uuid.UUID) -> TaskDispatchOutbox:
    async with AsyncSessionLocal() as session:
        return await session.get(TaskDispatchOutbox, event_id)


@pytest.mark.asyncio
async def test_recent_unclaimed_dispatch_is_redelivered_with_a_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(settings, "OUTBOX_AUTO_RECOVERY_MAX_AGE_SECONDS", 3600)
    monkeypatch.setattr(settings, "OUTBOX_MAX_UNCLAIMED_RETRIES", 2)
    published: list[str] = []
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: published.append(task_id)),
    )

    user_id, task_id, event_id = await create_dispatched_task(datetime.now(timezone.utc) - timedelta(seconds=31))

    assert await task_dispatcher.dispatch_one_outbox_event(user_id=user_id)
    first_event = await load_event(event_id)
    assert published == [str(task_id)]
    assert first_event.unclaimed_retries == 1
    assert first_event.dispatched_at is not None
    # The normal dispatch finalizer clears the transient recovery diagnostic;
    # the persisted counter and recovery log retain the retry history safely.
    assert first_event.last_error is None

    # A fresh dispatch is not sent again during its acknowledgement grace period.
    assert not await task_dispatcher.dispatch_one_outbox_event(user_id=user_id)
    assert published == [str(task_id)]

    # One more stale delivery is permitted; a third is stopped and diagnosed.
    async with AsyncSessionLocal() as session:
        event = await session.get(TaskDispatchOutbox, event_id)
        event.dispatched_at = datetime.now(timezone.utc) - timedelta(seconds=31)
        await session.commit()
    assert await task_dispatcher.dispatch_one_outbox_event(user_id=user_id)
    assert published == [str(task_id), str(task_id)]

    async with AsyncSessionLocal() as session:
        event = await session.get(TaskDispatchOutbox, event_id)
        event.dispatched_at = datetime.now(timezone.utc) - timedelta(seconds=31)
        await session.commit()
    assert not await task_dispatcher.dispatch_one_outbox_event(user_id=user_id)
    exhausted_event = await load_event(event_id)
    assert exhausted_event.unclaimed_retries == 2
    assert exhausted_event.dispatched_at is not None
    assert exhausted_event.last_error == "Automatic redelivery limit reached; manual retry required"
    async with AsyncSessionLocal() as session:
        task = await session.get(ResearchTask, task_id)
        assert task.status == "FAILED"
        assert task.current_step == "DISPATCH_FAILED"
    assert published == [str(task_id), str(task_id)]


@pytest.mark.asyncio
async def test_old_unclaimed_dispatch_is_never_automatically_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(settings, "OUTBOX_AUTO_RECOVERY_MAX_AGE_SECONDS", 3600)
    published: list[str] = []
    monkeypatch.setattr(
        task_dispatcher,
        "execute_research_workflow",
        SimpleNamespace(delay=lambda task_id: published.append(task_id)),
    )

    old_dispatch = datetime.now(timezone.utc) - timedelta(hours=2)
    user_id, _, event_id = await create_dispatched_task(old_dispatch)

    assert not await task_dispatcher.dispatch_one_outbox_event(user_id=user_id)
    event = await load_event(event_id)
    assert event.dispatched_at == old_dispatch
    assert event.unclaimed_retries == 0
    assert event.last_error is None
    assert published == []


@pytest.mark.asyncio
async def test_concurrent_recovery_resets_an_event_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(settings, "OUTBOX_AUTO_RECOVERY_MAX_AGE_SECONDS", 3600)
    user_id, _, event_id = await create_dispatched_task(datetime.now(timezone.utc) - timedelta(seconds=31))

    recovered = await asyncio.gather(
        task_dispatcher.recover_unclaimed_dispatches(user_id=user_id),
        task_dispatcher.recover_unclaimed_dispatches(user_id=user_id),
    )

    event = await load_event(event_id)
    assert sum(recovered) == 1
    assert event.unclaimed_retries == 1
    assert event.dispatched_at is None
