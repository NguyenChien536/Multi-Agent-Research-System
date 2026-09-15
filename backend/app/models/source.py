import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_tag = Column(String(20), nullable=False)  # src_01, src_02...
    title = Column(String(500), nullable=True)
    url = Column(Text, nullable=False)
    source_type = Column(String(50), default="WEBSITE", nullable=False)  # ARTICLE, PAPER, NEWS, OFFICIAL, WEBSITE
    author = Column(String(255), nullable=True)
    publication_date = Column(String(50), nullable=True)
    content_snippet = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    relevance_score = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="sources")
    chunks = relationship("DocumentChunk", back_populates="source", cascade="all, delete-orphan")
    evidences = relationship("Evidence", back_populates="source", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="source", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("research_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    vector_id = Column(String(100), nullable=True)  # Qdrant or internal vector ID
    embedding = Column(Vector(1536), nullable=True)  # text-embedding-3-small dimension
    token_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="chunks")
    source = relationship("ResearchSource", back_populates="chunks")
    evidences = relationship("Evidence", back_populates="chunk", cascade="all, delete-orphan")
