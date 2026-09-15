from celery import Celery
from app.core.config import settings

# Khởi tạo Celery Application
celery_app = Celery(
    "ati_research_worker",
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


@celery_app.task(bind=True, name="app.worker.execute_research_workflow")
def execute_research_workflow(self, task_id: str):
    """Task nền thực thi toàn bộ luồng Multi-Agent LangGraph cho một research task."""
    # Sẽ tích hợp LangGraph Compiled Graph tại Phase 2
    return {"status": "SUCCESS", "task_id": task_id, "message": "Workflow engine ready"}
