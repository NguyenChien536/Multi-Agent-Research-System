import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String(50), nullable=False)  # Supervisor | Researcher | Analyst | Critic | Writer
    status = Column(String(30), default="RUNNING", nullable=False)  # RUNNING | SUCCESS | FAILED
    iteration = Column(Integer, default=0, nullable=False)
    attempt_number = Column(Integer, default=1, nullable=False)  # Retry tracking
    
    # Reproducibility Fields
    model = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    temperature = Column(Float, default=0.2, nullable=False)
    prompt_version = Column(String(50), nullable=True)
    workflow_version = Column(String(50), nullable=True)
    input_hash = Column(String(64), nullable=True)
    
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    
    input_summary = Column(JSONB, default=dict, nullable=False)
    output_summary = Column(JSONB, default=dict, nullable=False)
    tool_calls = Column(JSONB, default=list, nullable=False)
    error_message = Column(Text, nullable=True)
    
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    estimated_cost = Column(Numeric(10, 6), default=0.0, nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="agent_runs")
    evaluations = relationship("Evaluation", back_populates="agent_run")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_task_id = Column(UUID(as_uuid=True), ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    metric = Column(String(50), nullable=False)  # RELEVANCE | GROUNDING | COMPLETENESS | HALLUCINATION | COHERENCE
    score = Column(Float, nullable=False)  # 0.0 - 1.0
    feedback = Column(Text, nullable=True)
    evaluator_type = Column(String(30), default="AUTOMATED_CODE", nullable=False)  # AUTOMATED_CODE | LLM_JUDGE | HUMAN
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    task = relationship("ResearchTask", back_populates="evaluations")
    agent_run = relationship("AgentRun", back_populates="evaluations")
