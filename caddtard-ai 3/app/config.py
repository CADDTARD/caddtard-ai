"""
Central runtime configuration, sourced from environment variables (or a .env
file when running outside Docker). See .env.example for every supported key.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CADDTARD AI"
    app_version: str = "3.1.0"

    # Falls back to a local SQLite file when no DATABASE_URL is supplied,
    # so `uvicorn app.main:app` works with zero extra setup outside Docker.
    database_url: str = "sqlite:///./caddtard.db"

    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # Public demo deployments can expose the dashboard and read APIs while
    # rejecting every externally initiated mutation. Scheduled agents run
    # inside the process and are unaffected by this HTTP guard.
    public_read_only: bool = False

    agents_enabled: bool = True
    agent_initial_delay_seconds: int = 5
    agent_stagger_seconds: int = 10
    agent_misfire_grace_seconds: int = 300
    # Optional: only the Patent Landscape Agent needs this (PatentsView
    # went key-gated in 2024). Free key: https://search.patentsview.org/api-request
    # Left unset, that agent runs on schedule and honestly reports "not
    # configured" instead of fabricating patent data.
    patentsview_api_key: str = ""
    # Per-agent intervals now live on each AgentDefinition DB row (seeded from
    # app/seed_data_v2.py), so adding agent #51 doesn't require a new env var.
    # This is only the fallback for a row whose interval_minutes is null.
    default_agent_interval_minutes: int = 720
    agent_http_timeout: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
