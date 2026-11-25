class TranscriptionError(Exception):
    """Base error for the transcription domain."""


class InvalidAudioError(TranscriptionError):
    """Audio cannot be probed or decoded."""


class AudioConversionError(TranscriptionError):
    """ffmpeg failed while converting a chunk."""
