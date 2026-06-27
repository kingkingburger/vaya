# Vaya - Game Video Auto-Editing Desktop App

## Tech Stack
- **Desktop Shell**: Tauri v2 (Rust + WebView2 on Windows)
- **Frontend**: TypeScript + Vite + HTML/CSS/Canvas
- **Backend**: Python FastAPI (localhost:8765)
- **Package Managers**: bun (frontend/Tauri CLI), cargo (Rust shell), uv (backend Python)
- **Video Processing**: FFmpeg/FFprobe, OpenCV, librosa
- **STT**: Whisper (CUDA accelerated, Korean)

## Project Structure
```
src-tauri/         # Tauri Rust desktop shell and backend process manager
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
cd backend && uv run pytest              # Run tests (45 tests)

# Frontend
bun run start                             # Tauri dev mode (starts Vite + Rust shell)
bun run build:frontend                    # Vite frontend build
bun run build:backend-sidecar             # Build PyInstaller backend sidecar for Tauri bundle
bun run build                             # Tauri production build (frontend + backend sidecar)
bun run typecheck                         # TypeScript check
cd src-tauri && cargo check               # Rust shell check

# E2E Tests (backend 실행 상태에서)
cd backend && uv run pytest ../tests/e2e/test_backend_e2e.py -v   # 백엔드 E2E (15 tests)
cd backend && uv run pytest ../tests/e2e/test_frontend_e2e.py -v  # 프론트엔드 Playwright E2E (15 tests)
cd backend && uv run pytest ../tests/e2e/ -v                      # 전체 E2E (30 tests)
```

## Architecture
- Desktop shell: Tauri Rust commands via `@tauri-apps/api/core`
- Backend lifecycle: Tauri starts/reuses the local FastAPI backend on port 8765
- Backend API: REST + WebSocket on port 8765
- In-memory store: `_videos: dict[str, dict]` (no database for MVP)
- WebSocket: `/ws/progress/{video_id}` for real-time progress
- Static files: `/static/thumbnails/{id}/` for thumbnail serving

## E2E 테스트 아키텍처
- `tests/e2e/serve_frontend.py`: Vite build output을 Playwright용 정적 서버로 서빙
- `tests/e2e/conftest.py`: backend(8765) + frontend(8766) 서버 자동 시작/종료
- `tests/fixtures/sample.mp4`: 10초 테스트 비디오 (640x360, 30fps)
- Browser E2E에서는 Tauri IPC를 테스트용 `window.__TAURI_INTERNALS__.invoke` 목으로 대체

## Conventions
- Routers register in `backend/main.py`
- Each feature follows: service → router → test → register pattern
- Tests mock FFmpeg/OpenCV/Whisper (no external deps needed for tests)
- Frontend uses screen state machine (loading/error/drop/main)
- Canvas API for timeline rendering
- CSS variables for dark theme consistency
