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
