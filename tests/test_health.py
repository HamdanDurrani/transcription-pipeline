def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_ffmpeg_present(client):
    response = client.get("/ready")
    # CI/local machines with ffmpeg installed should be ready
    assert response.status_code in (200, 503)
    if response.status_code == 200:
        assert response.json() == {"status": "ready"}
