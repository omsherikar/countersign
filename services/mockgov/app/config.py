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

    # The simulated DigiLocker sign-in (OAuth code flow, id token signed HS256 with the
    # client secret). The api reads the same DIGILOCKER_* values from .env.
    digilocker_client_id: str = "countersign-demo"
    digilocker_client_secret: str = "countersign-demo-digilocker-client-secret"
    digilocker_issuer: str = "http://localhost:8001/digilocker"
    # Comma-separated redirect URIs the client may use, matched exactly.
    digilocker_redirect_uris: str = "http://localhost:3000/api/auth/digilocker/callback"
    digilocker_code_ttl_seconds: int = 60
    digilocker_token_ttl_seconds: int = 600

    def digilocker_redirects(self) -> tuple[str, ...]:
        return tuple(u.strip() for u in self.digilocker_redirect_uris.split(",") if u.strip())

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
