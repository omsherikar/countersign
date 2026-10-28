"""Settings for the mockgov service.

Every value comes from the environment (compose loads .env). Keys that belong to other
services in the same .env are ignored.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    postgres_user: str = "countersign"
    postgres_password: str = "countersign"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    mockgov_db_name: str = "mockgov"

    # Chaos defaults applied to every source at startup and on reset.
    mockgov_latency_ms: int = 0
    mockgov_fail_rate: float = 0.0

    def database_url(self, db_name: str | None = None) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{db_name or self.mockgov_db_name}"
        )

    def asyncpg_dsn(self, db_name: str | None = None) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{db_name or self.mockgov_db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
