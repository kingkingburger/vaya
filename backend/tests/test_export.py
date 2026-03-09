"""Tests for export pipeline and endpoints."""

from unittest.mock import patch

from models import HighlightSegment


def _seed_video_with_highlights(client):
    """Upload a mock video and add highlights."""
    with patch("routers.upload.generate_thumbnails", return_value=[]), \
         patch("routers.upload.extract_metadata", return_value={
             "duration": 30.0,
             "width": 1920,
             "height": 1080,
             "fps": 30.0,
             "codec": "h264",
             "file_size": 500_000,
         }), \
         patch("routers.upload.validate_video_file"):
        resp = client.post("/api/upload", json={"file_path": "C:/fake/video.mp4"})
        video_id = resp.json()["id"]

    # Add highlights
    segments = [
        {"start": 5.0, "end": 15.0, "score": 0.85},
        {"start": 20.0, "end": 28.0, "score": 0.72},
    ]
    client.put(f"/api/video/{video_id}/highlights", json=segments)

    return video_id


# --- POST /api/video/{id}/export ---

def test_export_not_found(client):
    resp = client.post("/api/video/nonexistent/export", json={})
    assert resp.status_code == 404


def test_export_starts(client):
    video_id = _seed_video_with_highlights(client)

    with patch("routers.export._run_export", return_value=None) as mock_run:
        resp = client.post(f"/api/video/{video_id}/export", json={
            "youtube": True,
            "shorts": False,
            "subtitles": False,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"


def test_export_concurrent_409(client):
    video_id = _seed_video_with_highlights(client)

    from routers.export import _exporting
    _exporting.add(video_id)

    try:
        resp = client.post(f"/api/video/{video_id}/export", json={})
        assert resp.status_code == 409
    finally:
        _exporting.discard(video_id)


def test_export_blocked_by_analysis(client):
    video_id = _seed_video_with_highlights(client)

    from routers.analyze import _analyzing
    _analyzing.add(video_id)

    try:
        resp = client.post(f"/api/video/{video_id}/export", json={})
        assert resp.status_code == 409
        assert "analysis" in resp.json()["detail"].lower()
    finally:
        _analyzing.discard(video_id)


# --- GET /api/video/{id}/export/status ---

def test_export_status_not_found(client):
    resp = client.get("/api/video/nonexistent/export/status")
    assert resp.status_code == 404


def test_export_status_idle(client):
    video_id = _seed_video_with_highlights(client)
    resp = client.get(f"/api/video/{video_id}/export/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exporting"] is False
    assert data["complete"] is False


# --- Exporter unit tests ---

def test_unique_path(tmp_path):
    from services.exporter import _unique_path

    p = tmp_path / "test.mp4"
    assert _unique_path(p) == p

    p.write_bytes(b"x")
    result = _unique_path(p)
    assert result == tmp_path / "test_1.mp4"

    result.write_bytes(b"x")
    result2 = _unique_path(p)
    assert result2 == tmp_path / "test_2.mp4"


def test_format_output_name():
    from services.exporter import _format_output_name

    name = _format_output_name("gameplay.mp4", "youtube")
    assert "gameplay" in name
    assert "youtube" in name
    assert name.endswith(".mp4")


def test_detect_encoder():
    from services.exporter import _detect_encoder
    encoder = _detect_encoder()
    assert encoder in ("h264_nvenc", "libx264")
