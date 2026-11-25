from io import BytesIO
from unittest.mock import MagicMock, patch

from app.schemas import Segment, TranscriptResponse


def test_rejects_unsupported_format(client):
    response = client.post(
        "/transcribe",
        files={"file": ("notes.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 415
    assert "Unsupported format" in response.json()["detail"]


def test_rejects_oversized_upload(client):
    with patch("app.api.routes.get_settings") as mock_settings:
        settings = MagicMock()
        settings.supported_formats = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
        settings.max_upload_bytes = 10  # tiny limit for the test
        mock_settings.return_value = settings

        response = client.post(
            "/transcribe",
            files={"file": ("clip.wav", BytesIO(b"x" * 64), "audio/wav")},
        )
    assert response.status_code == 413
    assert response.json()["detail"] == "File too large"


def test_transcribe_json_success(client):
    fake = TranscriptResponse(
        language="en",
        duration=1.0,
        text="hello",
        segments=[Segment(id=0, start=0.0, end=1.0, text="hello")],
    )
    mock_service = MagicMock()
    mock_service.transcribe.return_value = fake

    with patch(
        "app.api.routes.get_transcription_service",
        return_value=mock_service,
    ):
        response = client.post(
            "/transcribe",
            files={"file": ("clip.wav", BytesIO(b"RIFF"), "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "en"
    assert body["text"] == "hello"
    assert len(body["segments"]) == 1
    mock_service.transcribe.assert_called_once()


def test_transcribe_srt_success(client):
    fake = TranscriptResponse(
        language="en",
        duration=1.0,
        text="hello",
        segments=[Segment(id=0, start=0.0, end=1.0, text="hello")],
    )
    mock_service = MagicMock()
    mock_service.transcribe.return_value = fake

    with patch(
        "app.api.routes.get_transcription_service",
        return_value=mock_service,
    ):
        response = client.post(
            "/transcribe?format=srt",
            files={"file": ("clip.wav", BytesIO(b"RIFF"), "audio/wav")},
        )

    assert response.status_code == 200
    assert "hello" in response.text
    assert "-->" in response.text
