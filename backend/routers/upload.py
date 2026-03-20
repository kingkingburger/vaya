import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File

from models import UploadRequest, UploadResponse, VideoInfo
from services.video_info import extract_metadata, validate_video_file, SUPPORTED_EXTENSIONS
from services.thumbnail_generator import generate_thumbnails

router = APIRouter()

# In-memory video store (MVP — no database)
_videos: dict[str, dict] = {}

STORAGE_DIR = Path(__file__).parent.parent / "storage"
THUMBNAILS_DIR = STORAGE_DIR / "thumbnails"
UPLOADS_DIR = STORAGE_DIR / "uploads"


def get_video_store() -> dict[str, dict]:
    return _videos


def _process_video(file_path: str) -> UploadResponse:
    """공통 비디오 처리 로직: 메타데이터 추출, 썸네일 생성, 메모리 저장."""
    try:
        meta = extract_metadata(file_path)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"Cannot read video: {e}")

    video_id = str(uuid.uuid4())[:8]

    info = VideoInfo(
        id=video_id,
        file_path=file_path,
        **meta,
    )

    thumb_dir = THUMBNAILS_DIR / video_id
    try:
        thumb_files = generate_thumbnails(file_path, thumb_dir)
    except Exception as e:
        print(f"[upload] Thumbnail generation failed: {e}")
        thumb_files = []

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


@router.post("/api/upload", response_model=UploadResponse)
async def upload_video(req: UploadRequest) -> UploadResponse:
    try:
        validate_video_file(req.file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _process_video(req.file_path)


@router.post("/api/upload-file", response_model=UploadResponse)
async def upload_video_file(file: UploadFile = File(...)) -> UploadResponse:
    """드래그&드롭용: multipart 파일 업로드를 받아 로컬에 저장 후 처리."""
    filename = file.filename or "video.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{filename}"

    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    return _process_video(str(save_path))
