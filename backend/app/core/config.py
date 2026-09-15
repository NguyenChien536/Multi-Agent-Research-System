from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "MultiAgent Research System (ATI)"
    VERSION: str = "2.2.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    APP_SECRET_KEY: str = "development-secret-key-replace-in-production-32-chars-min"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database & Vector Store
    DATABASE_URL: str = "postgresql+asyncpg://ati_user:ati_secure_password@localhost:5432/ati_research_db"
    POSTGRES_SYNC_URL: str = "postgresql://ati_user:ati_secure_password@localhost:5432/ati_research_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Model Providers & Keys
    TAVILY_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # LLM Observability (LangSmith)
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "ati-multiagent-research"

    # Quotas & Guardrails
    MAX_CONCURRENT_TASKS_PER_USER: int = 2
    DEFAULT_BUDGET_USD: float = 2.00
    DEFAULT_MAX_LLM_CALLS: int = 50
    DEFAULT_MAX_INPUT_TOKENS: int = 100000
    DEFAULT_MAX_OUTPUT_TOKENS: int = 50000
    DEFAULT_TIMEOUT_SECONDS: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
