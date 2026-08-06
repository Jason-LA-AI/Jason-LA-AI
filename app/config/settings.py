"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
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
    site_url: str = "http://127.0.0.1:8000"
    allowed_hosts: str = "127.0.0.1,localhost,testserver"
    phone_number: str | None = None
    email_address: str | None = None
    telegram_username: str | None = None
    xiaohongshu_url: str | None = None
    facebook_url: str | None = None
    dashboard_username: str | None = Field(default=None, repr=False)
    dashboard_password: str | None = Field(default=None, repr=False)
    telegram_bot_token: str | None = Field(default=None, repr=False)
    telegram_chat_id: str | None = Field(default=None, repr=False)
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

    @property
    def is_production(self) -> bool:
        return self.app_environment.lower() == "production"

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return one settings instance for the running process."""
    return Settings()


settings = get_settings()
