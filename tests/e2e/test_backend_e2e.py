"""
Backend E2E tests: Full pipeline with real FFmpeg processing.
Tests: upload → analyze → highlights → subtitles → export
"""
import os
import time
import json
import pytest
import httpx

BACKEND_URL = "http://127.0.0.1:8765"
SAMPLE_VIDEO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample.mp4")
)


@pytest.fixture(scope="module")
def client(backend_server):
    with httpx.Client(base_url=backend_server, timeout=60) as c:
        yield c


class TestHealthCheck:
    def test_health_endpoint(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "gpu_available" in data
        assert "nvenc_available" in data


class TestUploadPipeline:
    """Test the upload → metadata → thumbnails flow."""

    def test_upload_valid_video(self, client):
        r = client.post("/api/upload", json={"file_path": SAMPLE_VIDEO})
        assert r.status_code == 200
        data = r.json()
        assert "id" in data
        assert "info" in data
        info = data["info"]
        assert info["duration"] > 0
        assert info["width"] == 640
        assert info["height"] == 360
        assert info["fps"] == 30
        assert info["codec"] != ""
        assert info["file_size"] > 0
        assert data["thumbnail_count"] >= 1

    def test_upload_nonexistent_file(self, client):
        r = client.post("/api/upload", json={"file_path": "/nonexistent/video.mp4"})
        assert r.status_code in (400, 404)

    def test_upload_unsupported_format(self, client):
        # Create a temp txt file
        txt_path = os.path.join(os.path.dirname(SAMPLE_VIDEO), "test.txt")
        with open(txt_path, "w") as f:
            f.write("not a video")
        try:
            r = client.post("/api/upload", json={"file_path": txt_path})
            assert r.status_code == 400
        finally:
            os.unlink(txt_path)

    def test_get_video_info(self, client):
        # Upload first
        upload = client.post("/api/upload", json={"file_path": SAMPLE_VIDEO})
        video_id = upload.json()["id"]

        r = client.get(f"/api/video/{video_id}/info")
        assert r.status_code == 200
        info = r.json()
        assert info["duration"] > 0

    def test_get_thumbnails(self, client):
        upload = client.post("/api/upload", json={"file_path": SAMPLE_VIDEO})
        video_id = upload.json()["id"]

        r = client.get(f"/api/video/{video_id}/thumbnails")
        assert r.status_code == 200
        data = r.json()
        assert "thumbnails" in data
        assert len(data["thumbnails"]) >= 1


class TestAnalysisPipeline:
    """Test the analysis → highlights → subtitles flow."""

    @pytest.fixture
    def uploaded_video(self, client):
        r = client.post("/api/upload", json={"file_path": SAMPLE_VIDEO})
        return r.json()["id"]

    def test_start_analysis(self, client, uploaded_video):
        r = client.post(f"/api/video/{uploaded_video}/analyze")
        assert r.status_code == 200
        assert r.json()["status"] == "started"

        # Wait for completion by polling (analysis lock released)
        for _ in range(90):
            time.sleep(1)
            r2 = client.post(f"/api/video/{uploaded_video}/analyze")
            if r2.status_code == 200:
                # Lock released = previous analysis completed
                break
        else:
            pytest.fail("Analysis did not complete within 90 seconds")

    def test_highlights_endpoint_works(self, client, uploaded_video):
        """Test that highlights endpoint returns valid data after analysis.
        Sample video (test pattern) may produce 0 highlights — that's OK."""
        # Trigger analysis and wait for completion
        client.post(f"/api/video/{uploaded_video}/analyze")
        for _ in range(90):
            time.sleep(1)
            r = client.post(f"/api/video/{uploaded_video}/analyze")
            if r.status_code == 200:
                break

        r = client.get(f"/api/video/{uploaded_video}/highlights")
        assert r.status_code == 200
        highlights = r.json()
        assert isinstance(highlights, list)
        # 0 highlights is valid for a test pattern video

    def test_put_highlights(self, client, uploaded_video):
        """Test manual highlight CRUD — the core user interaction."""
        new_highlights = [
            {"start": 0, "end": 5, "score": 0.8},
            {"start": 6, "end": 10, "score": 0.5},
        ]
        r = client.put(
            f"/api/video/{uploaded_video}/highlights",
            json=new_highlights,
        )
        assert r.status_code == 200

        # Verify saved
        r = client.get(f"/api/video/{uploaded_video}/highlights")
        saved = r.json()
        assert len(saved) == 2
        assert saved[0]["start"] == 0
        assert saved[1]["end"] == 10

    def test_subtitles_endpoint(self, client, uploaded_video):
        """Test subtitle endpoint. Sine wave won't produce real speech."""
        r = client.get(f"/api/video/{uploaded_video}/subtitles")
        assert r.status_code == 200
        subs = r.json()
        assert isinstance(subs, list)

    def test_concurrent_analysis_409(self, client, uploaded_video):
        """Concurrent analysis should return 409."""
        r1 = client.post(f"/api/video/{uploaded_video}/analyze")
        if r1.status_code == 200:
            r2 = client.post(f"/api/video/{uploaded_video}/analyze")
            assert r2.status_code == 409


class TestExportPipeline:
    """Test the export flow."""

    @pytest.fixture
    def analyzed_video(self, client):
        """Upload video and set manual highlights for export testing."""
        r = client.post("/api/upload", json={"file_path": SAMPLE_VIDEO})
        video_id = r.json()["id"]

        # Set manual highlights (sample video produces 0 auto-highlights)
        highlights = [{"start": 0, "end": 5, "score": 0.8}]
        client.put(f"/api/video/{video_id}/highlights", json=highlights)

        return video_id

    def test_export_youtube(self, client, analyzed_video):
        r = client.post(
            f"/api/video/{analyzed_video}/export",
            json={"youtube": True, "shorts": False, "subtitles": False},
        )
        assert r.status_code == 200

        # Wait for export to complete
        for _ in range(180):
            time.sleep(1)
            sr = client.get(f"/api/video/{analyzed_video}/export/status")
            if sr.status_code == 200:
                data = sr.json()
                if data.get("complete") is True:
                    assert len(data.get("files", [])) >= 1
                    return
                if not data.get("exporting") and data.get("files") is None:
                    # Export finished with error (no results stored)
                    pytest.fail(f"Export failed silently: {data}")

        pytest.fail("Export did not complete within 180 seconds")

    def test_export_status_not_found(self, client):
        r = client.get("/api/video/nonexistent/export/status")
        assert r.status_code == 404


class TestSettings:
    """Test settings CRUD."""

    def test_get_default_settings(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200

    def test_put_settings(self, client):
        # Save original settings for restore
        original = client.get("/api/settings").json()

        settings = {
            "highlight": {
                "audio_weight": 0.7,
                "video_weight": 0.3,
                "top_percent": 40,
                "min_clip_duration": 5,
                "max_clip_duration": 120,
                "merge_gap": 3,
            },
            "silence": {
                "threshold_db": -35,
                "min_silence_duration": 2.0,
                "padding": 0.5,
            },
            "subtitle": {
                "model": "base",
                "language": "ko",
            },
        }
        r = client.put("/api/settings", json=settings)
        assert r.status_code == 200

        # Verify saved
        r = client.get("/api/settings")
        data = r.json()
        assert data["highlight"]["audio_weight"] == 0.7

        # Restore original settings to avoid polluting config.yaml
        client.put("/api/settings", json=original)
