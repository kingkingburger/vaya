"""Tests for export pipeline and endpoints."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_build_export_timeline_segments_removes_silence():
    from services.exporter import _build_export_timeline_segments

    highlights = [
        HighlightSegment(start=0.0, end=10.0, score=0.8),
        HighlightSegment(start=20.0, end=25.0, score=0.7),
    ]
    silence = [
        {"start": 2.0, "end": 4.0},
        {"start": 8.0, "end": 12.0},
        {"start": 22.0, "end": 23.0},
    ]

    assert _build_export_timeline_segments(highlights, silence) == [
        {"start": 0.0, "end": 2.0},
        {"start": 4.0, "end": 8.0},
        {"start": 20.0, "end": 22.0},
        {"start": 23.0, "end": 25.0},
    ]


def test_build_filter_complex_uses_non_silent_segments():
    from services.exporter import _build_filter_complex

    highlights = [HighlightSegment(start=0.0, end=10.0, score=0.8)]
    filter_str = _build_filter_complex(
        highlights=highlights,
        silence_segments=[{"start": 2.0, "end": 4.0}],
        subtitles_path=None,
        subtitle_config={},
    )

    assert "trim=start=0.0:end=2.0" in filter_str
    assert "trim=start=4.0:end=10.0" in filter_str
    assert "trim=start=0.0:end=10.0" not in filter_str
    assert "concat=n=2" in filter_str


def test_detect_encoder():
    from services.exporter import _detect_encoder
    encoder = _detect_encoder()
    assert encoder in ("h264_nvenc", "libx264")


def test_remap_subtitles_to_export_timeline():
    from services.exporter import _remap_subtitles_for_export

    highlights = [
        HighlightSegment(start=10.0, end=20.0, score=0.8),
        HighlightSegment(start=30.0, end=40.0, score=0.7),
    ]
    subtitles = [
        {"start": 12.0, "end": 14.0, "text": "첫 번째 킬"},
        {"start": 18.0, "end": 32.0, "text": "이어지는 장면"},
        {"start": 35.0, "end": 38.0, "text": "마무리"},
        {"start": 5.0, "end": 8.0, "text": "잘린 자막"},
    ]

    remapped = _remap_subtitles_for_export(subtitles, highlights)

    assert remapped == [
        {"start": 2.0, "end": 4.0, "text": "첫 번째 킬"},
        {"start": 8.0, "end": 10.0, "text": "이어지는 장면"},
        {"start": 10.0, "end": 12.0, "text": "이어지는 장면"},
        {"start": 15.0, "end": 18.0, "text": "마무리"},
    ]


def test_remap_subtitles_to_export_timeline_after_silence_removal():
    from services.exporter import _remap_subtitles_for_export

    highlights = [HighlightSegment(start=0.0, end=10.0, score=0.8)]
    subtitles = [{"start": 1.0, "end": 5.0, "text": "split around silence"}]
    silence = [{"start": 2.0, "end": 4.0}]

    remapped = _remap_subtitles_for_export(subtitles, highlights, silence)

    assert remapped == [
        {"start": 1.0, "end": 2.0, "text": "split around silence"},
        {"start": 2.0, "end": 3.0, "text": "split around silence"},
    ]


def test_export_uses_remapped_subtitle_file(tmp_path, monkeypatch):
    from config import AppConfig
    from services import exporter

    monkeypatch.setattr(exporter, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(exporter, "STORAGE_DIR", tmp_path / "storage")

    captured_cmds = []

    async def fake_run_ffmpeg(cmd, progress_callback, stage, start_pct, end_pct):
        captured_cmds.append(cmd)
        output_path = Path(cmd[-1])
        output_path.write_bytes(b"video")

    highlights = [HighlightSegment(start=10.0, end=20.0, score=0.8)]
    subtitles = [{"start": 12.0, "end": 14.0, "text": "테스트 자막"}]

    with patch("services.exporter._detect_encoder", return_value="libx264"), \
         patch("services.exporter._run_ffmpeg", side_effect=fake_run_ffmpeg):
        results = asyncio.run(exporter.export_video(
            video_id="vid123",
            file_path="gameplay.mp4",
            highlights=highlights,
            silence_segments=[],
            subtitles_path=None,
            subtitle_segments=subtitles,
            config=AppConfig(),
            youtube=True,
            shorts=False,
            subtitles=True,
        ))

    assert results[0]["size"] == 5
    filter_index = captured_cmds[0].index("-filter_complex") + 1
    filter_str = captured_cmds[0][filter_index]
    remapped_srt = tmp_path / "storage" / "analysis" / "vid123" / "export_subtitles.srt"
    assert str(remapped_srt).replace("\\", "/").replace(":", "\\:") in filter_str
    assert "00:00:02,000 --> 00:00:04,000" in remapped_srt.read_text(encoding="utf-8")
    assert "테스트 자막" in remapped_srt.read_text(encoding="utf-8")


def test_export_does_not_burn_original_subtitle_file_without_segments(tmp_path, monkeypatch):
    from config import AppConfig
    from services import exporter

    monkeypatch.setattr(exporter, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(exporter, "STORAGE_DIR", tmp_path / "storage")

    original_srt = tmp_path / "source_subtitles.srt"
    original_srt.write_text(
        "1\n00:00:12,000 --> 00:00:14,000\nOriginal timeline subtitle\n",
        encoding="utf-8",
    )
    captured_cmds = []

    async def fake_run_ffmpeg(cmd, progress_callback, stage, start_pct, end_pct):
        captured_cmds.append(cmd)
        Path(cmd[-1]).write_bytes(b"video")

    with patch("services.exporter._detect_encoder", return_value="libx264"), \
         patch("services.exporter._run_ffmpeg", side_effect=fake_run_ffmpeg):
        asyncio.run(exporter.export_video(
            video_id="vid123",
            file_path="gameplay.mp4",
            highlights=[HighlightSegment(start=10.0, end=20.0, score=0.8)],
            silence_segments=[],
            subtitles_path=str(original_srt),
            subtitle_segments=[],
            config=AppConfig(),
            youtube=True,
            shorts=False,
            subtitles=True,
        ))

    filter_index = captured_cmds[0].index("-filter_complex") + 1
    filter_str = captured_cmds[0][filter_index]
    assert "subtitles=" not in filter_str


def test_export_fails_when_silence_removes_all_segments(tmp_path, monkeypatch):
    from config import AppConfig
    from services import exporter

    monkeypatch.setattr(exporter, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(exporter, "STORAGE_DIR", tmp_path / "storage")

    with patch("services.exporter._detect_encoder", return_value="libx264"):
        with pytest.raises(RuntimeError, match="No exportable video segments"):
            asyncio.run(exporter.export_video(
                video_id="vid123",
                file_path="gameplay.mp4",
                highlights=[HighlightSegment(start=10.0, end=20.0, score=0.8)],
                silence_segments=[{"start": 10.0, "end": 20.0}],
                subtitles_path=None,
                subtitle_segments=[],
                config=AppConfig(),
                youtube=True,
                shorts=False,
                subtitles=True,
            ))
