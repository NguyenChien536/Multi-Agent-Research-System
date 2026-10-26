import uuid
from datetime import datetime
from typing import Optional
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field

class ResearchReportResponse(BaseModel):
    id: uuid.UUID
    research_task_id: uuid.UUID
    title: str
    content_markdown: str
    executive_summary: Optional[str] = None
    review_status: str = "NEEDS_REVIEW"
    review_metadata: Dict[str, Any] = Field(default_factory=dict)
    word_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitationItemResponse(BaseModel):
    id: uuid.UUID
    citation_number: Optional[int] = None
    citation_label: str
    claim_text: Optional[str] = None
    source_id: uuid.UUID
    source_title: Optional[str] = None
    source_url: str
    chunk_id: Optional[uuid.UUID] = None
    chunk_content: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ResearchSourceItemResponse(BaseModel):
    id: uuid.UUID
    source_tag: str
    title: Optional[str] = None
    url: str
    source_type: str = "WEBSITE"
    author: Optional[str] = None
    publication_date: Optional[str] = None
    content_snippet: Optional[str] = None
    summary: Optional[str] = None
    relevance_score: float = 0.0
    ingestion_status: str = "READY"
    ingestion_error: Optional[str] = None
    attribution: Optional[str] = None
    provider_name: Optional[str] = None
    license_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


