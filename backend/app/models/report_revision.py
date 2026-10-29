import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ReportRevision(Base):
    """Durable, idempotent editorial request pinned to an immutable base report."""
    __tablename__ = "report_revisions"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_report_revision_request"),
        Index("uq_report_revision_active_task", "research_task_id", unique=True,
              postgresql_where=text("status IN ('QUEUED', 'RUNNING')")),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    base_version_id = Column(UUID(as_uuid=True), ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    instructions = Column(Text, nullable=False)
    status = Column(String(30), default="QUEUED", nullable=False)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    result_version_id = Column(UUID(as_uuid=True), ForeignKey("report_versions.id", ondelete="SET NULL"), nullable=True)
    error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
