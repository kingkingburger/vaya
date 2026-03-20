import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import load_config
from models import ExportRequest
from ws.progress import progress_manager

router = APIRouter()

# Per-video export lock (shared with analyze)
_exporting: set[str] = set()


def _get_store():
    from routers.upload import get_video_store
    return get_video_store()


class ExportResponse(BaseModel):
    status: str
    files: list[dict] = []


@router.post("/api/video/{video_id}/export", response_model=ExportResponse)
async def start_export(video_id: str, req: ExportRequest):
    store = _get_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    if video_id in _exporting:
        raise HTTPException(status_code=409, detail="Export already in progress")

    # Check analysis lock
    from routers.analyze import _analyzing
    if video_id in _analyzing:
        raise HTTPException(status_code=409, detail="Analysis in progress, cannot export")

    _exporting.add(video_id)
    asyncio.create_task(_run_export(video_id, req))

    return ExportResponse(status="started")


async def _run_export(video_id: str, req: ExportRequest):
    store = _get_store()
    info = store[video_id]["info"]
    highlights = store[video_id].get("highlights", [])
    silence = store[video_id].get("silence", [])

    if not highlights:
        await progress_manager.broadcast(video_id, "error", 0, "내보내기 실패: 하이라이트 구간이 없습니다. 먼저 분석을 실행하세요.")
        _exporting.discard(video_id)
        return
    config = load_config()

    # Determine subtitles path
    from pathlib import Path
    analysis_dir = Path(__file__).parent.parent / "storage" / "analysis" / video_id
    srt_path = analysis_dir / "subtitles.srt"
    subtitles_path = str(srt_path) if srt_path.exists() else None

    async def on_progress(stage: str, percent: float, message: str):
        await progress_manager.broadcast(video_id, stage, percent, message)

    try:
        from services.exporter import export_video

        results = await export_video(
            video_id=video_id,
            file_path=info.file_path,
            highlights=highlights,
            silence_segments=silence,
            subtitles_path=subtitles_path,
            config=config,
            youtube=req.youtube,
            shorts=req.shorts,
            subtitles=req.subtitles,
            progress_callback=on_progress,
        )

        store[video_id]["export_results"] = results
        await progress_manager.broadcast(video_id, "export_complete", 100, "내보내기 완료")

    except Exception as e:
        print(f"[export] Error: {e}")
        await progress_manager.broadcast(video_id, "error", 0, f"내보내기 실패: {e}")
    finally:
        _exporting.discard(video_id)


@router.get("/api/video/{video_id}/export/status")
async def get_export_status(video_id: str):
    store = _get_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    results = store[video_id].get("export_results", None)
    exporting = video_id in _exporting

    return {
        "exporting": exporting,
        "complete": results is not None and not exporting,
        "files": results or [],
    }
