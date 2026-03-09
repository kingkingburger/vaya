from fastapi import APIRouter, HTTPException

from models import SubtitleSegment

router = APIRouter()


def _get_store():
    from routers.upload import get_video_store
    return get_video_store()


@router.get("/api/video/{video_id}/subtitles", response_model=list[SubtitleSegment])
async def get_subtitles(video_id: str) -> list[SubtitleSegment]:
    store = _get_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    return store[video_id].get("subtitles", [])
