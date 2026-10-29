import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ReportRevisionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: uuid.UUID
    instructions: str = Field(min_length=10, max_length=4000)


class ReportRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    request_id: uuid.UUID
    base_version_id: uuid.UUID
    instructions: str
    status: str
    workflow_run_id: uuid.UUID | None = None
    result_version_id: uuid.UUID | None = None
    error_code: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
