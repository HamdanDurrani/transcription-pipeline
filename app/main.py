from fastapi import FastAPI

from app.api import api_router

app = FastAPI(
    title="Transcription Pipeline",
    description=(
        "Speech-to-text API built on faster-whisper. "
        "Uploads are validated, normalized with ffmpeg, transcribed in "
        "overlapping chunks, and returned as JSON or SRT."
    ),
    version="1.0.0",
)

app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
