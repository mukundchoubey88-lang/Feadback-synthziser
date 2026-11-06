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

    # Gemini AI Configuration (Architectural placeholder for Part 4)
    GEMINI_API_KEY: Optional[str] = None

    # Hindsight Persistent Memory Configuration (Architectural placeholder for Part 9)
    HINDSIGHT_API_KEY: Optional[str] = None
    HINDSIGHT_BASE_URL: Optional[str] = None

    # Ingestion & Upload Safeguards
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB limit
    MAX_UPLOAD_RECORDS: int = 10000  # Maximum records per batch
    MAX_FEEDBACK_TEXT_LENGTH: int = 10000  # Character ceiling for raw feedback text

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:5173"

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

    @field_validator("GEMINI_API_KEY", "HINDSIGHT_API_KEY", "HINDSIGHT_BASE_URL", mode="before")
    @classmethod
    def sanitize_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str) and not v.strip():
            return None
        return v


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
