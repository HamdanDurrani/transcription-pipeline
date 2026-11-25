import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse

from app.config import MAX_UPLOAD_BYTES, SUPPORTED_FORMATS
from app.schemas import TranscriptResponse
from app.services.transcription import get_transcription_service, to_srt

router = APIRouter(tags=["transcription"])


@router.post(
    "/transcribe",
    response_model=TranscriptResponse,
    responses={
        200: {
            "content": {
                "application/json": {},
                "text/plain": {"schema": {"type": "string"}},
            }
        }
    },
)
async def transcribe_audio(
    file: UploadFile = File(...),
    format: str = Query("json", pattern="^(json|srt)$"),
):
    """
    Accept an audio upload and return a timestamped transcript.

    - **json** (default): language, duration, full text, and segments
    - **srt**: SubRip subtitle file
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported format, allowed: {sorted(SUPPORTED_FORMATS)}",
        )

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        if os.path.getsize(tmp_path) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")

        service = get_transcription_service()
        result = await run_in_threadpool(service.transcribe, tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    if format == "srt":
        return PlainTextResponse(to_srt(result), media_type="application/x-subrip")
    return result
