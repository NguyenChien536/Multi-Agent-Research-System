import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ResearchReportResponse(BaseModel):
    id: uuid.UUID
    research_task_id: uuid.UUID
    title: str
    content_markdown: str
    executive_summary: Optional[str] = None
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

