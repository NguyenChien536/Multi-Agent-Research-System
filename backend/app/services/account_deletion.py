"""Resumable account erasure built on the existing task cleanup outbox."""
from datetime import datetime, timezone

from sqlalchemy import delete, exists, select

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.task import ResearchTask, TaskDeletionOutbox, TaskDispatchOutbox, WorkflowRun
from app.models.user import User
from app.services.provider_budget import pause_budget_config


async def tombstone_task(session, task):
    """Caller holds the task lock; commit the tombstone and outbox together."""
    if task.status == "DELETING":
        return
    now = datetime.now(timezone.utc)
    task.status = "DELETING"
    task.deleted_at = now
    config = pause_budget_config(task.budget_config)
    config.pop('_llm_connection', None)
    task.budget_config = config
    runs = await session.scalars(select(WorkflowRun).where(
        WorkflowRun.research_task_id == task.id,
        WorkflowRun.status.in_(["RUNNING", "WAITING_APPROVAL", "WAITING_USER_DATA"]),
    ).with_for_update())
    for run in runs:
        run.status = "CANCELLED"
        run.completed_at = now
    events = await session.scalars(select(TaskDispatchOutbox).where(
        TaskDispatchOutbox.research_task_id == task.id,
        TaskDispatchOutbox.dispatched_at.is_(None),
    ).with_for_update())
    for event in events:
        event.dispatched_at = now
        event.last_error = "Task deleted by owner"
    outbox = await session.scalar(select(TaskDeletionOutbox).where(
        TaskDeletionOutbox.research_task_id == task.id,
    ).with_for_update())
    if outbox is None:
        session.add(TaskDeletionOutbox(research_task_id=task.id))


async def progress_account_deletion() -> bool:
    """One bounded step per poll; no account lock is held while locking tasks."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            task = await session.scalar(select(ResearchTask).join(User).where(
                User.deleted_at.is_not(None), ResearchTask.status != "DELETING",
            ).order_by(ResearchTask.id).limit(1).with_for_update(of=ResearchTask, skip_locked=True))
            if task is not None:
                await tombstone_task(session, task)
                return True
            user = await session.scalar(select(User).where(
                User.deleted_at.is_not(None),
                ~exists().where(ResearchTask.user_id == User.id),
            ).order_by(User.deleted_at).limit(1).with_for_update(skip_locked=True))
            if user is None:
                return False
            await session.execute(delete(User).where(User.id == user.id))
            return True


async def delete_checkpoint_threads(thread_ids):
    """Remove private graph state before its WorkflowRun identities disappear."""
    if not thread_ids:
        return
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_SYNC_URL) as saver:
        cursor = await saver.conn.execute(
            "SELECT to_regclass('public.checkpoints') AS checkpoints, "
            "to_regclass('public.checkpoint_blobs') AS blobs, "
            "to_regclass('public.checkpoint_writes') AS writes"
        )
        tables = (await cursor.fetchone()).values()
        present = [table is not None for table in tables]
        if not any(present):
            return
        if not all(present):
            raise RuntimeError("Incomplete checkpoint schema; keep cleanup intent for retry")
        for thread_id in thread_ids:
            await saver.adelete_thread(thread_id)
