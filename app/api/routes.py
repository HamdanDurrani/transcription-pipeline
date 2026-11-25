from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.core.exceptions import TranscriptionError
from app.schemas import ErrorResponse, TranscriptResponse
from app.services.transcription import get_transcription_service, to_srt

logger = logging.getLogger(__name__)
router = APIRouter(tags=["transcription"])

READ_CHUNK_BYTES = 1024 * 1024  # 1 MB


@router.post(
    "/transcribe",
    response_model=TranscriptResponse,
    responses={
        200: {
            "content": {
                "application/json": {},
                "text/plain": {"schema": {"type": "string"}},
            }
        },
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def transcribe_audio(
    file: UploadFile = File(...),
    format: str = Query(
        "json",
        pattern="^(json|srt)$",
        description="Response format: json (default) or srt",
    ),
):
    """
    Accept an audio upload and return a timestamped transcript.

    - **json** (default): language, duration, full text, and segments
    - **srt**: SubRip subtitle file
    """
    settings = get_settings()
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()

    if ext not in settings.supported_formats:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported format, allowed: "
                f"{sorted(settings.supported_formats)}"
            ),
        )

    tmp_path: str | None = None
    try:
        tmp_path = await _persist_upload(file, ext, settings.max_upload_bytes)
        logger.info(
            "Upload accepted filename=%s size_bytes=%d format=%s",
            filename,
            os.path.getsize(tmp_path),
            format,
        )

        service = get_transcription_service()
        result = await run_in_threadpool(service.transcribe, tmp_path)
    except HTTPException:
        raise
    except TranscriptionError as exc:
        logger.warning("Transcription failed filename=%s error=%s", filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected transcription failure filename=%s", filename)
        raise HTTPException(
            status_code=500,
            detail="Internal transcription error",
        ) from None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if format == "srt":
        return PlainTextResponse(
            to_srt(result),
            media_type="application/x-subrip",
        )
    return result


async def _persist_upload(
    file: UploadFile,
    ext: str,
    max_bytes: int,
) -> str:
    """Stream upload to disk and enforce size limit while writing."""
    written = 0
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    try:
        while True:
            chunk = await file.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                raise HTTPException(status_code=413, detail="File too large")
            tmp.write(chunk)
        tmp.flush()
    except Exception:
        tmp.close()
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
        raise
    else:
        tmp.close()
        return tmp.name
