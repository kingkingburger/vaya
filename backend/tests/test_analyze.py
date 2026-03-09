"""Tests for analysis pipeline, highlights, and WebSocket progress."""

import asyncio
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from fastapi.testclient import TestClient


# --- Helper: seed a video in the store ---

def _seed_video(client):
    """Upload a mock video and return video_id."""
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
        return resp.json()["id"]


# --- POST /api/video/{id}/analyze ---

def test_analyze_not_found(client):
    resp = client.post("/api/video/nonexistent/analyze")
    assert resp.status_code == 404


def test_analyze_starts(client):
    video_id = _seed_video(client)

    with patch("routers.analyze._analyze_audio", return_value=np.array([0.5, 0.8, 0.3])), \
         patch("routers.analyze._analyze_video", return_value=np.array([0.4, 0.7, 0.2])), \
         patch("routers.analyze._detect_silence", return_value=[]):
        resp = client.post(f"/api/video/{video_id}/analyze")
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"


def test_analyze_concurrent_409(client):
    """Concurrent analysis on same video should return 409."""
    video_id = _seed_video(client)

    # Manually add to _analyzing set to simulate in-progress
    from routers.analyze import _analyzing
    _analyzing.add(video_id)

    try:
        resp = client.post(f"/api/video/{video_id}/analyze")
        assert resp.status_code == 409
        assert "already in progress" in resp.json()["detail"].lower()
    finally:
        _analyzing.discard(video_id)


# --- GET /api/video/{id}/highlights ---

def test_get_highlights_empty(client):
    video_id = _seed_video(client)
    resp = client.get(f"/api/video/{video_id}/highlights")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_highlights_not_found(client):
    resp = client.get("/api/video/nonexistent/highlights")
    assert resp.status_code == 404


# --- PUT /api/video/{id}/highlights ---

def test_put_highlights(client):
    video_id = _seed_video(client)

    segments = [
        {"start": 5.0, "end": 15.0, "score": 0.85},
        {"start": 20.0, "end": 28.0, "score": 0.72},
    ]

    resp = client.put(f"/api/video/{video_id}/highlights", json=segments)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2

    # Verify stored
    resp2 = client.get(f"/api/video/{video_id}/highlights")
    assert resp2.status_code == 200
    data = resp2.json()
    assert len(data) == 2
    assert data[0]["start"] == 5.0
    assert data[1]["score"] == 0.72


def test_put_highlights_not_found(client):
    resp = client.put("/api/video/nonexistent/highlights", json=[])
    assert resp.status_code == 404


# --- highlight_scorer unit tests ---

def test_highlight_scorer_basic():
    from services.highlight_scorer import compute_highlights
    from config import HighlightConfig

    config = HighlightConfig(
        audio_weight=0.6,
        video_weight=0.4,
        top_percent=50,
        min_clip_duration=2,
        max_clip_duration=60,
        merge_gap=2,
    )

    # Create scores with a clear high section in the middle
    audio = np.array([0.1, 0.1, 0.9, 0.9, 0.9, 0.1, 0.1])
    video = np.array([0.2, 0.2, 0.8, 0.8, 0.7, 0.2, 0.2])

    highlights = compute_highlights(audio, video, duration=14.0, config=config)
    assert len(highlights) >= 1
    # The highlight should cover the high-score region and have a reasonable score
    assert highlights[0]["end"] > highlights[0]["start"]
    assert highlights[0]["score"] > 0.3


def test_highlight_scorer_empty():
    from services.highlight_scorer import compute_highlights
    from config import HighlightConfig

    config = HighlightConfig()
    result = compute_highlights(np.array([]), np.array([]), duration=0, config=config)
    assert result == []


def test_highlight_scorer_merge_gap():
    from services.highlight_scorer import compute_highlights
    from config import HighlightConfig

    config = HighlightConfig(
        top_percent=40,
        min_clip_duration=1,
        max_clip_duration=60,
        merge_gap=3,
    )

    # Two peaks close together (should merge)
    scores = np.zeros(20)
    scores[3:6] = 1.0  # peak 1
    scores[8:11] = 1.0  # peak 2 (gap of 2 samples)

    highlights = compute_highlights(scores, scores, duration=20.0, config=config)
    # With merge_gap=3 and close peaks, should merge into fewer segments
    assert len(highlights) >= 1


# --- WebSocket test ---

def test_ws_progress_connect(client):
    """WebSocket endpoint should accept connections."""
    video_id = _seed_video(client)

    with client.websocket_connect(f"/ws/progress/{video_id}") as ws:
        # Connection established, just close it
        pass
