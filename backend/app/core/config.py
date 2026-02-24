"""Runtime configuration for backend services."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VINS_", env_file=".env", extra="ignore")

    app_name: str = "VINS Backend"
    api_prefix: str = "/api/v1"
    max_upload_mb: int = 200
    default_sample_rate: int = 44100
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    project_root: Path = Path(__file__).resolve().parents[3]

    @property
    def projects_dir(self) -> Path:
        return self.project_root / "projects"

    @property
    def examples_dir(self) -> Path:
        return self.project_root / "examples"


settings = Settings()
settings.projects_dir.mkdir(parents=True, exist_ok=True)
settings.examples_dir.mkdir(parents=True, exist_ok=True)

