"""Configuration, read from environment variables (and a local .env file)."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # The app's restricted (ledger_app) connection. LEDGER_DATABASE_URL wins because hosting
    # integrations manage DATABASE_URL and point it at the owner login.
    database_url: str = Field(validation_alias=AliasChoices("LEDGER_DATABASE_URL", "DATABASE_URL"))
    database_url_owner: str | None = None

    s3_backend: Literal["s3", "memory"] = "s3"
    s3_endpoint_url: str | None = None
    s3_bucket: str
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_region: str = "auto"

    jwt_secret: str
    cron_secret: str

    checkpoint_interval: int = 1000
    demo_tenant_ttl_hours: int = 24
    max_content_bytes: int = 2_097_152


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
