from app.schemas import Segment, TranscriptResponse
from app.services.transcription import to_srt


def test_to_srt_format():
    result = TranscriptResponse(
        language="en",
        duration=3.5,
        text="Hello world.",
        segments=[
            Segment(id=0, start=0.0, end=1.25, text="Hello"),
            Segment(id=1, start=1.5, end=3.5, text="world."),
        ],
    )
    srt = to_srt(result)
    assert "1\n00:00:00,000 --> 00:00:01,250\nHello" in srt
    assert "2\n00:00:01,500 --> 00:00:03,500\nworld." in srt
