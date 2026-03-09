"""Tests for upload, video info, and thumbnail endpoints."""

from unittest.mock import patch

import pytest


# --- POST /api/upload ---


def test_upload_file_not_found(client):
    resp = client.post("/api/upload", json={"file_path": "/nonexistent/video.mp4"})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_upload_unsupported_format(client, tmp_path):
    bad_file = tmp_path / "file.txt"
    bad_file.write_text("not a video")

    resp = client.post("/api/upload", json={"file_path": str(bad_file)})
    assert resp.status_code == 400
    assert "unsupported" in resp.json()["detail"].lower()


@patch("routers.upload.generate_thumbnails", return_value=["thumb_000000.jpg"])
@patch("routers.upload.extract_metadata", return_value={
    "duration": 60.0,
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "codec": "h264",
    "file_size": 1_000_000,
})
@patch("routers.upload.validate_video_file")
def test_upload_success(mock_validate, mock_meta, mock_thumb, client, tmp_path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"\x00" * 100)

    resp = client.post("/api/upload", json={"file_path": str(video_file)})
    assert resp.status_code == 200

    data = resp.json()
    assert "id" in data
    assert data["info"]["duration"] == 60.0
    assert data["info"]["width"] == 1920
    assert data["info"]["height"] == 1080
    assert data["info"]["fps"] == 30.0
    assert data["info"]["codec"] == "h264"
    assert data["thumbnail_count"] == 1


# --- GET /api/video/{id}/info ---


@patch("routers.upload.generate_thumbnails", return_value=[])
@patch("routers.upload.extract_metadata", return_value={
    "duration": 120.0,
    "width": 2560,
    "height": 1440,
    "fps": 60.0,
    "codec": "hevc",
    "file_size": 5_000_000,
})
@patch("routers.upload.validate_video_file")
def test_get_video_info(mock_validate, mock_meta, mock_thumb, client, tmp_path):
    video_file = tmp_path / "game.mp4"
    video_file.write_bytes(b"\x00" * 100)

    # Upload first
    upload_resp = client.post("/api/upload", json={"file_path": str(video_file)})
    video_id = upload_resp.json()["id"]

    # Get info
    resp = client.get(f"/api/video/{video_id}/info")
    assert resp.status_code == 200

    info = resp.json()
    assert info["id"] == video_id
    assert info["duration"] == 120.0
    assert info["width"] == 2560
    assert info["fps"] == 60.0


def test_get_video_info_not_found(client):
    resp = client.get("/api/video/nonexistent/info")
    assert resp.status_code == 404


# --- GET /api/video/{id}/thumbnails ---


@patch("routers.upload.generate_thumbnails", return_value=[
    "thumb_000000.jpg", "thumb_000005.jpg", "thumb_000010.jpg",
])
@patch("routers.upload.extract_metadata", return_value={
    "duration": 15.0,
    "width": 1920,
    "height": 1080,
    "fps": 30.0,
    "codec": "h264",
    "file_size": 500_000,
})
@patch("routers.upload.validate_video_file")
def test_get_thumbnails(mock_validate, mock_meta, mock_thumb, client, tmp_path):
    video_file = tmp_path / "clip.mp4"
    video_file.write_bytes(b"\x00" * 100)

    upload_resp = client.post("/api/upload", json={"file_path": str(video_file)})
    video_id = upload_resp.json()["id"]

    resp = client.get(f"/api/video/{video_id}/thumbnails")
    assert resp.status_code == 200

    data = resp.json()
    assert data["video_id"] == video_id
    assert data["count"] == 3
    assert len(data["thumbnails"]) == 3
    assert all(f"/static/thumbnails/{video_id}/" in url for url in data["thumbnails"])


def test_get_thumbnails_not_found(client):
    resp = client.get("/api/video/nonexistent/thumbnails")
    assert resp.status_code == 404


# --- Edge cases ---


@patch("routers.upload.generate_thumbnails", side_effect=RuntimeError("ffmpeg crashed"))
@patch("routers.upload.extract_metadata", return_value={
    "duration": 10.0,
    "width": 1280,
    "height": 720,
    "fps": 30.0,
    "codec": "h264",
    "file_size": 100_000,
})
@patch("routers.upload.validate_video_file")
def test_upload_thumbnail_failure_graceful(mock_validate, mock_meta, mock_thumb, client, tmp_path):
    """Thumbnail generation failure should not block upload."""
    video_file = tmp_path / "game.mp4"
    video_file.write_bytes(b"\x00" * 100)

    resp = client.post("/api/upload", json={"file_path": str(video_file)})
    assert resp.status_code == 200
    assert resp.json()["thumbnail_count"] == 0
