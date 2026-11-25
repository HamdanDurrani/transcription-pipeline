from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

from app.api import api_router
from app.config import get_settings
from app.core.logging import setup_logging
from app.services.transcription import get_transcription_service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(
        "Starting %s v%s (model=%s device=%s)",
        settings.app_name,
        settings.app_version,
        settings.whisper_model,
        settings.whisper_device,
    )
    # Warm the model at boot so the first /transcribe is not a cold start
    await run_in_threadpool(get_transcription_service)
    logger.info("Model warm-up complete")
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Speech-to-text API built on faster-whisper. "
            "Uploads are validated, normalized with ffmpeg, transcribed in "
            "overlapping chunks, and returned as JSON or SRT."
        ),
        lifespan=lifespan,
    )
    application.include_router(api_router)

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """Liveness probe — process is up."""
        return {"status": "ok"}

    @application.get("/ready", tags=["ops"])
    async def ready() -> dict[str, str]:
        """Readiness probe — ffmpeg/ffprobe available and model loaded."""
        import shutil

        from fastapi import HTTPException

        from app.services.transcription import is_model_ready

        missing = [bin_ for bin_ in ("ffmpeg", "ffprobe") if shutil.which(bin_) is None]
        if missing:
            raise HTTPException(
                status_code=503,
                detail=f"Missing dependencies: {', '.join(missing)}",
            )
        if not is_model_ready():
            raise HTTPException(status_code=503, detail="Model not loaded yet")
        return {"status": "ready"}

    return application


app = create_app()
