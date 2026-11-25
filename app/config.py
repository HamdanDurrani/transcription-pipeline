import os

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}

# Chunking keeps peak memory low on long recordings
CHUNK_SECONDS = 600
OVERLAP_SECONDS = 5

# Deduplicate segments that fall inside the overlap window
OVERLAP_DEDUP_TOLERANCE = 0.2

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
