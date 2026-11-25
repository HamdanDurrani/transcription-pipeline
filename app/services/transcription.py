from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from faster_whisper import WhisperModel

from app.config import Settings, get_settings
from app.core.exceptions import AudioConversionError, InvalidAudioError
from app.schemas import Segment, TranscriptResponse

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Chunked speech-to-text using faster-whisper + ffmpeg."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        logger.info(
            "Loading Whisper model=%s device=%s compute_type=%s",
            self.settings.whisper_model,
            self.settings.whisper_device,
            self.settings.whisper_compute_type,
        )
        self._model = WhisperModel(
            self.settings.whisper_model,
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
        )
        logger.info("Whisper model ready")

    def get_duration(self, path: str) -> float:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise InvalidAudioError("Invalid or corrupt audio file")
        return float(result.stdout.strip())

    def convert_chunk(
        self,
        input_path: str,
        output_path: str,
        start: float,
        length: float,
    ) -> None:
        """Extract a window and normalize to 16 kHz mono WAV."""
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", str(start),
                    "-t", str(length),
                    "-i", input_path,
                    "-vn", "-ac", "1", "-ar", "16000",
                    output_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise AudioConversionError(
                f"ffmpeg failed converting chunk at {start}s"
            ) from exc

    def transcribe(self, input_path: str) -> TranscriptResponse:
        duration = self.get_duration(input_path)
        settings = self.settings
        segments_out: list[Segment] = []
        last_end = 0.0
        start = 0.0
        language: str | None = None
        chunk_index = 0

        logger.info("Transcribing path=%s duration=%.2fs", input_path, duration)

        with tempfile.TemporaryDirectory() as tmp:
            chunk_path = os.path.join(tmp, "chunk.wav")

            while start < duration:
                chunk_index += 1
                self.convert_chunk(
                    input_path,
                    chunk_path,
                    start,
                    settings.chunk_seconds + settings.overlap_seconds,
                )
                segments, info = self._model.transcribe(
                    chunk_path,
                    vad_filter=True,
                    language=language,
                )
                language = language or info.language

                for seg in segments:
                    seg_start = seg.start + start
                    seg_end = seg.end + start

                    if seg_start < last_end - settings.overlap_dedup_tolerance:
                        continue
                    if seg_start >= start + settings.chunk_seconds:
                        break

                    segments_out.append(
                        Segment(
                            id=len(segments_out),
                            start=round(seg_start, 2),
                            end=round(seg_end, 2),
                            text=seg.text.strip(),
                        )
                    )
                    last_end = seg_end

                start += settings.chunk_seconds

        result = TranscriptResponse(
            language=language,
            duration=round(duration, 2),
            text=" ".join(s.text for s in segments_out),
            segments=segments_out,
        )
        logger.info(
            "Transcription complete language=%s segments=%d chunks=%d",
            result.language,
            len(result.segments),
            chunk_index,
        )
        return result


def to_srt(result: TranscriptResponse) -> str:
    def ts(t: float) -> str:
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"

    lines = []
    for i, segment in enumerate(result.segments, 1):
        lines.append(
            f"{i}\n{ts(segment.start)} --> {ts(segment.end)}\n{segment.text}\n"
        )
    return "\n".join(lines)


_service: TranscriptionService | None = None


def get_transcription_service() -> TranscriptionService:
    """Lazy singleton — model loads once per process."""
    global _service
    if _service is None:
        _service = TranscriptionService()
    return _service


def is_model_ready() -> bool:
    return _service is not None


def reset_transcription_service() -> None:
    """Test helper to clear the singleton between cases."""
    global _service
    _service = None


if __name__ == "__main__":
    import json
    import sys

    from app.core.logging import setup_logging

    setup_logging()
    if len(sys.argv) < 2:
        print("Usage: python -m app.services.transcription <audio_path>", file=sys.stderr)
        sys.exit(1)

    service = get_transcription_service()
    print(json.dumps(service.transcribe(sys.argv[1]).model_dump(), indent=2))
