"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = BACKEND_DIR / "frontend"
UPLOAD_DIR = REPO_ROOT / "data" / "uploads"

# Default dev signing key. The lifespan guard refuses to boot in production
# (APP_ENV=production) while this value (or any <32-char secret) is in use.
DEV_JWT_SECRET = "neuratriage-dev-secret-2026-eeg-x"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_name: str = "NeuraTriage EEG"
    app_version: str = "0.2.0"

    jwt_secret: str = Field(
        default=DEV_JWT_SECRET,
        description="HS256 signing key. Override in production.",
    )
    jwt_expires_hours: int = 8

    port: int = 8501

    allowed_origins: str = (
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5501,http://127.0.0.1:5501,"
        "http://localhost:5500,http://127.0.0.1:5500,"
        "https://neuratriage-eeg.vercel.app,"
        "https://5cdc41db78b1249d-1-53-112-82.serveousercontent.com,"
        "https://d9b17158a0527c.lhr.life"
    )

    model_path: str = "backend/models/model.joblib"
    auto_load_model_on_startup: bool = True
    # Real-time scorer: "features" = entropy/MFDFA + LightGBM (model_path);
    # "riemann" = covariance tangent-space model (riemann_model_path), the most
    # device-transferable model in the leave-source-out study. SQI gating, EMA and
    # hysteresis are shared by both.
    realtime_model: str = "features"
    riemann_model_path: str = "backend/models/riemann_model.joblib"
    # Opt-in folder OUTSIDE the repo with extra replay cases (e.g. F:/eeg_extra/npz/oslo
    # for the "unseen device -> false alert" demo). Empty = only the repo datasets.
    extra_replay_dir: str = ""

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@neuratriage.ai"
    sendgrid_from_name: str = "NeuraTriage EEG"

    # Weekly report scheduler
    weekly_report_dow: str = "mon"
    weekly_report_hour: int = 7

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    def jwt_secret_is_insecure(self) -> bool:
        return self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32

    def candidate_model_paths(self) -> List[Path]:
        primary = (REPO_ROOT / self.model_path).resolve()
        return [
            primary,
            REPO_ROOT / "models_store" / "model.joblib",
            REPO_ROOT / "out" / "model.joblib",
            REPO_ROOT / "dataset_npz" / "model_smoke.joblib",
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
