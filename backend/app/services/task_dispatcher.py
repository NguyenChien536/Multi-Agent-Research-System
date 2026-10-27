"""Reliable, retryable publication of database-backed task dispatch events."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.experiment import AnalysisRun, ExperimentJournalEntry
from app.models.task import ResearchTask, TaskDispatchOutbox, DocumentIngestionOutbox, TaskDeletionOutbox, WorkflowRun
from app.models.source import ResearchSource
from app.worker import execute_document_ingestion, execute_research_workflow, execute_task_deletion

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
                # Do not leave a paper looking busy forever when no worker has
                # accepted it after the bounded redelivery window.
                from app.services.provider_budget import pause_budget_config
                task.status = "FAILED"
                task.current_step = "DISPATCH_FAILED"
                task.completed_at = now
                task.budget_config = pause_budget_config(task.budget_config, now=now)
                task.description = (task.description or "") + "\nNo worker accepted the job after bounded redelivery; check worker availability before retrying."
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
                # If the worker died during a computational run, retain that
                # attempt as a technical failure before redelivering the task.
                # This is an operational failure, never a scientific finding.
                started_runs = await session.execute(
                    select(AnalysisRun)
                    .where(
                        AnalysisRun.research_task_id == task.id,
                        AnalysisRun.status == "STARTED",
                    )
                    .with_for_update()
                )
                for analysis_run in started_runs.scalars():
                    analysis_run.status = "FAILED"
                    analysis_run.error_message = "Worker lease expired before the analysis result was persisted"
                    analysis_run.completed_at = now
                    last_sequence = await session.scalar(
                        select(func.coalesce(func.max(ExperimentJournalEntry.sequence), 0)).where(
                            ExperimentJournalEntry.analysis_run_id == analysis_run.id
                        )
                    )
                    session.add(ExperimentJournalEntry(
                        research_task_id=task.id,
                        analysis_run_id=analysis_run.id,
                        sequence=int(last_sequence or 0) + 1,
                        kind="EXECUTION_RESULT",
                        actor="SYSTEM",
                        payload={
                            "status": "TECHNICAL_FAILURE",
                            "error_type": "WORKER_LEASE_EXPIRED",
                            "error": analysis_run.error_message,
                        },
                        artifact_ids=(
                            [str(analysis_run.dataset_artifact_id)]
                            if analysis_run.dataset_artifact_id else []
                        ),
                    ))

                config = dict(task.budget_config or {})
                recoveries = int(config.get("_worker_recoveries", 0)) + 1
                config["_worker_recoveries"] = recoveries
                task.budget_config = config
                if recoveries > settings.WORKER_MAX_RECOVERIES:
                    from app.services.provider_budget import pause_budget_config
                    task.budget_config = pause_budget_config(config, now=now)
                    task.status = "FAILED"
                    task.current_step = "RECOVERY_LIMIT"
                    task.worker_lease_until = None
                    task.completed_at = now
                    task.description = (task.description or "") + "\nWorker recovery limit reached; inspect runtime before retrying."
                    await session.execute(update(WorkflowRun).where(
                        WorkflowRun.research_task_id == task.id, WorkflowRun.status == "RUNNING",
                    ).values(status="FAILED", completed_at=now))
                    recovered += 1
                    continue
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


async def dispatch_one_document_ingestion_event(now: datetime | None = None) -> bool:
    """Publish one pending PDF-ingestion event from its durable database outbox."""
    now = now or datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=settings.OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS)
    recover_after = now - timedelta(seconds=settings.OUTBOX_AUTO_RECOVERY_MAX_AGE_SECONDS)
    max_retries = settings.OUTBOX_MAX_UNCLAIMED_RETRIES
    async with AsyncSessionLocal() as session:
        async with session.begin():
            stale = await session.execute(
                select(ResearchSource, DocumentIngestionOutbox)
                .join(DocumentIngestionOutbox, DocumentIngestionOutbox.source_id == ResearchSource.id)
                .join(ResearchTask, ResearchTask.id == DocumentIngestionOutbox.research_task_id)
                .where(
                    ResearchTask.status != "DELETING",
                    ResearchSource.ingestion_status == "PROCESSING",
                    ResearchSource.ingestion_lease_until <= now,
                    DocumentIngestionOutbox.dispatched_at.is_not(None),
                )
                .limit(50)
                .with_for_update(of=(ResearchSource, DocumentIngestionOutbox), skip_locked=True)
            )
            for source, stale_event in stale.all():
                source.ingestion_lease_until = None
                stale_event.locked_until = None
                if source.ingestion_attempt < max_retries:
                    source.ingestion_status = "PENDING"
                    source.ingestion_error = "Previous ingestion worker lease expired; retrying the same stored document"
                    stale_event.dispatched_at = None
                    stale_event.available_at = now
                    stale_event.last_error = source.ingestion_error
                else:
                    source.ingestion_status = "FAILED"
                    source.ingestion_error = "Document worker stopped repeatedly before ingestion completed. Retry this document manually."
                    stale_event.last_error = source.ingestion_error

            # A broker can accept a message even when no worker ever claims it.
            # Recover only recent messages and bound redelivery; terminally mark
            # exhausted/old jobs so they remain visible and manually retryable.
            stale_pending = await session.execute(
                select(ResearchSource, DocumentIngestionOutbox)
                .join(DocumentIngestionOutbox, DocumentIngestionOutbox.source_id == ResearchSource.id)
                .join(ResearchTask, ResearchTask.id == DocumentIngestionOutbox.research_task_id)
                .where(
                    ResearchTask.status != "DELETING",
                    ResearchSource.ingestion_status == "PENDING",
                    DocumentIngestionOutbox.dispatched_at <= stale_before,
                )
                .limit(50)
                .with_for_update(of=(ResearchSource, DocumentIngestionOutbox), skip_locked=True)
            )
            for source, stale_event in stale_pending.all():
                if stale_event.dispatched_at >= recover_after and stale_event.unclaimed_retries < max_retries:
                    stale_event.dispatched_at = None
                    stale_event.locked_until = None
                    stale_event.available_at = now
                    stale_event.unclaimed_retries += 1
                    stale_event.last_error = (
                        "Ingestion message was not claimed; retrying "
                        f"({stale_event.unclaimed_retries}/{max_retries})"
                    )
                    source.ingestion_error = stale_event.last_error
                else:
                    source.ingestion_status = "FAILED"
                    source.ingestion_error = "Ingestion worker did not claim this document. Retry it manually."
                    stale_event.last_error = source.ingestion_error

    async with AsyncSessionLocal() as session:
        async with session.begin():
            event = await session.scalar(
                select(DocumentIngestionOutbox)
                .join(ResearchTask, ResearchTask.id == DocumentIngestionOutbox.research_task_id)
                .join(ResearchSource, ResearchSource.id == DocumentIngestionOutbox.source_id)
                .where(
                    DocumentIngestionOutbox.dispatched_at.is_(None),
                    DocumentIngestionOutbox.available_at <= now,
                    (DocumentIngestionOutbox.locked_until.is_(None) | (DocumentIngestionOutbox.locked_until <= now)),
                    ResearchSource.ingestion_status == "PENDING",
                )
                .order_by(DocumentIngestionOutbox.created_at)
                .limit(1)
                .with_for_update(of=DocumentIngestionOutbox, skip_locked=True)
            )
            if event is None:
                return False
            event.locked_until = now + timedelta(seconds=settings.OUTBOX_LOCK_SECONDS)
            event.attempts += 1
            event_id = event.id
            source_id = event.source_id

    try:
        await asyncio.to_thread(execute_document_ingestion.delay, str(source_id))
    except Exception as exc:
        retry_after = min(
            settings.OUTBOX_MAX_RETRY_SECONDS,
            settings.OUTBOX_RETRY_SECONDS * 2 ** min(event.attempts - 1, 10),
        )
        async with AsyncSessionLocal() as session:
            async with session.begin():
                event = await session.get(DocumentIngestionOutbox, event_id, with_for_update=True)
                if event and event.dispatched_at is None:
                    event.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    event.locked_until = None
                    event.last_error = str(exc)[:2000]
        logger.warning("Document ingestion dispatch failed event=%s", event_id, exc_info=exc)
        return True

    async with AsyncSessionLocal() as session:
        async with session.begin():
            event = await session.get(DocumentIngestionOutbox, event_id, with_for_update=True)
            if event and event.dispatched_at is None:
                event.dispatched_at = datetime.now(timezone.utc)
                event.locked_until = None
                event.last_error = None
    return True


async def dispatch_one_task_deletion_event(now: datetime | None = None) -> bool:
    """Publish one due tombstone cleanup job from its durable outbox."""
    now = now or datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=settings.OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(TaskDeletionOutbox)
                .join(ResearchTask, ResearchTask.id == TaskDeletionOutbox.research_task_id)
                .where(
                    ResearchTask.status == "DELETING",
                    or_(
                        TaskDeletionOutbox.dispatched_at.is_(None),
                        (TaskDeletionOutbox.dispatched_at <= stale_before)
                        & (TaskDeletionOutbox.cleanup_lease_until.is_(None) | (TaskDeletionOutbox.cleanup_lease_until <= now)),
                    ),
                    TaskDeletionOutbox.available_at <= now,
                    (TaskDeletionOutbox.locked_until.is_(None) | (TaskDeletionOutbox.locked_until <= now)),
                )
                .order_by(TaskDeletionOutbox.created_at)
                .limit(1)
                .with_for_update(of=TaskDeletionOutbox, skip_locked=True)
            )
            event = result.scalar_one_or_none()
            if event is None:
                return False
            event.locked_until = now + timedelta(seconds=settings.OUTBOX_LOCK_SECONDS)
            event.attempts += 1
            event_id = event.id
            task_id = event.research_task_id
            claim_lease = event.locked_until

    try:
        await asyncio.to_thread(execute_task_deletion.delay, str(task_id))
    except Exception as exc:
        retry_after = min(settings.OUTBOX_MAX_RETRY_SECONDS, settings.OUTBOX_RETRY_SECONDS * 2 ** min(event.attempts - 1, 10))
        async with AsyncSessionLocal() as session:
            async with session.begin():
                event = await session.get(TaskDeletionOutbox, event_id, with_for_update=True)
                if event and event.dispatched_at is None and event.locked_until == claim_lease:
                    event.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    event.locked_until = None
                    event.last_error = f"Broker dispatch failed: {str(exc)[:1800]}"
        logger.warning("Task deletion dispatch failed event=%s", event_id, exc_info=exc)
        return True

    async with AsyncSessionLocal() as session:
        async with session.begin():
            event = await session.get(TaskDeletionOutbox, event_id, with_for_update=True)
            if event and event.dispatched_at is None and event.locked_until == claim_lease:
                event.dispatched_at = datetime.now(timezone.utc)
                event.locked_until = None
                event.last_error = None
    return True


async def outbox_dispatch_loop() -> None:
    """Poll the durable outbox; unavailable broker/DB never drops queued work."""
    while True:
        try:
            research_dispatched = await dispatch_one_outbox_event()
            ingestion_dispatched = await dispatch_one_document_ingestion_event()
            deletion_dispatched = await dispatch_one_task_deletion_event()
            dispatched = research_dispatched or ingestion_dispatched or deletion_dispatched
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Outbox dispatcher iteration failed")
            dispatched = False
        if not dispatched:
            await asyncio.sleep(settings.OUTBOX_POLL_SECONDS)
