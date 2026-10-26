"""Public research progress: operational facts, never raw prompts or errors."""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class MonitorActivity(BaseModel):
    id: uuid.UUID
    agent: str
    status: str
    iteration: int
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int
    output: dict[str, int | str | bool] = Field(default_factory=dict)
    has_error: bool


class MonitorWorkflow(BaseModel):
    id: uuid.UUID
    run_number: int
    status: str
    plan_version: int
    started_at: datetime
    completed_at: datetime | None


class ResearchMonitorResponse(BaseModel):
    task_id: uuid.UUID
    title: str
    research_type: str
    status: str
    current_step: str | None
    current_iteration: int
    attempt_number: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    observed_at: datetime
    worker_lease_expired: bool | None
    next_action: str
    workflow: MonitorWorkflow | None
    counts: dict[str, int]
    estimated_cost_usd: float
    reserved_cost_usd: float
    recorded_tokens: int
    accounting_source: str
    activities: list[MonitorActivity]
    activity_total: int
    activity_offset: int
    activity_limit: int
