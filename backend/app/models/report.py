import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content_markdown = Column(Text, nullable=False)
    executive_summary = Column(Text, nullable=True)
    word_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="report")
    citations = relationship("Citation", back_populates="report", cascade="all, delete-orphan")


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
    task = relationship("ResearchTask", back_populates="artifacts")
