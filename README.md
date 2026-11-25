# Transcription Pipeline

Simple service that takes an audio file and returns the transcript with timestamps per segment.

Uses faster-whisper for speech to text and ffmpeg for audio conversion.

## Setup

Needs Python 3.10+ and ffmpeg installed.

```
pip install -r requirements.txt
```

## Run as API

```
uvicorn app:app --reload
curl -F "file=@sample.mp3" http://localhost:8000/transcribe
curl -F "file=@sample.mp3" "http://localhost:8000/transcribe?format=srt"
```

## Run as script

```
python transcriber.py sample.mp3
```

## How it works

- validates the file with ffprobe before processing
- converts any format to 16kHz mono WAV with ffmpeg
- splits long audio into 10 min chunks with a small overlap, so memory stays low
- VAD skips silence
- returns JSON with language, full text and segments (start, end, text), or SRT
