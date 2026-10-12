import asyncio
import logging
from datetime import datetime, timedelta, timezone
from celery import Celery
from sqlalchemy import func, select, update
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask, TaskDispatchOutbox
from app.models.user import User
from app.agents.graph import research_graph
from app.agents.state import ResearchState

logger = logging.getLogger(__name__)

# Khởi tạo Celery Application
celery_app = Celery(
    "research_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Cấu hình Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Idempotency & Worker Crash Protection
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 360},
    worker_prefetch_multiplier=1,  # Đảm bảo phân bổ task công bằng
)


async def renew_worker_lease(task_id: str, attempt_number: int) -> None:
    """Renew the active claim so the API dispatcher can recover dead workers."""
    while True:
        await asyncio.sleep(settings.WORKER_HEARTBEAT_SECONDS)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(ResearchTask)
                .where(
                    ResearchTask.id == task_id,
                    ResearchTask.status == "RUNNING",
                    ResearchTask.attempt_number == attempt_number,
                )
                .values(worker_lease_until=datetime.now(timezone.utc) + timedelta(seconds=settings.WORKER_LEASE_SECONDS))
            )
            await session.commit()
            if result.rowcount != 1:
                return


async def run_langgraph_workflow(task_id: str) -> dict:
    """Hàm chạy async LangGraph và tương tác với DB."""
    heartbeat: asyncio.Task | None = None
    try:
        async with AsyncSessionLocal() as session:
            # Claim only a queued task. A duplicate Celery delivery is acknowledged
            # without starting another graph run or creating another report.
            result = await session.execute(
                select(ResearchTask)
                .where(ResearchTask.id == task_id)
                .with_for_update()
            )
            task = result.scalar_one_or_none()
            if not task:
                return {"status": "FAILED", "task_id": task_id, "message": "Task not found in DB"}
            if task.status != "QUEUED":
                return {"status": "IGNORED", "task_id": task_id, "message": f"Task is {task.status}"}

            # Atomically serialize capacity checks for this user across concurrent workers.
            if task.user_id:
                await session.execute(
                    select(User.id)
                    .where(User.id == task.user_id)
                    .with_for_update()
                )

            # Enforce the per-user running job limit.
            # Queued and WAITING_* states do not consume running slots.
            active_count_res = await session.execute(
                select(func.count(ResearchTask.id))
                .where(
                    ResearchTask.user_id == task.user_id,
                    ResearchTask.status == "RUNNING",
                )
            )
            active_count = active_count_res.scalar_one()
            if active_count >= settings.MAX_CONCURRENT_TASKS_PER_USER:
                # User has reached concurrent running job limit.
                # Task remains QUEUED; reset outbox event so it is dispatched when capacity frees.
                event_result = await session.execute(
                    select(TaskDispatchOutbox)
                    .where(
                        TaskDispatchOutbox.research_task_id == task.id,
                        TaskDispatchOutbox.event_type == "START_RESEARCH",
                    )
                    .with_for_update()
                )
                outbox_event = event_result.scalar_one_or_none()
                if outbox_event is not None:
                    outbox_event.dispatched_at = None
                    outbox_event.available_at = datetime.now(timezone.utc)
                    outbox_event.locked_until = None
                    outbox_event.last_error = "User at concurrent running job limit; waiting for capacity"
                await session.commit()
                return {
                    "status": "QUEUED",
                    "task_id": task_id,
                    "message": "User has reached concurrent running job limit; task remains QUEUED",
                }

            task.status = "RUNNING"
            task.attempt_number += 1
            task.worker_lease_until = datetime.now(timezone.utc) + timedelta(seconds=settings.WORKER_LEASE_SECONDS)
            claim_attempt = task.attempt_number
            user_id = task.user_id
            await session.commit()
            heartbeat = asyncio.create_task(renew_worker_lease(task_id, claim_attempt))

            # 2. Khởi tạo State ban đầu
            initial_state = {
                "task_id": str(task.id),
                "user_id": str(task.user_id) if task.user_id else "anonymous",
                "research_question": task.research_question,
                "research_depth": task.research_depth,
                "language": task.language,
                "status": "RUNNING",
                "require_plan_approval": task.require_plan_approval,
                "current_iteration": task.current_iteration,
                "current_micro_revision": 0,
                "max_iterations": task.max_iterations,
                "max_micro_revisions": 2,
                "attempt_number": task.attempt_number,
            }

            # 3. Kích hoạt (Invoke) Graph
            try:
                final_state = await research_graph.ainvoke(initial_state)
                report_content = final_state.get("final_report_markdown") if final_state else None
                if not report_content:
                    raise RuntimeError("Research graph completed without producing a report")

                await session.refresh(task)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}

                from app.models.report import ResearchReport
                report = ResearchReport(
                    research_task_id=task.id,
                    title=f"Báo cáo: {task.title}",
                    content_markdown=report_content,
                    word_count=len(report_content.split()),
                )
                session.add(report)
                task.status = "COMPLETED"
                task.worker_lease_until = None
                await session.commit()

                try:
                    from app.services.task_dispatcher import dispatch_one_outbox_event
                    await dispatch_one_outbox_event(user_id=user_id)
                except Exception as dispatch_err:
                    logger.warning("Failed to dispatch next queued task after completion: %s", dispatch_err)

                return {
                    "status": "SUCCESS",
                    "task_id": task_id,
                    "message": "Workflow completed",
                    "final_agent": final_state.get("current_agent")
                }
            except Exception as e:
                await session.refresh(task)
                if task.status != "RUNNING" or task.attempt_number != claim_attempt:
                    return {"status": "SUPERSEDED", "task_id": task_id}
                task.status = "FAILED"
                task.worker_lease_until = None
                error_msg = f"ERROR: {str(e)}"
                task.description = f"{task.description}\n\n{error_msg}" if task.description else error_msg
                await session.commit()

                try:
                    from app.services.task_dispatcher import dispatch_one_outbox_event
                    await dispatch_one_outbox_event(user_id=user_id)
                except Exception as dispatch_err:
                    logger.warning("Failed to dispatch next queued task after failure: %s", dispatch_err)

                raise RuntimeError(f"Research workflow failed for task {task_id}: {e}") from e
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass


@celery_app.task(bind=True, name="app.worker.execute_research_workflow")
def execute_research_workflow(self, task_id: str):
    """Task nền thực thi toàn bộ luồng Multi-Agent LangGraph cho một research task."""
    self.update_state(state="PROGRESS", meta={"message": "Khởi tạo LangGraph Engine"})

    # Celery chạy hàm đồng bộ, gọi hàm bất đồng bộ bằng asyncio.run
    result = asyncio.run(run_langgraph_workflow(task_id))

    return result
