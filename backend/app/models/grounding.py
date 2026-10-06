import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ClaimEvidence(Base):
    """Junction table: ResearchClaim ↔ Evidence.
    Replaces the evidence_ids UUID[] array on ResearchClaim.
    Migration: a1b2c3d4e5f6
    """

    __tablename__ = "claim_evidences"

    claim_id = Column(
        UUID(as_uuid=True),
        ForeignKey("research_claims.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidences.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    relevance_score = Column(Float, nullable=True)  # 0.0–1.0, assigned by Analyst agent

    # Relationships
    claim = relationship("ResearchClaim", back_populates="claim_evidences")
    evidence = relationship("Evidence", back_populates="claim_evidences")


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
    claim_evidences = relationship("ClaimEvidence", back_populates="evidence", cascade="all, delete-orphan")


class ResearchClaim(Base):
    __tablename__ = "research_claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(30), default="KEY_FINDING", nullable=False)  # KEY_FINDING | CONTRADICTION | LIMITATION
    # evidence_ids (UUID[]) removed — replaced by ClaimEvidence junction table (migration a1b2c3d4e5f6)
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="claims")
    citations = relationship("Citation", back_populates="claim")
    claim_evidences = relationship("ClaimEvidence", back_populates="claim", cascade="all, delete-orphan")

    @property
    def evidences(self):
        """Convenience accessor: returns Evidence objects via ClaimEvidence junction."""
        return [ce.evidence for ce in self.claim_evidences]


class Citation(Base):
    __tablename__ = "citations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("research_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id = Column(UUID(as_uuid=True), ForeignKey("research_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,   # populated by Writer agent; replaces chunk_reference string
        index=True,
    )
    claim_id = Column(UUID(as_uuid=True), ForeignKey("research_claims.id", ondelete="SET NULL"), nullable=True, index=True)
    citation_number = Column(Integer, nullable=True)    # Sequential number within report: 1, 2, 3...
    citation_label = Column(String(20), nullable=False)  # Backward compat: retain until report writer migrates
    claim_text = Column(Text, nullable=True)
    chunk_reference = Column(String(100), nullable=True)  # DEPRECATED — use chunk_id FK; drop after Writer is updated

    # Relationships
    task = relationship("ResearchTask", foreign_keys=[research_task_id])
    report = relationship("ResearchReport", back_populates="citations")
    source = relationship("ResearchSource", back_populates="citations")
    chunk = relationship("DocumentChunk", foreign_keys=[chunk_id])
    claim = relationship("ResearchClaim", back_populates="citations")
