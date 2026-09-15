import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


class Evidence(Base):
    __tablename__ = "evidences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)  # Exact quote / statistic from chunk
    evidence_type = Column(String(30), default="FACT", nullable=False)  # STATISTIC | QUOTE | FACT | OPINION
    confidence_score = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="evidences")
    source = relationship("ResearchSource", back_populates="evidences")
    chunk = relationship("DocumentChunk", back_populates="evidences")


class ResearchClaim(Base):
    __tablename__ = "research_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(30), default="KEY_FINDING", nullable=False)  # KEY_FINDING | CONTRADICTION | LIMITATION
    evidence_ids = Column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="claims")
    citations = relationship("Citation", back_populates="claim")


class Citation(Base):
    __tablename__ = "citations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("research_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("research_claims.id", ondelete="SET NULL"), nullable=True, index=True)
    citation_label = Column(String(20), nullable=False)  # [1], [2]...
    claim_text = Column(Text, nullable=True)
    chunk_reference = Column(String(100), nullable=True)

    # Relationships
    report = relationship("ResearchReport", back_populates="citations")
    source = relationship("ResearchSource", back_populates="citations")
    claim = relationship("ResearchClaim", back_populates="citations")
