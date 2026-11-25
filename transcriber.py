import os
import subprocess
import tempfile
from faster_whisper import WhisperModel

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
CHUNK = 600    # 10 min chunks
OVERLAP = 5    # seconds of overlap between chunks

model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")


def get_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True
    )
    if out.returncode != 0 or not out.stdout.strip():
        raise ValueError("Invalid or corrupt audio file")
    return float(out.stdout.strip())


def convert_chunk(input_path, output_path, start, length):
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-ss", str(start), "-t", str(length), "-i", input_path,
        "-vn", "-ac", "1", "-ar", "16000", output_path
    ], check=True)


def transcribe(input_path):
    duration = get_duration(input_path)
    segments_out = []
    last_end = 0
    start = 0
    language = None

    with tempfile.TemporaryDirectory() as tmp:
        chunk_path = os.path.join(tmp, "chunk.wav")

        while start < duration:
            convert_chunk(input_path, chunk_path, start, CHUNK + OVERLAP)
            segments, info = model.transcribe(chunk_path, vad_filter=True, language=language)
            language = language or info.language

            for seg in segments:
                seg_start = seg.start + start
                seg_end = seg.end + start
                if seg_start < last_end - 0.2:   # duplicate from overlap
                    continue
                if seg_start >= start + CHUNK:   # belongs to next chunk
                    break
                segments_out.append({
                    "id": len(segments_out),
                    "start": round(seg_start, 2),
                    "end": round(seg_end, 2),
                    "text": seg.text.strip()
                })
                last_end = seg_end

            start += CHUNK

    return {
        "language": language,
        "duration": round(duration, 2),
        "text": " ".join(s["text"] for s in segments_out),
        "segments": segments_out
    }


def to_srt(result):
    def ts(t):
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"

    lines = []
    for i, s in enumerate(result["segments"], 1):
        lines.append(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['text']}\n")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys, json
    print(json.dumps(transcribe(sys.argv[1]), indent=2))
