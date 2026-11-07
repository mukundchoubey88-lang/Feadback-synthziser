from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Core Application Settings
    APP_NAME: str = "Feedback Intelligence API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # Database Configuration (PostgreSQL with psycopg v3)
    DATABASE_URL: Optional[str] = None

    # AI Provider Settings (Part 5.1 Multi-Provider Failover)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "google/gemini-2.0-flash-001"
    OPENROUTER_FALLBACK_MODELS: str = "anthropic/claude-3.5-haiku,meta-llama/llama-3.3-70b-instruct"

    XAI_API_KEY: Optional[str] = None
    XAI_MODEL: str = "grok-4.7"

    AI_PRIMARY_PROVIDER: str = "gemini"
    AI_PROVIDER_FALLBACK_ENABLED: bool = True
    AI_PROVIDER_PRIORITY: str = "gemini,openrouter,grok"

    AI_REQUEST_TIMEOUT: float = 30.0
    AI_PROVIDER_MAX_RETRIES: int = 2
    AI_PROVIDER_COOLDOWN_SECONDS: int = 60

    # AI Embedding Provider Settings (Part 7)
    AI_EMBEDDING_PROVIDER: str = "gemini"
    AI_EMBEDDING_MODEL: str = "gemini-embedding-2"
    AI_EMBEDDING_DIMENSIONS: int = 768
    AI_EMBEDDING_TIMEOUT: float = 30.0
    AI_EMBEDDING_MAX_RETRIES: int = 2

    # Theme Clustering Configuration (Part 7 Step 4)
    THEME_CLUSTERING_SIMILARITY_THRESHOLD: float = 0.80
    THEME_CLUSTERING_MIN_CLUSTER_SIZE: int = 3
    THEME_CLUSTERING_MAX_BATCH_SIZE: int = 150
    THEME_CLUSTERING_REPRESENTATIVE_COUNT: int = 3

    # Hindsight Persistent Memory Configuration (Architectural placeholder for Part 9)
    HINDSIGHT_API_KEY: Optional[str] = None
    HINDSIGHT_BASE_URL: Optional[str] = None

    # Ingestion & Upload Safeguards
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
    MAX_UPLOAD_RECORDS: int = 10000  # Maximum records per batch
    MAX_FEEDBACK_TEXT_LENGTH: int = 10000  # Character ceiling for raw feedback text
    MAX_CLASSIFICATION_BATCH_SIZE: int = 50  # Bounded batch size for AI classification

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def ai_provider_priority_list(self) -> List[str]:
        """Ordered list of AI provider names based on priority."""
        if not self.AI_PROVIDER_PRIORITY:
            return ["gemini", "openrouter", "grok"]
        return [p.strip().lower() for p in self.AI_PROVIDER_PRIORITY.split(",") if p.strip()]

    @property
    def openrouter_fallback_models_list(self) -> List[str]:
        """Parsed list of approved fallback models for OpenRouter."""
        if not self.OPENROUTER_FALLBACK_MODELS:
            return []
        return [m.strip() for m in self.OPENROUTER_FALLBACK_MODELS.split(",") if m.strip()]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS_ORIGINS into a clean list of origins."""
        if not self.CORS_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator(
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "XAI_API_KEY",
        "HINDSIGHT_API_KEY",
        "HINDSIGHT_BASE_URL",
        mode="before",
    )
    @classmethod
    def sanitize_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("THEME_CLUSTERING_SIMILARITY_THRESHOLD")
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        if not (0.0 < v <= 1.0):
            raise ValueError("THEME_CLUSTERING_SIMILARITY_THRESHOLD must be between 0.0 (exclusive) and 1.0 (inclusive)")
        return v

    @field_validator("THEME_CLUSTERING_MIN_CLUSTER_SIZE")
    @classmethod
    def validate_min_cluster_size(cls, v: int) -> int:
        if v < 2:
            raise ValueError("THEME_CLUSTERING_MIN_CLUSTER_SIZE must be at least 2")
        return v

    @field_validator("THEME_CLUSTERING_MAX_BATCH_SIZE")
    @classmethod
    def validate_max_batch_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("THEME_CLUSTERING_MAX_BATCH_SIZE must be positive")
        return v

    @field_validator("THEME_CLUSTERING_REPRESENTATIVE_COUNT")
    @classmethod
    def validate_representative_count(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("THEME_CLUSTERING_REPRESENTATIVE_COUNT must be positive")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
