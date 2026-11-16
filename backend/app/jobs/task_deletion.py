"""Tombstone cleanup for tasks and private artifacts."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, TaskDeletionOutbox, WorkflowRun
from app.models.source import ResearchSource

logger = logging.getLogger(__name__)

async def delete_research_task(task_id: str, *, artifact_store) -> dict:
    """Remove private files only after active research/ingestion leases expire."""
    task_uuid = uuid.UUID(task_id)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            task = await session.scalar(
                select(ResearchTask).where(ResearchTask.id == task_uuid).with_for_update()
            )
            if task is None:
                return {"status": "DELETED", "task_id": task_id}
            if task.status != "DELETING":
                return {"status": "IGNORED", "task_id": task_id, "reason": "Task is not tombstoned"}
            outbox = await session.scalar(
                select(TaskDeletionOutbox)
                .where(TaskDeletionOutbox.research_task_id == task_uuid)
                .with_for_update()
            )
            if outbox is None:
                outbox = TaskDeletionOutbox(research_task_id=task_uuid)
                session.add(outbox)
                await session.flush()
            if outbox.cleanup_lease_until and outbox.cleanup_lease_until > now:
                return {"status": "ALREADY_CLAIMED", "task_id": task_id}
            active_ingestion = await session.scalar(
                select(func.count(ResearchSource.id)).where(
                    ResearchSource.research_task_id == task_uuid,
                    ResearchSource.ingestion_status == "PROCESSING",
                    ResearchSource.ingestion_lease_until > now,
                )
            )
            if (task.worker_lease_until and task.worker_lease_until > now) or active_ingestion:
                outbox.available_at = now + timedelta(seconds=15)
                outbox.dispatched_at = None
                outbox.locked_until = None
                outbox.cleanup_lease_until = None
                outbox.last_error = "Cleanup deferred while an active worker lease is running"
                return {"status": "DEFERRED", "task_id": task_id}
            outbox.cleanup_lease_until = now + timedelta(
                seconds=max(settings.WORKER_LEASE_SECONDS * 2, settings.OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS * 2)
            )
            outbox_id = outbox.id
            thread_ids = list(await session.scalars(select(WorkflowRun.checkpoint_thread_id).where(
                WorkflowRun.research_task_id == task_uuid,
            )))

    try:
        await asyncio.to_thread(artifact_store.delete_task_artifacts, task_uuid)
        from app.services.account_deletion import delete_checkpoint_threads
        await delete_checkpoint_threads(thread_ids)
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                outbox = await session.get(TaskDeletionOutbox, outbox_id, with_for_update=True)
                if outbox is not None:
                    outbox.attempts += 1
                    retry_after = min(settings.OUTBOX_MAX_RETRY_SECONDS, settings.OUTBOX_RETRY_SECONDS * 2 ** min(outbox.attempts - 1, 10))
                    outbox.available_at = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
                    outbox.dispatched_at = None
                    outbox.locked_until = None
                    outbox.cleanup_lease_until = None
                    outbox.last_error = f"{type(exc).__name__}: {str(exc)[:1800]}"
        logger.exception("Task artifact cleanup failed task=%s; retained tombstone for retry", task_id)
        return {"status": "RETRY", "task_id": task_id}

    async with AsyncSessionLocal() as session:
        async with session.begin():
            task = await session.scalar(
                select(ResearchTask).where(ResearchTask.id == task_uuid).with_for_update()
            )
            if task is None:
                return {"status": "DELETED", "task_id": task_id}
            if task.status != "DELETING":
                return {"status": "RETRY", "task_id": task_id, "reason": "Tombstone changed during cleanup"}
            # No new worker can claim a tombstoned task; leases checked before
            # cleanup are static because both worker claim paths reject DELETING.
            await session.delete(task)
    logger.info("Deleted task and private artifacts task=%s", task_id)
    return {"status": "DELETED", "task_id": task_id}


