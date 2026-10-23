import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


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
    research_type: str = Field(default="REVIEW", pattern="^(REVIEW|EMPIRICAL_COMPUTATIONAL|EMPIRICAL_HUMAN)$")
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
    description: Optional[str] = None
    research_question: str
    research_type: str = "REVIEW"
    research_depth: str
    language: str
    status: str
    current_step: Optional[str] = None
    require_plan_approval: bool
    max_sources: int
    max_iterations: int
    current_iteration: int
    attempt_number: int
    report_length: str = "MEDIUM"
    citation_style: str = "IEEE"
    total_cost_usd: float
    total_tokens_used: int
    plan: Optional[Dict[str, Any]] = None
    plan_approved: bool = False
    plan_feedback: Optional[str] = None
    protocol_artifact_id: Optional[uuid.UUID] = None
    user_data_submission: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PlanReviewResponse(BaseModel):
    task_id: uuid.UUID
    status: str
    require_plan_approval: bool
    plan_approved: bool
    plan: Optional[Dict[str, Any]] = None
    plan_feedback: Optional[str] = None


class PlanApprovalRequest(BaseModel):
    approved_queries: Optional[List[str]] = Field(default=None, description="Optional updated or curated search queries")
    feedback: Optional[str] = Field(default=None, description="Optional feedback notes for the research run")


class PlanRejectRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Reason for rejection or requested changes")


class UserDataResumeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sample_size: int = Field(..., ge=1, description="Sample size or observation count from fieldwork/lab")
    method_notes: str = Field(..., min_length=10, max_length=5000, description="Fieldwork/lab execution notes and procedure")
    results_summary: str = Field(..., min_length=10, max_length=20000, description="Summary of collected observations, metrics, or raw results")
    data_provenance: str = Field(..., min_length=10, max_length=2000, description="Data origin, collection date and responsible researcher")
    file_artifact_id: uuid.UUID = Field(..., description="Validated result file belonging to this research task")


class ProtocolResponse(BaseModel):
    task_id: uuid.UUID
    research_type: str
    status: str
    protocol_artifact_id: Optional[uuid.UUID] = None
    download_url: Optional[str] = None
    content_markdown: Optional[str] = None
