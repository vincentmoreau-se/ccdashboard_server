from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CCSRV_", env_file=".env", extra="ignore"
    )

    # Auth
    ingest_token: str = "change-me-shared-token"
    dashboard_password: str = "change-me"
    secret_key: str = "dev-insecure-secret-key"
    cookie_secure: bool = False
    session_max_age_seconds: int = 12 * 3600

    # Storage / reference data
    db_path: str = "./ccsrv.db"
    participants_csv: str = "./participants.csv"

    # Built frontend (SPA) served by the backend in production.
    # Empty/missing dir => API-only (dev runs Vite separately; the container
    # sets CCSRV_FRONTEND_DIST=/app/frontend/dist).
    frontend_dist: str = ""

    # Liveness / live-rate tuning
    live_window_seconds: int = 120
    snapshot_interval_seconds: int = 60

    # Presentation
    currency: str = "€"
    event_name: str = "Hackathon"

    # CORS
    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
