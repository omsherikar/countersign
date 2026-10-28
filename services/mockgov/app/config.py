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

    # The simulated DigiLocker sign-in (OAuth code flow with a signed id token). Demo
    # defaults; the api is configured with the same client id and secret.
    mockgov_digilocker_client_id: str = "countersign-demo"
    mockgov_digilocker_client_secret: str = "countersign-demo-secret"
    # `iss` of every id token; the api checks it against its own setting.
    mockgov_digilocker_issuer: str = "http://localhost:8001/digilocker"
    # Comma-separated URL prefixes a redirect_uri must start with.
    mockgov_digilocker_redirect_uris: str = "http://localhost:3000/,http://localhost:8000/,http://127.0.0.1:3000/,http://127.0.0.1:8000/"
    # PEM of an EC P-256 private key. Empty: one is generated on first start and kept in the
    # database, so tokens stay verifiable across restarts.
    mockgov_digilocker_signing_key: str = ""
    mockgov_digilocker_code_ttl_seconds: int = 300
    mockgov_digilocker_token_ttl_seconds: int = 600

    def digilocker_redirect_prefixes(self) -> tuple[str, ...]:
        return tuple(
            p.strip() for p in self.mockgov_digilocker_redirect_uris.split(",") if p.strip()
        )

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
