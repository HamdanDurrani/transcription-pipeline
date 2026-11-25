import os
import shutil
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from transcriber import transcribe, to_srt, SUPPORTED_FORMATS

app = FastAPI(title="Transcription Service")
MAX_SIZE = 200 * 1024 * 1024  # 200 MB


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile, format: str = "json"):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        raise HTTPException(415, f"Unsupported format, allowed: {sorted(SUPPORTED_FORMATS)}")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)

    try:
        if os.path.getsize(tmp.name) > MAX_SIZE:
            raise HTTPException(413, "File too large")
        result = await run_in_threadpool(transcribe, tmp.name)
    except ValueError as e:
        raise HTTPException(422, str(e))
    finally:
        os.remove(tmp.name)

    if format == "srt":
        return PlainTextResponse(to_srt(result))
    return result
