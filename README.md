# Transcription Pipeline

Production-oriented speech-to-text service. Upload audio, get a timestamped transcript as JSON or SRT.

Built with **FastAPI**, **faster-whisper**, and **ffmpeg**.

---

## Architecture

```
Client
  │  POST /transcribe  (multipart audio)
  ▼
┌─────────────────────┐
│  FastAPI (app/)     │  validate format + size
│  api/routes.py      │  persist upload to temp file
└──────────┬──────────┘
           │ run_in_threadpool
           ▼
┌─────────────────────┐
│  TranscriptionService│
│  services/           │
│                      │
│  1. ffprobe duration │
│  2. ffmpeg chunks    │──► 16 kHz mono WAV windows
│  3. Whisper + VAD    │──► segments per chunk
│  4. stitch + dedupe  │──► stable timeline
└──────────┬──────────┘
           ▼
    JSON  or  SRT
```

### Request flow

1. **Validate** — reject unsupported extensions and files over 200 MB.
2. **Probe** — `ffprobe` confirms the file is readable and returns duration.
3. **Chunk** — long audio is split into 10-minute windows with a 5-second overlap so memory stays bounded and word boundaries are not lost at cuts.
4. **Normalize** — each window is converted to 16 kHz mono WAV (Whisper’s expected input).
5. **Transcribe** — faster-whisper runs with VAD to skip silence; language detected on the first chunk is reused for the rest.
6. **Stitch** — overlap duplicates are dropped; segment timestamps are shifted back onto the absolute timeline.
7. **Respond** — full text + segments as JSON, or SubRip (`.srt`) when `?format=srt`.

---

## Project layout

```
transcription-pipeline/
├── app/
│   ├── main.py                 # FastAPI entrypoint, health check
│   ├── config.py               # env-driven settings & limits
│   ├── api/
│   │   └── routes.py           # HTTP handlers
│   ├── services/
│   │   └── transcription.py    # ffmpeg + Whisper pipeline
│   └── schemas/
│       └── transcript.py       # response models
├── requirements.txt
└── README.md
```

| Layer | Responsibility |
|-------|----------------|
| `api/` | HTTP concerns only — upload handling, status codes, response format |
| `services/` | Domain logic — probing, conversion, inference, SRT rendering |
| `schemas/` | Typed contracts returned to clients |
| `config.py` | Tunables (`WHISPER_MODEL`, chunk size, upload cap) |

---

## Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) on `PATH` (provides `ffmpeg` and `ffprobe`)

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `small` | Model size (`tiny`, `base`, `small`, `medium`, …) |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` | Quantization / precision for inference |

---

## Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Examples

```bash
# JSON transcript
curl -F "file=@sample.mp3" http://localhost:8000/transcribe

# SRT subtitles
curl -F "file=@sample.mp3" "http://localhost:8000/transcribe?format=srt"

# Health check
curl http://localhost:8000/health
```

### Example JSON response

```json
{
  "language": "en",
  "duration": 42.5,
  "text": "Hello world. This is a demo.",
  "segments": [
    { "id": 0, "start": 0.0, "end": 1.8, "text": "Hello world." },
    { "id": 1, "start": 2.1, "end": 4.0, "text": "This is a demo." }
  ]
}
```

---

## Run as a CLI

```bash
python -m app.services.transcription sample.mp3
```

---

## API reference

### `POST /transcribe`

| Param | In | Required | Description |
|-------|-----|----------|-------------|
| `file` | form | yes | Audio upload (`.wav`, `.mp3`, `.m4a`, `.flac`, `.ogg`) |
| `format` | query | no | `json` (default) or `srt` |

| Status | Meaning |
|--------|---------|
| `200` | Transcript ready |
| `413` | File exceeds 200 MB |
| `415` | Unsupported media type |
| `422` | Corrupt / unreadable audio |

### `GET /health`

Liveness probe — returns `{"status": "ok"}`.

---

## Design decisions

| Decision | Why |
|----------|-----|
| **faster-whisper over OpenAI Whisper** | CTranslate2 backend is faster and uses less memory on CPU, which matters for a self-hosted service without a GPU requirement. |
| **ffmpeg / ffprobe as the media layer** | Battle-tested format support; one conversion path to 16 kHz mono WAV keeps Whisper input consistent regardless of upload type. |
| **10-minute chunks + 5s overlap** | Bounds peak RAM on long files. Overlap prevents cutting mid-word; stitching drops near-duplicates so timestamps stay monotonic. |
| **VAD enabled** | Skips silence before inference — shorter effective audio, fewer empty segments, lower cost per request. |
| **Language lock after first chunk** | Avoids language flicker across chunks on the same recording. |
| **`run_in_threadpool`** | Whisper is CPU-bound; offloading keeps the FastAPI event loop free for health checks and concurrent accepts. |
| **Layered package (`api` / `services` / `schemas`)** | HTTP, domain logic, and response contracts stay separable — easier to test and swap backends later. |
| **Lazy model singleton** | Model load is expensive; one instance per process amortizes startup cost across requests. |
| **Temp-file lifecycle** | Uploads and chunk WAVs never persist past the request; reduces disk leak risk under load. |
| **JSON + SRT** | JSON for product/API consumers; SRT for editors and subtitle workflows without a second service. |
| **200 MB upload cap + extension allowlist** | Cheap abuse guardrails before any heavy decode/inference work. |
