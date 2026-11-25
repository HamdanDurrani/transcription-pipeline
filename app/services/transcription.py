import os
import subprocess
import tempfile

from faster_whisper import WhisperModel

from app.config import (
    CHUNK_SECONDS,
    OVERLAP_DEDUP_TOLERANCE,
    OVERLAP_SECONDS,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_MODEL,
)
from app.schemas import Segment, TranscriptResponse


class TranscriptionService:
    """Chunked speech-to-text using faster-whisper + ffmpeg."""

    def __init__(self) -> None:
        self._model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

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
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise ValueError("Invalid or corrupt audio file")
        return float(result.stdout.strip())

    def convert_chunk(
        self,
        input_path: str,
        output_path: str,
        start: float,
        length: float,
    ) -> None:
        """Extract a window and normalize to 16 kHz mono WAV."""
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
        )

    def transcribe(self, input_path: str) -> TranscriptResponse:
        duration = self.get_duration(input_path)
        segments_out: list[Segment] = []
        last_end = 0.0
        start = 0.0
        language: str | None = None

        with tempfile.TemporaryDirectory() as tmp:
            chunk_path = os.path.join(tmp, "chunk.wav")

            while start < duration:
                self.convert_chunk(
                    input_path,
                    chunk_path,
                    start,
                    CHUNK_SECONDS + OVERLAP_SECONDS,
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

                    # Drop duplicates produced by the overlap window
                    if seg_start < last_end - OVERLAP_DEDUP_TOLERANCE:
                        continue
                    # Hand off anything past the nominal chunk boundary
                    if seg_start >= start + CHUNK_SECONDS:
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

                start += CHUNK_SECONDS

        return TranscriptResponse(
            language=language,
            duration=round(duration, 2),
            text=" ".join(s.text for s in segments_out),
            segments=segments_out,
        )


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


# Lazy singleton — model loads once per process
_service: TranscriptionService | None = None


def get_transcription_service() -> TranscriptionService:
    global _service
    if _service is None:
        _service = TranscriptionService()
    return _service


if __name__ == "__main__":
    import json
    import sys

    service = get_transcription_service()
    print(json.dumps(service.transcribe(sys.argv[1]).model_dump(), indent=2))
