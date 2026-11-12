"""Private, run-scoped completed work; never a shared prompt/credential cache."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class ProviderResult(Base):
    __tablename__ = 'provider_results'
    __table_args__ = (UniqueConstraint('workflow_run_id', 'operation', 'input_hash', name='uq_provider_result_unit'),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey('research_tasks.id', ondelete='CASCADE'), nullable=False, index=True)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False)
    operation = Column(String(80), nullable=False)
    input_hash = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
