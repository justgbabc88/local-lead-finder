"""Application settings loaded from environment."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str = ""
    supabase_jwt_secret: str

    # Google Places (fallback key — Phase 2+ prefers the DB key pool)
    google_places_api_key: str = ""

    # Redis / RQ (Phase 2+)
    redis_url: str = "redis://localhost:6379/0"
    scrape_queue_name: str = "scrape_tasks"
    enrichment_queue_name: str = "enrichment_tasks"
    worker_job_timeout: int = 900  # seconds per task — covers 3-page Places lookup

    # CORS — comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173"
    # Optional regex to match dynamic origins (e.g. Vercel preview deploys)
    cors_origin_regex: str = ""

    # Misc
    log_level: str = "info"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
