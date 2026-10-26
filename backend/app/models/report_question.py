import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class ReportQuestion(Base):
    """A bounded, idempotent question pinned to one immutable article version."""
    __tablename__ = "report_questions"
    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_report_question_request"),
        Index("uq_report_question_active_user", "user_id", unique=True,
              postgresql_where=text("status = 'RUNNING'")),
        Index("ix_report_questions_version_created", "report_version_id", "created_at", "id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_version_id = Column(UUID(as_uuid=True), ForeignKey("report_versions.id", ondelete="CASCADE"), nullable=False)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    question = Column(Text, nullable=False)
    status = Column(String(30), nullable=False)
    answer = Column(Text, nullable=True)
    references = Column(JSONB, default=list, nullable=False)
    context_hash = Column(String(64), nullable=True)
    context_truncated = Column(Boolean, default=False, nullable=False)
    error_code = Column(String(40), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
