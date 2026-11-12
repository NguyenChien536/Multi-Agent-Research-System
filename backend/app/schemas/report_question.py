import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportQuestionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: uuid.UUID
    question: str = Field(min_length=3, max_length=2000)


class AnswerReference(BaseModel):
    citation_id: uuid.UUID
    source_title: str | None = None
    source_url: str
    quote: str


class ReportQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    report_version_id: uuid.UUID
    request_id: uuid.UUID
    question: str
    status: str
    answer: str | None
    references: list[AnswerReference]
    context_truncated: bool
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class ReportQuestionHistory(BaseModel):
    report_version_id: uuid.UUID
    version_number: int
    items: list[ReportQuestionResponse]
    total: int
    offset: int
    limit: int
