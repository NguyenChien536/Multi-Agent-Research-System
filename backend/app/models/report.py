import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResearchReport(Base):
    """Stable identity for one task's versioned research report."""
    __tablename__ = "research_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="report")
    citations = relationship(
        "Citation",
        back_populates="report",
        foreign_keys="Citation.report_id",
        cascade="all, delete-orphan",
    )
    versions = relationship("ReportVersion", back_populates="report", cascade="all, delete-orphan", order_by="ReportVersion.version_number")


class ReportVersion(Base):
    """Immutable snapshot of one report version and its producing workflow run."""
    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_report_version_number"),
        UniqueConstraint("report_id", "workflow_run_id", name="uq_report_version_workflow_run"),
        UniqueConstraint("id", "report_id", name="uq_report_version_id_report"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("research_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    plan_version = Column(Integer, nullable=True)
    title = Column(String(255), nullable=False)
    content_markdown = Column(Text, nullable=False)
    executive_summary = Column(Text, nullable=True)
    review_status = Column(String(30), default="NEEDS_REVIEW", nullable=False)
    review_metadata = Column(JSONB, default=dict, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    report = relationship("ResearchReport", back_populates="versions")
    citations = relationship(
        "Citation",
        back_populates="report_version",
        foreign_keys="Citation.report_version_id",
        cascade="all, delete-orphan",
    )


class ExportArtifact(Base):
    __tablename__ = "export_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    export_type = Column(String(20), default="PDF", nullable=False)  # PDF | DOCX | HTML
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    download_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="artifacts", foreign_keys=[research_task_id])
