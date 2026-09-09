from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Compose injects DATABASE_URL for the Postgres app."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+asyncpg://vendor:vendor@localhost:5432/vendor_orchestrator"
    )
    # None => call the in-process mock vendor via ASGI (no sidecar required).
    mock_vendor_alpha_url: str | None = None
    mock_vendor_beta_url: str | None = None
    vendor_http_timeout_seconds: float = 5.0
    db_connect_attempts: int = 20
    db_connect_delay_seconds: float = 0.5


@lru_cache
def get_settings() -> Settings:
    return Settings()
