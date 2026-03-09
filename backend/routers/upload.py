import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from models import UploadRequest, UploadResponse, VideoInfo
from services.video_info import extract_metadata, validate_video_file
from services.thumbnail_generator import generate_thumbnails

router = APIRouter()

# In-memory video store (MVP — no database)
_videos: dict[str, dict] = {}

STORAGE_DIR = Path(__file__).parent.parent / "storage"
THUMBNAILS_DIR = STORAGE_DIR / "thumbnails"


def get_video_store() -> dict[str, dict]:
    return _videos


@router.post("/api/upload", response_model=UploadResponse)
async def upload_video(req: UploadRequest) -> UploadResponse:
    # Validate file
    try:
        validate_video_file(req.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Extract metadata
    try:
        meta = extract_metadata(req.file_path)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"Cannot read video: {e}")

    # Assign UUID
    video_id = str(uuid.uuid4())[:8]

    # Build VideoInfo
    info = VideoInfo(
        id=video_id,
        file_path=req.file_path,
        **meta,
    )

    # Generate thumbnails in background-compatible way (sync for MVP)
    thumb_dir = THUMBNAILS_DIR / video_id
    try:
        thumb_files = generate_thumbnails(req.file_path, thumb_dir)
    except Exception as e:
        print(f"[upload] Thumbnail generation failed: {e}")
        thumb_files = []

    # Store in memory
    _videos[video_id] = {
        "info": info,
        "thumbnails": thumb_files,
        "highlights": [],
        "subtitles_path": None,
    }

    return UploadResponse(
        id=video_id,
        info=info,
        thumbnail_count=len(thumb_files),
    )
