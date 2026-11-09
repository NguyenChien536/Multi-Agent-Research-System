"""Write-only credential update contracts."""
import uuid
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Literal

class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    api_key: SecretStr | None = Field(default=None, min_length=8, max_length=4096, repr=False)
    base_url: str
    model: str
    input_price_per_million: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    output_price_per_million: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    output_token_limit: int = Field(default=32768, ge=1024, le=1_000_000)
    reasoning_effort: Literal['none', 'low', 'medium', 'high'] = 'low'
    structured_output_mode: Literal['json_object', 'json_schema'] = 'json_object'


class ModelCatalogRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    base_url: str = Field(min_length=8, max_length=500)
    api_key: SecretStr | None = Field(default=None, min_length=8, max_length=4096, repr=False)
    task_id: uuid.UUID | None = None
    free_only: bool = True
