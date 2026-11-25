from __future__ import annotations

import platform
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_whisper_device() -> str:
    # Apple Silicon can use the experimental Metal (MPS) backend
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return "mps"
    return "cpu"


def _default_whisper_compute_type() -> str:
    # MPS has no fast native INT8 path; float16 is the practical default there
    if _default_whisper_device() == "mps":
        return "float16"
    return "int8"


class Settings(BaseSettings):
    """Application settings. Env vars override defaults; .env is optional."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Transcription Pipeline"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    whisper_model: str = "small"
    whisper_device: str = Field(default_factory=_default_whisper_device)
    whisper_compute_type: str = Field(default_factory=_default_whisper_compute_type)

    chunk_seconds: int = 600
    overlap_seconds: int = 5
    overlap_dedup_tolerance: float = 0.2
    max_upload_bytes: int = 200 * 1024 * 1024

    supported_formats: frozenset[str] = frozenset(
        {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
