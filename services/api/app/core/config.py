"""Settings. Every key here has a line in the repo's .env.example."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_HERE = Path(__file__).resolve().parent.parent.parent  # services/api


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    # Postgres
    postgres_user: str = "countersign"
    postgres_password: str = "countersign"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    api_db_name: str = "countersign"
    api_test_db_name: str = "countersign_test"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"

    # API
    api_secret_key: str = "change-me-32-bytes-minimum-for-jwt-signing"
    api_access_token_minutes: int = 120
    pii_hmac_key: str = "00" * 32
    pii_fernet_key: str = "Zm9yLWRlbW8tb25seS1yZXBsYWNlLW1lLXBsZWFzZS0wMDA="
    cors_origins: list[str] = ["http://localhost:3000"]
    web_base_url: str = "http://localhost:3000"
    cookie_secure: bool = False
    api_version: str = "0.1.0"
    academic_year: str = "2026-27"
    rules_path: str = "./rules.yaml"
    auto_migrate: bool = True
    rate_limits_enabled: bool = True
    log_level: str = "INFO"

    # Government adapters
    gov_adapter: Literal["inmemory", "mockgov", "real"] = "mockgov"
    mockgov_base_url: str = "http://mockgov:8001"
    allow_real_gov_apis: bool = False
    gov_timeout_seconds: float = 3.0

    # Mail
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    mail_from: str = "notices@countersign.demo"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    def database_url(self, db_name: str | None = None) -> str:
        name = db_name or self.api_db_name
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{name}"
        )

    def resolved_rules_path(self) -> Path:
        """RULES_PATH, falling back to the repo root copy for local runs."""
        candidates = [Path(self.rules_path), _HERE.parent.parent / "rules.yaml"]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise FileNotFoundError(f"rules.yaml not found; tried {[str(c) for c in candidates]}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
