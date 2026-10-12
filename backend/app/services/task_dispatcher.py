"""Reliable, retryable publication of database-backed task dispatch events."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.worker import execute_research_workflow

logger = logging.getLogger(__name__)


async def recover_expired_worker_claims(now: datetime | None = None) -> int:
    """Requeue tasks whose worker stopped renewing its lease."""
    now = now or datetime.now(timezone.utc)
    recovered = 0
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(ResearchTask)
                .where(ResearchTask.status == "RUNNING", ResearchTask.worker_lease_until <= now)
                .order_by(ResearchTask.worker_lease_until)
                .limit(20)
                .with_for_update(skip_locked=True)
            )
            for task in result.scalars():
                task.status = "QUEUED"
                task.worker_lease_until = None
                event_result = await session.execute(
                    select(TaskDispatchOutbox)
                    .where(
                        TaskDispatchOutbox.research_task_id == task.id,
                        TaskDispatchOutbox.event_type == "START_RESEARCH",
                    )
                    .with_for_update()
                )
                event = event_result.scalar_one_or_none()
                if event is not None:
                    event.dispatched_at = None
                    event.available_at = now
                    event.locked_until = None
                    event.last_error = "Worker lease expired; task returned to the queue"
                    recovered += 1
    if recovered:
        logger.warning("Recovered %s task(s) after worker lease expiry", recovered)
    return recovered


async def dispatch_one_outbox_event() -> bool:
    """Publish one due event. Returns False when there is nothing ready."""
    now = datetime.now(timezone.utc)
    await recover_expired_worker_claims(now)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(TaskDispatchOutbox)
                .where(
                    TaskDispatchOutbox.dispatched_at.is_(None),
                    TaskDispatchOutbox.available_at <= now,
                    (TaskDispatchOutbox.locked_until.is_(None) | (TaskDispatchOutbox.locked_until <= now)),
                )
                .order_by(TaskDispatchOutbox.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            event = result.scalar_one_or_none()
            if event is None:
                return False
            event.locked_until = now + timedelta(seconds=settings.OUTBOX_LOCK_SECONDS)
            event.attempts += 1
            event_id = event.id
            task_id = event.research_task_id

    try:
        # Celery's .delay() is synchronous; keep broker I/O off the API event loop.
        await asyncio.to_thread(execute_research_workflow.delay, str(task_id))
    except Exception as exc:
        retry_after = min(settings.OUTBOX_MAX_RETRY_SECONDS, settings.OUTBOX_RETRY_SECONDS * 2 ** min(event.attempts - 1, 10))
        async with AsyncSessionLocal() as session:
            async with session.begin():
                event = await session.get(TaskDispatchOutbox, event_id, with_for_update=True)
                if event and event.dispatched_at is None:
                    event.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    event.locked_until = None
                    event.last_error = str(exc)[:2000]
        logger.warning("Task dispatch failed; event=%s retry_in=%ss", event_id, retry_after, exc_info=exc)
        return True

    async with AsyncSessionLocal() as session:
        async with session.begin():
            event = await session.get(TaskDispatchOutbox, event_id, with_for_update=True)
            if event and event.dispatched_at is None:
                event.dispatched_at = datetime.now(timezone.utc)
                event.locked_until = None
                event.last_error = None
    return True


async def outbox_dispatch_loop() -> None:
    """Poll the durable outbox; unavailable broker/DB never drops queued work."""
    while True:
        try:
            dispatched = await dispatch_one_outbox_event()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Outbox dispatcher iteration failed")
            dispatched = False
        if not dispatched:
            await asyncio.sleep(settings.OUTBOX_POLL_SECONDS)
