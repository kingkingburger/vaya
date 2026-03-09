# Vaya - Game Video Auto-Editing Desktop App

## Tech Stack
- **Frontend**: Electrobun (TypeScript + Bun) + WebView2
- **Backend**: Python FastAPI (localhost:8765)
- **Package Managers**: bun (frontend), uv (backend Python)
- **Video Processing**: FFmpeg/FFprobe, OpenCV, librosa
- **STT**: Whisper (CUDA accelerated, Korean)

## Project Structure
```
src/bun/           # Main process (Electrobun Bun side)
src/views/main/    # WebView frontend (HTML/CSS/TS)
backend/           # Python FastAPI server
  routers/         # API endpoints (health, settings, upload, video, analyze, subtitle, export)
  services/        # Business logic (video_info, thumbnail, audio/video analysis, highlight, silence, subtitle, exporter)
  ws/              # WebSocket progress manager
  tests/           # pytest tests
  storage/         # Runtime data (thumbnails, analysis, output)
docs/              # PRD, requirements
```

## Commands
```bash
# Backend
cd backend && uv run uvicorn main:app --host 127.0.0.1 --port 8765
cd backend && uv run pytest              # Run tests (34 tests)

# Frontend
npx electrobun dev                        # Dev mode
npx electrobun build                      # Production build
```

## Architecture
- RPC: Electrobun BrowserView.defineRPC for main↔webview communication
- Backend API: REST + WebSocket on port 8765
- In-memory store: `_videos: dict[str, dict]` (no database for MVP)
- WebSocket: `/ws/progress/{video_id}` for real-time progress
- Static files: `/static/thumbnails/{id}/` for thumbnail serving

## Conventions
- Routers register in `backend/main.py`
- Each feature follows: service → router → test → register pattern
- Tests mock FFmpeg/OpenCV/Whisper (no external deps needed for tests)
- Frontend uses screen state machine (loading/error/drop/main)
- Canvas API for timeline rendering
- CSS variables for dark theme consistency
