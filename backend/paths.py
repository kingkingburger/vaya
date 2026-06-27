import os
from pathlib import Path

BACKEND_DIR = Path(__file__).parent


def storage_dir() -> Path:
    """Runtime storage root for thumbnails, analysis files, uploads, and exports."""
    override = os.environ.get("VAYA_DATA_DIR")
    if override:
        return Path(override)
    return BACKEND_DIR / "storage"


def config_path() -> Path:
    """Writable config path. Dev defaults to the checked-in backend config."""
    override = os.environ.get("VAYA_CONFIG_PATH")
    if override:
        return Path(override)
    return BACKEND_DIR / "config.yaml"
