"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Validated settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=LOCAL_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Jason-LA-AI"
    app_version: str = "0.1.0"
    app_environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/jason_la_ai",
        repr=False,
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgresql_driver(cls, value: object) -> object:
        """Use the installed Psycopg 3 driver for common hosted URLs."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the running process."""
    return Settings()


settings = get_settings()
