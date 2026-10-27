from typing import List, Union, Optional
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Synthia — Multi-Agent Research System"
    VERSION: str = "2.2.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    MOCK_PROVIDERS: bool = False  # If True, bypass real LLM/Search API calls for tests

    # Security
    APP_SECRET_KEY: str = "development-secret-key-replace-in-production-32-chars-min"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database & Vector Store
    DATABASE_URL: str = "postgresql+asyncpg://research_user:research_secure_password@localhost:5432/research_db"
    POSTGRES_SYNC_URL: str = "postgresql://research_user:research_secure_password@localhost:5432/research_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    #Celetry
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AI Model Providers & Keys
    TAVILY_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    
    # Priority Config (Comma-separated)
    LLM_PROVIDER_PRIORITY: str = "gemini,openai,anthropic,groq"
    EMBEDDING_PROVIDER_PRIORITY: str = "gemini,openai"

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # LLM Observability (LangSmith)
    LANGSMITH_TRACING: bool = False
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_API_KEY: str | None = None
    LANGSMITH_PROJECT: str = "multi-agent-research-system"

    # Quotas & Guardrails
    MAX_CONCURRENT_TASKS_PER_USER: int = 2
    OUTBOX_POLL_SECONDS: float = 1.0
    OUTBOX_LOCK_SECONDS: int = 30
    OUTBOX_RETRY_SECONDS: int = 2
    OUTBOX_MAX_RETRY_SECONDS: int = 60
    OUTBOX_DISPATCH_ACK_TIMEOUT_SECONDS: int = 300
    OUTBOX_AUTO_RECOVERY_MAX_AGE_SECONDS: int = 86400
    OUTBOX_MAX_UNCLAIMED_RETRIES: int = 5
    WORKER_LEASE_SECONDS: int = 300
    WORKER_HEARTBEAT_SECONDS: int = 30
    WORKER_MAX_RECOVERIES: int = 3
    PROVIDER_CALL_TIMEOUT_SECONDS: int = 90
    DEFAULT_BUDGET_USD: float = 2.00
    DEFAULT_MAX_LLM_CALLS: int = 40
    DEFAULT_MAX_INPUT_TOKENS: int = 100000
    DEFAULT_MAX_OUTPUT_TOKENS: int = 50000
    DEFAULT_TIMEOUT_SECONDS: int = 900
    # Conservative per-request estimate used when reserving Tavily search budget.
    TAVILY_REQUEST_COST_USD: float = 0.01

    # Artifact Storage & Upload Limits (SRS FR-02 & P3)
    ARTIFACTS_DIR: str = "storage/artifacts"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MiB per file
    MAX_PDF_PAGES: int = 100  # Max 100 pages per file
    MAX_UPLOAD_FILES_PER_TASK: int = 5  # Max 5 files per task

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def sync_postgres_url(self) -> "Settings":
        if (
            self.POSTGRES_SYNC_URL == "postgresql://research_user:research_secure_password@localhost:5432/research_db"
            and self.DATABASE_URL != "postgresql+asyncpg://research_user:research_secure_password@localhost:5432/research_db"
        ):
            self.POSTGRES_SYNC_URL = self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        return self

    @model_validator(mode="after")
    def require_production_secret(self) -> "Settings":
        if self.ENVIRONMENT != "development" and (
            len(self.APP_SECRET_KEY) < 32
            or self.APP_SECRET_KEY in {
                "development-secret-key-replace-in-production-32-chars-min",
                "replace-with-a-secure-random-secret-key-32-chars-min",
            }
        ):
            raise ValueError("APP_SECRET_KEY must be a unique secret of at least 32 characters outside development")
        return self



settings = Settings()
