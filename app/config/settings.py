from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

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
