"""Environment-driven settings, validated once at startup."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GPU_TWIN_", env_file=".env", extra="ignore")

    database_url: str = Field(default=f"sqlite+pysqlite:///{_PROJECT_ROOT / 'gpu_lab_twin.db'}")
    fleet_fixture_path: Path = Field(default=_PROJECT_ROOT / "fixtures" / "fleet.json")
    policy_version: str = Field(default="impl1-v1", min_length=1)
    log_level: str = Field(default="INFO")
    liveness_scan_seconds: float = Field(default=5.0, ge=0, allow_inf_nan=False)

    @field_validator("fleet_fixture_path")
    @classmethod
    def _fixture_must_exist(cls, path: Path) -> Path:
        if not path.is_file():
            raise ValueError(f"fleet fixture not found: {path}")
        return path

    @field_validator("liveness_scan_seconds")
    @classmethod
    def _scan_disabled_or_not_busy(cls, seconds: float) -> float:
        # Each scan holds the shared write lock; a sub-100 ms period would starve heartbeat ingestion.
        if 0 < seconds < 0.1:
            raise ValueError("liveness_scan_seconds must be 0 (disabled) or at least 0.1")
        return seconds

    @field_validator("log_level")
    @classmethod
    def _known_log_level(cls, level: str) -> str:
        level = level.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("log_level must be DEBUG, INFO, WARNING or ERROR")
        return level


@lru_cache
def get_settings() -> Settings:
    return Settings()
