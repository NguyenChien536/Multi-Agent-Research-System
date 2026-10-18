import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnalysisRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    research_task_id: uuid.UUID
    routine_name: str
    status: str
    dataset_artifact_id: Optional[uuid.UUID] = None
    input_checksum: Optional[str] = None
    manifest: Dict[str, Any] = Field(default_factory=dict)
    metrics: Optional[Dict[str, Any]] = None
    reproducibility_status: str
    reproducibility_diff: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class ExperimentJournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    research_task_id: uuid.UUID
    analysis_run_id: uuid.UUID
    sequence: int
    kind: str
    actor: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    artifact_ids: List[str] = Field(default_factory=list)
    created_at: datetime


class DatasetUploadResponse(BaseModel):
    artifact_id: uuid.UUID
    file_name: str
    rows_count: int
    columns_count: int
    columns: List[str]
    checksum: str
