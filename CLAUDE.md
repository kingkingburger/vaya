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

# E2E Tests (backend 실행 상태에서)
cd backend && uv run pytest ../tests/e2e/test_backend_e2e.py -v   # 백엔드 E2E (15 tests)
cd backend && uv run pytest ../tests/e2e/test_frontend_e2e.py -v  # 프론트엔드 Playwright E2E (15 tests)
cd backend && uv run pytest ../tests/e2e/ -v                      # 전체 E2E (30 tests)
```

## Architecture
- RPC: Electrobun BrowserView.defineRPC for main↔webview communication
- Backend API: REST + WebSocket on port 8765
- In-memory store: `_videos: dict[str, dict]` (no database for MVP)
- WebSocket: `/ws/progress/{video_id}` for real-time progress
- Static files: `/static/thumbnails/{id}/` for thumbnail serving

## E2E 테스트 아키텍처
- `tests/e2e/electrobun_mock.js`: Electroview 클래스를 HTTP 직접 호출로 대체하는 목
- `tests/e2e/serve_frontend.py`: 빌드된 main.js에서 Electroview를 regex로 목으로 교체하여 서빙
- `tests/e2e/conftest.py`: backend(8765) + frontend(8766) 서버 자동 시작/종료
- `tests/fixtures/sample.mp4`: 10초 테스트 비디오 (640x360, 30fps)
- Electrobun RPC 프로토콜: `{type:'message', id:name, payload:data}`, `{type:'response', id, success, payload}`
- 목의 `defineRPC`는 번들에 보존된 `defineElectrobunRPC`에 위임

## Conventions
- Routers register in `backend/main.py`
- Each feature follows: service → router → test → register pattern
- Tests mock FFmpeg/OpenCV/Whisper (no external deps needed for tests)
- Frontend uses screen state machine (loading/error/drop/main)
- Canvas API for timeline rendering
- CSS variables for dark theme consistency
