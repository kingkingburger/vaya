import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from models import HighlightSegment, SubtitleSegment
from config import load_config
from ws.progress import progress_manager

STORAGE_DIR = Path(__file__).parent.parent / "storage"
ANALYSIS_DIR = STORAGE_DIR / "analysis"

router = APIRouter()

# Per-video analysis lock
_analyzing: set[str] = set()


def _get_store():
    from routers.upload import get_video_store
    return get_video_store()


@router.post("/api/video/{video_id}/analyze")
async def start_analysis(video_id: str):
    store = _get_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    if video_id in _analyzing:
        raise HTTPException(status_code=409, detail="Analysis already in progress")

    _analyzing.add(video_id)

    # Run analysis in background task
    asyncio.create_task(_run_analysis(video_id))

    return {"status": "started", "video_id": video_id}


async def _run_analysis(video_id: str):
    """Background analysis pipeline."""
    store = _get_store()
    info = store[video_id]["info"]
    file_path = info.file_path
    config = load_config()

    try:
        # Stage 1: Audio analysis (0-40%)
        await progress_manager.broadcast(video_id, "audio", 0, "오디오 추출 중...")
        audio_scores = await asyncio.to_thread(
            _analyze_audio, file_path
        )
        await progress_manager.broadcast(video_id, "audio", 40, "오디오 분석 완료")

        # Stage 2: Video analysis (40-70%)
        await progress_manager.broadcast(video_id, "video", 40, "영상 분석 중...")
        video_scores = await asyncio.to_thread(
            _analyze_video, file_path
        )
        await progress_manager.broadcast(video_id, "video", 70, "영상 분석 완료")

        # Stage 3: Highlight scoring (70-85%)
        await progress_manager.broadcast(video_id, "scoring", 70, "하이라이트 스코어링 중...")
        highlights = await asyncio.to_thread(
            _compute_highlights, audio_scores, video_scores, info.duration, config.highlight
        )
        await progress_manager.broadcast(video_id, "scoring", 85, "하이라이트 스코어링 완료")

        # Stage 4: Silence detection (85-100%)
        await progress_manager.broadcast(video_id, "silence", 85, "무음 구간 감지 중...")
        silence_segments = await asyncio.to_thread(
            _detect_silence, file_path, config.silence
        )
        await progress_manager.broadcast(video_id, "silence", 95, "무음 구간 감지 완료")

        # Stage 5: Subtitle generation (95-100%)
        await progress_manager.broadcast(video_id, "subtitle", 95, "자막 생성 중...")
        subtitles = await asyncio.to_thread(
            _generate_subtitles, file_path, video_id, config.subtitle
        )
        await progress_manager.broadcast(video_id, "subtitle", 99, "자막 생성 완료")

        # Store results
        store[video_id]["highlights"] = [
            HighlightSegment(**h) for h in highlights
        ]
        store[video_id]["silence"] = silence_segments
        store[video_id]["subtitles"] = subtitles

        await progress_manager.broadcast(video_id, "complete", 100, "분석 완료")

    except Exception as e:
        print(f"[analyze] Error analyzing {video_id}: {e}")
        await progress_manager.broadcast(video_id, "error", 0, f"분석 실패: {e}")
    finally:
        _analyzing.discard(video_id)


def _analyze_audio(file_path: str):
    from services.audio_analysis import analyze_audio_energy
    return analyze_audio_energy(file_path)


def _analyze_video(file_path: str):
    from services.video_analysis import analyze_frame_difference
    return analyze_frame_difference(file_path)


def _compute_highlights(audio_scores, video_scores, duration, highlight_config):
    from services.highlight_scorer import compute_highlights
    return compute_highlights(audio_scores, video_scores, duration, highlight_config)


def _detect_silence(file_path: str, silence_config):
    from services.silence_detector import detect_silence
    return detect_silence(
        file_path,
        threshold_db=silence_config.threshold_db,
        min_duration=silence_config.min_silence_duration,
        padding=silence_config.padding,
    )


def _generate_subtitles(file_path: str, video_id: str, subtitle_config):
    from services.subtitle_generator import generate_subtitles
    output_dir = ANALYSIS_DIR / video_id
    segments = generate_subtitles(
        file_path,
        output_dir=output_dir,
        model_name=subtitle_config.model,
        language=subtitle_config.language,
    )
    return [SubtitleSegment(**s) for s in segments]


@router.get("/api/video/{video_id}/highlights", response_model=list[HighlightSegment])
async def get_highlights(video_id: str) -> list[HighlightSegment]:
    store = _get_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    return store[video_id].get("highlights", [])


@router.put("/api/video/{video_id}/highlights")
async def update_highlights(video_id: str, segments: list[HighlightSegment]):
    store = _get_store()
    if video_id not in store:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    store[video_id]["highlights"] = segments
    return {"status": "updated", "count": len(segments)}


@router.websocket("/ws/progress/{video_id}")
async def ws_progress(websocket: WebSocket, video_id: str):
    await progress_manager.connect(video_id, websocket)
    try:
        while True:
            # Keep connection alive, wait for client messages (or disconnect)
            await websocket.receive_text()
    except WebSocketDisconnect:
        progress_manager.disconnect(video_id, websocket)
