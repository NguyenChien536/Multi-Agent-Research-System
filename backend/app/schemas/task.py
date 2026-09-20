import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class BudgetConfigSchema(BaseModel):
    max_cost_usd: float = Field(default=2.00, ge=0.1, le=20.0)
    max_llm_calls: int = Field(default=50, ge=5, le=200)
    max_input_tokens: int = Field(default=100000, ge=10000)
    max_output_tokens: int = Field(default=50000, ge=5000)
    timeout_seconds: int = Field(default=300, ge=60, le=1800)


class ResearchTaskCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    research_question: str = Field(..., min_length=10)
    description: Optional[str] = None
    research_depth: str = Field(default="STANDARD", pattern="^(SHALLOW|STANDARD|DEEP)$")
    language: str = Field(default="vi", max_length=10)
    require_plan_approval: bool = Field(default=False, description="Enable Human-in-the-Loop plan review")
    max_sources: int = Field(default=10, ge=3, le=30)
    max_iterations: int = Field(default=2, ge=1, le=3)
    report_length: str = Field(default="MEDIUM", pattern="^(SHORT|MEDIUM|LONG)$")
    citation_style: str = Field(default="IEEE", pattern="^(IEEE|APA|HARVARD)$")
    budget: Optional[BudgetConfigSchema] = None


class ResearchTaskResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    research_question: str
    research_depth: str
    language: str
    status: str
    require_plan_approval: bool
    max_sources: int
    max_iterations: int
    current_iteration: int
    attempt_number: int
    total_cost_usd: float
    total_tokens_used: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
