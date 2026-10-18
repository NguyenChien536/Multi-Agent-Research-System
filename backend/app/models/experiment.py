import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    routine_name = Column(String(100), default="tabular_regression_v1", nullable=False)
    status = Column(String(30), default="STARTED", nullable=False)  # STARTED, COMPLETED, FAILED
    dataset_artifact_id = Column(UUID(as_uuid=True), ForeignKey("export_artifacts.id", ondelete="SET NULL"), nullable=True)
    input_checksum = Column(String(64), nullable=True)
    manifest = Column(JSONB, default=dict, nullable=False)
    metrics = Column(JSONB, nullable=True)
    reproducibility_status = Column(String(30), default="NOT_RUN", nullable=False)  # NOT_RUN, PASSED, FAILED
    reproducibility_diff = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    task = relationship("ResearchTask", back_populates="analysis_runs")
    dataset_artifact = relationship("ExportArtifact", foreign_keys=[dataset_artifact_id])
    journal_entries = relationship(
        "ExperimentJournalEntry",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        order_by="ExperimentJournalEntry.sequence",
    )


class ExperimentJournalEntry(Base):
    __tablename__ = "experiment_journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_run_id = Column(UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    kind = Column(String(50), nullable=False)  # PLAN_FROZEN, STARTED, EXECUTION_RESULT, OBSERVATION, INTERPRETATION, REPRODUCTION_CHECK
    actor = Column(String(50), nullable=False)  # SYSTEM, METHODOLOGIST, DATA_ANALYST, WRITER, USER
    payload = Column(JSONB, default=dict, nullable=False)
    artifact_ids = Column(JSONB, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("analysis_run_id", "sequence", name="uq_journal_run_sequence"),
    )

    # Relationships
    task = relationship("ResearchTask", back_populates="journal_entries")
    analysis_run = relationship("AnalysisRun", back_populates="journal_entries")
