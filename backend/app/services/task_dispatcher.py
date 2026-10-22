"""Reliable, retryable publication of database-backed task dispatch events."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.worker import execute_research_workflow

logger = logging.getLogger(__name__)


async def recover_unclaimed_dispatches(
    now: datetime | None = None,
    user_id: uuid.UUID | None = None,
) -> int:
    """Redeliver recent queued tasks whose broker message was never claimed.

    A dispatch is considered stale only after the acknowledgement grace period.
    Automatic recovery is limited by both task age and retry count so this loop
    cannot unexpectedly replay old work or redeliver forever.
    """
    now = now or datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=settings.OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS)
    recover_after = now - timedelta(seconds=settings.OUTBOX_AUTO_RECOVERY_MAX_AGE_SECONDS)
    max_retries = settings.OUTBOX_MAX_UNCLAIMED_RETRIES
    recovered = 0

    async with AsyncSessionLocal() as session:
        async with session.begin():
            query = (
                select(ResearchTask, TaskDispatchOutbox)
                .join(TaskDispatchOutbox, TaskDispatchOutbox.research_task_id == ResearchTask.id)
                .where(
                    ResearchTask.status == "QUEUED",
                    TaskDispatchOutbox.event_type == "START_RESEARCH",
                    TaskDispatchOutbox.dispatched_at <= stale_before,
                    TaskDispatchOutbox.dispatched_at >= recover_after,
                    TaskDispatchOutbox.unclaimed_retries < max_retries,
                )
                .order_by(TaskDispatchOutbox.dispatched_at)
                .limit(100)
                .with_for_update(of=(ResearchTask, TaskDispatchOutbox), skip_locked=True)
            )
            if user_id is not None:
                query = query.where(ResearchTask.user_id == user_id)
            result = await session.execute(query)

            for task, event in result.all():
                event.dispatched_at = None
                event.available_at = now
                event.locked_until = None
                event.unclaimed_retries += 1
                event.last_error = (
                    "Worker did not claim dispatched task; scheduled bounded redelivery "
                    f"({event.unclaimed_retries}/{max_retries})"
                )
                recovered += 1
                logger.warning(
                    "Requeued stale task dispatch event=%s task=%s unclaimed_retry=%s/%s",
                    event.id,
                    task.id,
                    event.unclaimed_retries,
                    max_retries,
                )

            diagnostic = "Automatic redelivery limit reached; manual retry required"
            exhausted_query = (
                select(ResearchTask, TaskDispatchOutbox)
                .join(TaskDispatchOutbox, TaskDispatchOutbox.research_task_id == ResearchTask.id)
                .where(
                    ResearchTask.status == "QUEUED",
                    TaskDispatchOutbox.event_type == "START_RESEARCH",
                    TaskDispatchOutbox.dispatched_at <= stale_before,
                    TaskDispatchOutbox.dispatched_at >= recover_after,
                    TaskDispatchOutbox.unclaimed_retries >= max_retries,
                    or_(
                        TaskDispatchOutbox.last_error.is_(None),
                        TaskDispatchOutbox.last_error != diagnostic,
                    ),
                )
                .order_by(TaskDispatchOutbox.dispatched_at)
                .limit(100)
                .with_for_update(of=(ResearchTask, TaskDispatchOutbox), skip_locked=True)
            )
            if user_id is not None:
                exhausted_query = exhausted_query.where(ResearchTask.user_id == user_id)
            exhausted_result = await session.execute(exhausted_query)
            for task, event in exhausted_result.all():
                event.last_error = diagnostic
                logger.error(
                    "Stale task dispatch exhausted retries event=%s task=%s unclaimed_retries=%s",
                    event.id,
                    task.id,
                    event.unclaimed_retries,
                )

    return recovered


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


async def dispatch_one_outbox_event(user_id: uuid.UUID | None = None) -> bool:
    """Publish one due event for a user with running capacity. Returns False when nothing is ready."""
    now = datetime.now(timezone.utc)
    await recover_expired_worker_claims(now)
    await recover_unclaimed_dispatches(now, user_id=user_id)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            task_alias = aliased(ResearchTask)
            active_running_tasks = (
                select(func.count(task_alias.id))
                .where(
                    task_alias.user_id == ResearchTask.user_id,
                    task_alias.status == "RUNNING",
                )
                .scalar_subquery()
            )

            query = (
                select(TaskDispatchOutbox)
                .join(ResearchTask, TaskDispatchOutbox.research_task_id == ResearchTask.id)
                .where(
                    TaskDispatchOutbox.dispatched_at.is_(None),
                    TaskDispatchOutbox.available_at <= now,
                    (TaskDispatchOutbox.locked_until.is_(None) | (TaskDispatchOutbox.locked_until <= now)),
                    ResearchTask.status == "QUEUED",
                    active_running_tasks < settings.MAX_CONCURRENT_TASKS_PER_USER,
                )
            )
            if user_id is not None:
                query = query.where(ResearchTask.user_id == user_id)

            query = (
                query.order_by(TaskDispatchOutbox.created_at)
                .limit(1)
                .with_for_update(of=TaskDispatchOutbox, skip_locked=True)
            )
            result = await session.execute(query)
            event = result.scalar_one_or_none()
            if event is None:
                return False
            claim_lease = now + timedelta(seconds=settings.OUTBOX_LOCK_SECONDS)
            event.locked_until = claim_lease
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
                if event and event.dispatched_at is None and event.locked_until == claim_lease:
                    event.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    event.locked_until = None
                    event.last_error = str(exc)[:2000]
        logger.warning("Task dispatch failed; event=%s retry_in=%ss", event_id, retry_after, exc_info=exc)
        return True

    async with AsyncSessionLocal() as session:
        async with session.begin():
            event = await session.get(TaskDispatchOutbox, event_id, with_for_update=True)
            if event and event.dispatched_at is None and event.locked_until == claim_lease:
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
