import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from app.services.transcription import reset_transcription_service


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    reset_transcription_service()
    yield
    get_settings.cache_clear()
    reset_transcription_service()


@pytest.fixture
def client():
    return TestClient(create_app())
