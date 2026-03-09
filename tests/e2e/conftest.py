"""
E2E test fixtures: backend server + frontend server + Playwright browser.
"""
import os
import subprocess
import time
import pytest
import httpx

BACKEND_PORT = 8765
FRONTEND_PORT = 8766
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
FRONTEND_URL = f"http://127.0.0.1:{FRONTEND_PORT}"
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
SAMPLE_VIDEO = os.path.join(FIXTURES_DIR, "sample.mp4")


def _wait_for_server(url, timeout=15):
    """Wait for a server to become available."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def backend_server():
    """Start the FastAPI backend server for the test session."""
    # Check if already running
    try:
        r = httpx.get(f"{BACKEND_URL}/api/health", timeout=2)
        if r.status_code == 200:
            yield BACKEND_URL
            return
    except (httpx.ConnectError, httpx.ReadTimeout):
        pass

    # Start the backend
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if not _wait_for_server(f"{BACKEND_URL}/api/health"):
        proc.terminate()
        raise RuntimeError("Backend server failed to start")

    yield BACKEND_URL

    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def frontend_server(backend_server):
    """Start the patched frontend server for the test session."""
    from tests.e2e.serve_frontend import start_server
    server = start_server(port=FRONTEND_PORT)
    if not _wait_for_server(FRONTEND_URL):
        server.shutdown()
        raise RuntimeError("Frontend server failed to start")
    yield FRONTEND_URL
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    """Launch Playwright Chromium browser."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def page(browser, frontend_server):
    """Create a new browser page for each test."""
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 800})
    yield page
    page.close()


@pytest.fixture
def sample_video_path():
    """Return the absolute path to the sample video file."""
    path = os.path.abspath(SAMPLE_VIDEO)
    assert os.path.exists(path), f"Sample video not found: {path}"
    return path


@pytest.fixture
def api_client(backend_server):
    """HTTP client for direct backend API calls."""
    with httpx.Client(base_url=backend_server, timeout=30) as client:
        yield client
