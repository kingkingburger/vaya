import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_video_store():
    """Clear in-memory video store between tests."""
    from routers.upload import get_video_store

    store = get_video_store()
    store.clear()
    yield
    store.clear()
