import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ArtifactItemResponse(BaseModel):
    id: uuid.UUID
    research_task_id: uuid.UUID
    export_type: str
    file_path: str
    file_size_bytes: int
    download_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PdfUploadResponse(BaseModel):
    artifact_id: uuid.UUID
    source_id: uuid.UUID
    source_tag: str
    file_name: str
    file_size_bytes: int
    page_count: int
    chunks_count: int
    sha256_hash: str
    message: str

    model_config = ConfigDict(from_attributes=True)


class FieldworkUploadResponse(BaseModel):
    artifact_id: uuid.UUID
    file_name: str
    file_size_bytes: int
    sha256_hash: str
