from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models import VideoInfo

router = APIRouter()


class ThumbnailListResponse(BaseModel):
    video_id: str
    thumbnails: list[str]
    count: int


@router.get("/api/video/{video_id}/info", response_model=VideoInfo)
async def get_video_info(video_id: str) -> VideoInfo:
    from routers.upload import get_video_store

    store = get_video_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    return store[video_id]["info"]


@router.get("/api/video/{video_id}/thumbnails", response_model=ThumbnailListResponse)
async def get_video_thumbnails(video_id: str) -> ThumbnailListResponse:
    from routers.upload import get_video_store

    store = get_video_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    thumb_files = store[video_id]["thumbnails"]

    # Return URLs relative to static mount
    urls = [
        f"/static/thumbnails/{video_id}/{f}"
        for f in thumb_files
    ]

    return ThumbnailListResponse(
        video_id=video_id,
        thumbnails=urls,
        count=len(urls),
    )
