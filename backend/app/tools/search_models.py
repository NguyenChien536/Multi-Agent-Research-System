from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    content: str = ""
    score: float = Field(default=0.0)
    published_date: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    doi: Optional[str] = None
    venue: Optional[str] = None
    source_type: str = "WEBSITE"
    provider: str = "web"
    query: Optional[str] = None
    matched_queries: list[str] = Field(default_factory=list)
    full_text_url: Optional[HttpUrl] = None
