import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    research_question = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    research_depth = Column(String(20), default="STANDARD", nullable=False)  # SHALLOW | STANDARD | DEEP
    language = Column(String(10), default="vi", nullable=False)
    status = Column(String(30), default="PENDING", nullable=False, index=True)  # PENDING, QUEUED, PLANNING, RESEARCHING, INDEXING, ANALYZING, WRITING, REVIEWING, FINALIZING, COMPLETED, RETRYING, FAILED, CANCELLED
    
    # Resource Limits & Accrual
    max_sources = Column(Integer, default=10, nullable=False)
    max_iterations = Column(Integer, default=2, nullable=False)
    current_iteration = Column(Integer, default=0, nullable=False)
    attempt_number = Column(Integer, default=0, nullable=False)  # Crash recovery counter
    
    budget_config = Column(JSONB, default=dict, nullable=False)  # max_cost_usd, max_llm_calls, max_tokens, timeout_s
    total_cost_usd = Column(Numeric(10, 4), default=0.0, nullable=False)
    total_tokens_used = Column(Integer, default=0, nullable=False)
    
    report_length = Column(String(20), default="MEDIUM", nullable=False)
    citation_style = Column(String(20), default="IEEE", nullable=False)
    
    queued_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="tasks")
    iterations = relationship("ResearchIteration", back_populates="task", cascade="all, delete-orphan", order_by="ResearchIteration.iteration_number")
    sources = relationship("ResearchSource", back_populates="task", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="task", cascade="all, delete-orphan")
    evidences = relationship("Evidence", back_populates="task", cascade="all, delete-orphan")
    claims = relationship("ResearchClaim", back_populates="task", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="task", cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="task", cascade="all, delete-orphan")
    report = relationship("ResearchReport", back_populates="task", uselist=False, cascade="all, delete-orphan")
    artifacts = relationship("ExportArtifact", back_populates="task", cascade="all, delete-orphan")


class ResearchIteration(Base):
    __tablename__ = "research_iterations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    iteration_number = Column(Integer, nullable=False)
    iteration_type = Column(String(30), nullable=False)  # INITIAL | MACRO_LOOP | MICRO_LOOP
    trigger_reason = Column(Text, nullable=True)
    queries_used = Column(JSONB, default=list, nullable=False)
    sources_found = Column(Integer, default=0, nullable=False)
    chunks_indexed = Column(Integer, default=0, nullable=False)
    critic_verdict = Column(String(20), nullable=True)  # PASS | REVISE | NEED_MORE_DATA
    
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    task = relationship("ResearchTask", back_populates="iterations")
