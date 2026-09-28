import asyncio
from celery import Celery
from sqlalchemy import select
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.task import ResearchTask
from app.agents.graph import research_graph
from app.agents.state import ResearchState

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
    worker_prefetch_multiplier=1,  # Đảm bảo phân bổ task công bằng
)


async def run_langgraph_workflow(task_id: str) -> dict:
    """Hàm chạy async LangGraph và tương tác với DB."""
    try:
        async with AsyncSessionLocal() as session:
            # 1. Fetch Task Info
            stmt = select(ResearchTask).where(ResearchTask.id == task_id)
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                return {"status": "FAILED", "task_id": task_id, "message": "Task not found in DB"}

            # Cập nhật trạng thái
            task.status = "RUNNING"
            await session.commit()

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

                from app.models.report import ResearchReport
                report = ResearchReport(
                    research_task_id=task.id,
                    title=f"Báo cáo: {task.title}",
                    content_markdown=report_content,
                    word_count=len(report_content.split()),
                )
                session.add(report)
                task.status = "COMPLETED"
                await session.commit()

                return {
                    "status": "SUCCESS",
                    "task_id": task_id,
                    "message": "Workflow completed",
                    "final_agent": final_state.get("current_agent")
                }
            except Exception as e:
                task.status = "FAILED"
                error_msg = f"ERROR: {str(e)}"
                task.description = f"{task.description}\n\n{error_msg}" if task.description else error_msg
                await session.commit()
                raise RuntimeError(f"Research workflow failed for task {task_id}: {e}") from e
    finally:
        from app.core.database import engine
        await engine.dispose()


@celery_app.task(bind=True, name="app.worker.execute_research_workflow")
def execute_research_workflow(self, task_id: str):
    """Task nền thực thi toàn bộ luồng Multi-Agent LangGraph cho một research task."""
    self.update_state(state="PROGRESS", meta={"message": "Khởi tạo LangGraph Engine"})

    # Celery chạy hàm đồng bộ, gọi hàm bất đồng bộ bằng asyncio.run
    result = asyncio.run(run_langgraph_workflow(task_id))

    return result
