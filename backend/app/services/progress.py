"""Persist user-visible workflow progress for task polling."""

import logging
import uuid

from sqlalchemy import func, update

from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask

logger = logging.getLogger(__name__)


async def record_agent_progress(
    task_id: str | None,
    attempt_number: int | None,
    current_step: str,
    current_iteration: int | None = None,
) -> bool:
    """Update the current workflow step only while this worker owns the task."""
    if not task_id or attempt_number is None:
        return False

    try:
        parsed_task_id = uuid.UUID(task_id)
    except (TypeError, ValueError):
        logger.warning("Ignoring progress update with invalid task ID")
        return False

    values: dict[str, object] = {"current_step": current_step}
    if current_iteration is not None:
        values["current_iteration"] = current_iteration

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            update(ResearchTask)
            .where(
                ResearchTask.id == parsed_task_id,
                ResearchTask.status == "RUNNING",
                ResearchTask.attempt_number == attempt_number,
                ResearchTask.worker_lease_until > func.now(),
            )
            .values(**values)
        )
        await session.commit()
        updated = result.rowcount == 1
        if not updated:
            logger.info(
                "Skipped stale progress update task=%s attempt=%s step=%s",
                task_id,
                attempt_number,
                current_step,
            )
        return updated
