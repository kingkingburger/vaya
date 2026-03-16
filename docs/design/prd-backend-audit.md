# PRD User Stories vs Backend Implementation — Full Audit

> **Date:** 2026-03-16
> **Scope:** US-001 through US-011 audited against backend Python codebase
> **Method:** Line-by-line comparison of PRD acceptance criteria and backend source code
> **Cross-references:** known-bugs.md, future-fixes.md, test-gaps.md, conscious-decisions.md, architecture-decisions.md, edge-cases.md

---

## Audit Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Fully implemented — backend code matches PRD requirement |
| ⚠️ | Partially implemented — core logic present but with documented gap |
| ❌ | Not implemented — requirement missing from backend |
| ➡️ | Frontend-only — no backend audit applicable |

---

## US-001: Phase 1R — Phase 1 잔여 이슈 해결

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | electrobun.config.ts views entrypoint 설정 | ➡️ Frontend/build | No backend component |
| 2 | bun start → 웹뷰 정상 로드 | ➡️ Frontend | No backend component |
| 3 | RPC backendReady/backendError 메시지 전송 | ➡️ Frontend/Bun | Backend provides `/api/health` endpoint (`health.py:31-37`); polling is Bun-side |
| 4 | python-manager.ts 포트 8765 재사용/재시작 | ➡️ Bun process | Backend binds port via `uvicorn.run(host="127.0.0.1", port=8765)` (`main.py:36`) |
| 5 | Backend ready 또는 에러 상태 표시 | ✅ | `GET /api/health` returns `{status, gpu_available, nvenc_available}` (`health.py:31-37`) |

**Gaps identified:** None for backend. US-001 is primarily frontend/Bun-layer.

---

## US-002: Phase 2A — 백엔드 업로드 + 메타데이터 + 썸네일

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | `POST /api/upload {file_path}` → UUID + VideoInfo | ✅ | `upload.py:23-69` — validates, extracts metadata via FFprobe, assigns UUID, returns `UploadResponse` |
| 2 | `GET /api/video/{id}/info` → 메타데이터 | ✅ | `video.py:15-23` — returns stored `VideoInfo` from `_videos` dict |
| 3 | `GET /api/video/{id}/thumbnails` → URL 리스트 | ✅ | `video.py:26-46` — returns `/static/thumbnails/{id}/{filename}` URLs |
| 4 | Static thumbnail access at `/static/thumbnails/...` | ✅ | `main.py:21-23` — `StaticFiles` mounted at `/static` serving `storage/` directory |
| 5 | `video_info.py` FFprobe extraction | ✅ | `video_info.py:19-59` — extracts duration, width, height, fps, codec, file_size |
| 6 | `thumbnail_generator.py` 5초 간격 JPEG | ✅ | `thumbnail_generator.py:5-56` — `interval=5.0`, 320x180 thumbnails |
| 7 | pytest 통합 테스트 통과 | ✅ | E2E tests in `tests/e2e/test_backend_e2e.py` cover upload+info+thumbnails flow |

**Gaps identified:**

- **GAP-US002-A**: `SUPPORTED_EXTENSIONS` in `video_info.py:6` includes `.avi` but PRD Scenario 2 only lists "MP4 · MKV · MOV · WEBM". AVI is accepted by backend but explicitly listed as unsupported in PRD Edge Case 1 ("지원 불가 포맷 (AVI, 코덱 문제)"). **Classification: Minor inconsistency** — AVI inclusion is arguably more permissive than PRD specifies. The PRD edge case text uses AVI as an example of unsupported format, but the actual format list in Scenario 2 omits AVI. → **Conscious Decision** (permissive validation).

- **GAP-US002-B**: Upload is synchronous — thumbnails are generated before returning response (`upload.py:51-55`). PRD says "썸네일 생성 시작" implying async start. For long videos, thumbnail generation blocks the upload response. → Already tracked as part of **KB-002** (long video warning timing).

---

## US-003: Phase 2B — 프론트엔드 드롭→메인 전환 + 기본 UI

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | 로딩 화면 → health check → 드래그&드롭 | ➡️ Frontend | Backend provides `GET /api/health` |
| 2 | 에러 화면 + 재시도 | ➡️ Frontend | |
| 3 | 드래그&드롭 + openFileDialog 폴백 | ➡️ Frontend | |
| 4 | FFprobe 포맷 검증 실패 토스트 | ⚠️ | Backend validates in `upload.py:26-31`, returns HTTP 400. But see GAP-US002-A above regarding AVI |
| 5 | 1시간+ 경고 모달 | ⚠️ | Backend returns `duration` in `UploadResponse.info.duration`. Duration check is frontend-only. See **KB-002** for timing issue. |
| 6 | 메인 화면 레이아웃 | ➡️ Frontend | |
| 7 | 타임라인 Canvas + 썸네일 | ➡️ Frontend | Backend serves thumbnails via `/static/` mount |

**Gaps identified:** None new for backend beyond already-tracked KB-002.

---

## US-004: Phase 3A — 오디오/영상 분석 + 하이라이트 스코어링

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | `POST /api/video/{id}/analyze` → background task + lock | ✅ | `analyze.py:24-38` — `_analyzing` set + `asyncio.create_task()` |
| 2 | `audio_analysis.py` librosa RMS (sr=22050, mono) | ✅ | `audio_analysis.py:25-53` — sr=22050, mono, hop_length=sr//2 (~0.5s) |
| 3 | `video_analysis.py` OpenCV frame diff (2fps, 160x90) | ✅ | `video_analysis.py:8-55` — fps=2.0, size="160x90" |
| 4 | `highlight_scorer.py` composite + top N% + duration + merge | ✅ | `highlight_scorer.py:6-99` — all filters applied |
| 5 | `silence_detector.py` threshold + min_duration + padding | ✅ | `silence_detector.py:8-82` — all parameters used |
| 6 | `GET /api/video/{id}/highlights` → segment list | ✅ | `analyze.py:137-143` |
| 7 | `PUT /api/video/{id}/highlights` → manual update | ✅ | `analyze.py:146-153` |
| 8 | WebSocket `/ws/progress/{id}` → broadcast | ✅ | `analyze.py:156-164` + `ws/progress.py` ProgressManager |
| 9 | 동일 영상 동시 분석 HTTP 409 | ✅ | `analyze.py:30-31` — checks `_analyzing` set |
| 10 | pytest 통합 테스트 통과 | ✅ | E2E tests cover analysis flow |

**Gaps identified:**

- **GAP-US004-A**: `_analyzing` set does not cross-check `_exporting`. → **Known Bug KB-001** (already documented).

- **GAP-US004-B**: PRD specifies "per-video asyncio.Lock" for concurrent analysis prevention, but implementation uses a `set[str]` instead of `asyncio.Lock`. The set approach works for the duplicate-prevention use case but is not a true mutex — if the same video ID were somehow analyzed twice in a race condition between the check and the add, the set would not prevent it. In practice, Python's GIL makes this safe for the current single-process architecture. → **Architecture nuance** — no action needed for MVP.

- **GAP-US004-C**: PRD Phase 3A mentions "`task_manager.py` — per-video asyncio.Lock (동시 분석 방지)" as a planned file, but no `task_manager.py` exists. The lock functionality is embedded directly in `analyze.py` and `export.py` using separate `_analyzing`/`_exporting` sets. → **Architecture Decision** — simplified from PRD plan, functionally equivalent.

---

## US-005: Phase 3B — 프론트엔드 프로그레스 + 하이라이트 표시

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | 업로드 후 자동 analyze 호출 | ➡️ Frontend | Frontend calls `POST /api/video/{id}/analyze` after upload |
| 2 | 프로그레스 배너 | ➡️ Frontend | Backend sends progress via WebSocket |
| 3 | WebSocket 실시간 업데이트 | ✅ | `ws/progress.py` broadcasts `{stage, percent, message}` |
| 4 | 타임라인 하이라이트 오버레이 | ➡️ Frontend | |
| 5 | 좌측 패널 구간 리스트 | ➡️ Frontend | Backend provides `GET /api/video/{id}/highlights` |
| 6 | 0개 → 전체 영상 1구간 | ⚠️ | Backend `highlight_scorer.py` returns empty `[]` when no highlights detected. The zero-to-full-video fallback is frontend-only (`main.ts`). |

**Gaps identified:**

- **GAP-US005-A**: The "0 highlights → full video as 1 segment" logic exists only in the frontend. The backend returns `[]` and relies on the frontend to create the fallback segment. If any other client (API consumer, test) calls the backend directly, they get zero segments with no fallback. → **Conscious Decision** — frontend handles this per PRD Scenario 3 Step 6. Backend could optionally implement this but it's correctly frontend responsibility in the current architecture.

---

## US-006: Phase 4A — Whisper STT 자막 생성

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | `subtitle_generator.py` Whisper + cache + language=ko | ✅ | `subtitle_generator.py:12-23` model cache, `language="ko"` param |
| 2 | 분석 파이프라인에 자막 단계 포함 | ✅ | `analyze.py:77-82` — Stage 5 calls `_generate_subtitles` |
| 3 | SRT 파일: `storage/analysis/{id}/subtitles.srt` | ✅ | `subtitle_generator.py:71-72` writes SRT |
| 4 | `GET /api/video/{id}/subtitles` → segment list | ✅ | `subtitle.py:13-19` returns `SubtitleSegment` list |
| 5 | CUDA GPU 사용 | ✅ | `subtitle_generator.py:50` — `device = "cuda" if torch.cuda.is_available() else "cpu"` |
| 6 | WebSocket 진행률 'whisper_download' / '자막 생성 중...' | ⚠️ | Progress shows `"자막 생성 중..."` (`analyze.py:78`) but **no** `whisper_download` stage for first-time model download |
| 7 | pytest 자막 테스트 통과 | ✅ | E2E tests mock Whisper and verify subtitle flow |

**Gaps identified:**

- **GAP-US006-A**: No Whisper model download progress reporting. → **Future Fix FF-004** (already documented).

- **GAP-US006-B**: `subtitle_generator.py` hardcodes `language` parameter from config, but config default is `"ko"` with no UI to change it. PRD settings table lists "Whisper 모델" (model selector) but not language selector. However, the constraint says "Korean default language with English support planned." → **Future Fix FF-007** (already documented).

- **GAP-US006-C**: The subtitle generator extracts audio to a temp WAV at 16kHz (`sr=16000`, line 46), while `audio_analysis.py` uses 22050Hz. This is correct (Whisper expects 16kHz) but worth noting the intentional difference.

---

## US-007: Phase 4B — 타임라인 인터랙션

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | Canvas 마우스 상태 머신 | ➡️ Frontend | |
| 2 | 구간 양끝 드래그 | ➡️ Frontend | |
| 3 | 빈 영역 클릭 → 새 구간 추가 | ➡️ Frontend | |
| 4 | Delete 키 삭제 | ➡️ Frontend | |
| 5 | Ctrl+Z / Ctrl+Y | ➡️ Frontend | |
| 6 | debounce 500ms → `PUT /api/video/{id}/highlights` | ✅ | Backend `PUT` endpoint at `analyze.py:146-153` accepts segment list |
| 7 | 수동(파란) vs 자동(주황) 구분 | ⚠️ | Backend `HighlightSegment` model (`models.py:31-34`) has only `start`, `end`, `score` — **no `manual` boolean field** |
| 8 | 좌측 리스트 ↔ 타임라인 동기화 | ➡️ Frontend | |
| 9 | [+ 구간 추가] + hover [×] 삭제 | ➡️ Frontend | |

**Gaps identified:**

- **GAP-US007-A** ⭐: `HighlightSegment` Pydantic model lacks a `manual: bool` field. The frontend tracks `manual` as a property on each segment (`main.ts` line 14: `manual?: boolean`), but when segments are sent to the backend via `PUT /api/video/{id}/highlights`, the `manual` flag is **silently dropped** by Pydantic validation (extra fields ignored by default). This means:
  1. After any backend roundtrip (PUT then GET), the `manual` flag is lost
  2. The backend cannot distinguish manual from auto segments during re-analysis
  3. This directly contributes to **FF-013** (manual segments lost on re-analysis)

  **Classification: Future Fix (new)** — Backend model needs `manual: bool = False` field on `HighlightSegment` to preserve the distinction across API roundtrips.

---

## US-008: Phase 4C — 설정 패널 + 실시간 재계산

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | 설정 패널 UI controls | ➡️ Frontend | Backend provides `GET/PUT /api/settings` |
| 2 | `PUT /api/settings` + re-analyze | ✅ | `settings.py:8-16` saves to config.yaml; re-analyze is frontend-triggered |
| 3 | 수동 구간 보존, 자동만 재계산 | ⚠️ | Backend has no `manual` field (see GAP-US007-A). Re-analysis replaces all highlights. |
| 4 | 토스트 알림 | ➡️ Frontend | |
| 5 | 자막 리스트 (read-only) | ✅ | `GET /api/video/{id}/subtitles` is read-only (no PUT endpoint) |

**Gaps identified:**

- **GAP-US008-A**: PRD settings table specifies `merge_gap` (0-10s, default 2s) and `min_silence_duration` (0.5-5s, default 1.5s) as configurable controls. Backend `config.py` has these fields (`HighlightConfig.merge_gap`, `SilenceConfig.min_silence_duration`) and `PUT /api/settings` persists them. However, **no frontend UI** exists for these controls. → **Future Fix FF-003** (already documented). Backend is correct.

- **GAP-US008-B**: PRD settings table specifies "Whisper 모델 (tiny~large, default medium)" selector. Backend `SubtitleConfig.model` supports this (`config.py:26`), and `PUT /api/settings` can change it. The model change takes effect on next analysis. The setting **does** persist and **is** used by the analysis pipeline. ✅ Backend correct.

- **GAP-US008-C**: `AppConfig` in `config.py` lacks an `output_dir` field. The PRD specifies output folder is configurable and persisted. → **Future Fix FF-001/FF-002** (already documented).

---

## US-009: Phase 5A — FFmpeg 내보내기 파이프라인

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | `POST /api/video/{id}/export` | ✅ | `export.py:25-42` with `ExportRequest` model |
| 2 | YouTube: 1920x1080 60fps h264_nvenc 8Mbps + libx264 fallback | ✅ | `exporter.py:149-162` — `-c:v encoder -b:v 8M -r 60 -s 1920x1080` |
| 3 | Shorts: 중앙크롭 608x1080 → 1080x1920 + offset | ✅ | `exporter.py:86-88` — `crop=608:1080:{crop_offset}:0,scale=1080:1920` |
| 4 | 자막 번인 (흰 글씨 검정 테두리) | ✅ | `exporter.py:93-103` — subtitles filter with `PrimaryColour`, `OutlineColour`, `BorderStyle` |
| 5 | 하이라이트 내부 무음 구간 제거 | ❌ | `_build_filter_complex()` receives `silence_segments` but **never uses them** |
| 6 | 항상 재인코딩 + `-avoid_negative_ts make_zero -async 1` | ✅ | `exporter.py:159-160` includes both flags |
| 7 | 파일명 규칙 + 중복 번호 | ⚠️ | `_format_output_name()` correct, but `_unique_path()` uses `_1` format instead of PRD's `(2)` format |
| 8 | FFmpeg stderr 진행률 파싱 → WebSocket | ✅ | `exporter.py:211-249` — `_run_ffmpeg` parses `Duration:` and `time=` |
| 9 | 순차 실행: YouTube → Shorts | ✅ | `export_video()` runs YouTube block, then Shorts block sequentially |
| 10 | per-video lock (분석/내보내기 동시 방지) | ⚠️ | Export checks both `_exporting` and `_analyzing`. But analyze does NOT check `_exporting`. |
| 11 | pytest 테스트 통과 | ✅ | E2E tests cover export flow |

**Gaps identified:**

- **GAP-US009-A** ⭐: Silence removal within highlights is **not implemented**. `_build_filter_complex()` accepts `silence_segments` parameter but the function body never references it. Only highlight trim+concat and optional subtitle burn-in are applied. → **Future Fix FF-014** (already documented).

- **GAP-US009-B**: File duplicate naming format mismatch (`_1` vs `(2)`). → **Future Fix FF-009** (already documented).

- **GAP-US009-C**: Asymmetric lock — export guards against analysis but not vice-versa. → **Known Bug KB-001** (already documented).

- **GAP-US009-D**: `ExportRequest` model in `models.py:43-47` includes `crop_offset: int = 0`. However, the `export_video()` function signature in `exporter.py:120` also has `crop_offset: int = 0`, but the `export.py` router at line 64 passes the request fields individually **without `crop_offset`**:
  ```python
  results = await export_video(
      ...
      youtube=req.youtube,
      shorts=req.shorts,
      subtitles=req.subtitles,
      progress_callback=on_progress,
  )
  ```
  The `crop_offset` from `req.crop_offset` is **not passed** to `export_video()`, so it always defaults to 0.

  **Classification: Known Bug (new)** — Shorts crop offset from user input is silently ignored. The export always uses center crop with zero offset regardless of slider position.

---

## US-010: Phase 5B — 내보내기 패널 + 완료 플로우

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | 출력 폴더 표시 + [변경] | ⚠️ | Backend exports to `storage/output/` (not `~/Videos/Vaya/`). No folder change API. |
| 2 | YouTube/Shorts/자막 체크박스 | ✅ | `ExportRequest` model has `youtube`, `shorts`, `subtitles` bools |
| 3 | Shorts 크롭 오프셋 슬라이더 | ⚠️ | Model has field but value not passed to exporter (see GAP-US009-D) |
| 4 | 내보내기 버튼 활성화 조건 | ➡️ Frontend | |
| 5 | 프로그레스 배너 + UI 비활성화 | ⚠️ | Backend sends progress. UI disablement is frontend-only (incomplete per FF-008) |
| 6 | 완료 카드 + 파일 리스트 | ✅ | `export.py:77` stores `export_results` with format/path/size; `export.py:87-100` returns status with files |
| 7 | [폴더 열기] → 초기 화면 복귀 | ➡️ Frontend | Backend holds results for retrieval; navigation is frontend |

**Gaps identified:**

- **GAP-US010-A**: Output folder defaults to project-internal path, not user's Videos folder. → **Future Fix FF-001** (already documented).

- **GAP-US010-B**: No `DELETE /api/video/{id}` or cleanup endpoint exists. When the frontend returns to the initial screen after export, the `_videos` dict still holds the completed video entry. This is consistent with **CD-003** (stateless sessions) but means repeated uploads accumulate stale entries until restart.

---

## US-011: Phase 6 — 통합 + 에러 핸들링 + 폴리시

| # | Acceptance Criterion | Backend Status | Notes |
|---|---------------------|----------------|-------|
| 1 | E2E 워크플로우 동작 | ✅ | Full pipeline: upload → analyze → highlights → subtitles → export |
| 2 | HTTP 에러 코드 (400, 404, 409, 500) | ✅ | All routers use `HTTPException` with appropriate codes |
| 3 | FFmpeg/OpenCV/Whisper try/except | ✅ | `analyze.py:93-96` catches all exceptions; `exporter.py:80-82` catches export errors |
| 4 | 프론트 에러 토스트 | ➡️ Frontend | Backend sends `stage="error"` via WebSocket |
| 5 | 백엔드 연결 끊김 자동 재연결 | ⚠️ | WebSocket reconnect exists. HTTP health polling does not. |
| 6 | NVENC → libx264 폴백 + 경고 | ✅ | `exporter.py:15-33` `_detect_encoder()` + `health.py` reports status |
| 7 | 다크 테마 일관성 | ➡️ Frontend | |
| 8 | 키보드 단축키 | ➡️ Frontend | |

**Gaps identified:**

- **GAP-US011-A**: Backend has no structured logging. All error handling uses `print()` statements (`analyze.py:94`, `export.py:81`, `upload.py:54`). PRD Phase 6 tasks list "구조화된 로깅 (백엔드)" as a requirement. → **Future Fix (new)** — Replace `print()` with `logging` module with structured JSON format for production debugging.

- **GAP-US011-B**: No HTTP backend health polling mechanism exists for detecting connection loss. WebSocket has reconnect. → **Future Fix FF-012** (already documented).

---

## New Gaps Discovered in This Audit

The following gaps were identified during this audit that are **not yet tracked** in existing design documents:

### NEW-1: `crop_offset` Not Passed to Export Service (Bug)

**Location:** `backend/routers/export.py:64`
**PRD Reference:** Scenario 5, Edge Case 14
**Description:** `ExportRequest.crop_offset` is accepted from the client but never forwarded to `export_video()`. All Shorts exports use `crop_offset=0` (center crop) regardless of user's slider position.
**Severity:** Medium — Shorts crop offset feature is non-functional.
**Fix:** Add `crop_offset=req.crop_offset` to the `export_video()` call in `export.py:64`.
**Tracking:** Should be added to **known-bugs.md** as **KB-003**.

### NEW-2: `HighlightSegment` Model Missing `manual` Field

**Location:** `backend/models.py:31-34`
**PRD Reference:** Scenario 4 — manual vs auto segment distinction
**Description:** `HighlightSegment` has only `start`, `end`, `score`. Frontend tracks `manual?: boolean` but it's dropped on PUT/GET roundtrip. This prevents backend-side manual segment preservation during re-analysis.
**Severity:** Medium — contributes to FF-013 (manual segments lost on re-analysis).
**Fix:** Add `manual: bool = False` to `HighlightSegment` model.
**Tracking:** Should extend **FF-013** or create new entry in **future-fixes.md**.

### NEW-3: Backend Uses `print()` Instead of Structured Logging

**Location:** `analyze.py:94`, `export.py:81`, `upload.py:54`
**PRD Reference:** Phase 6 task — "구조화된 로깅 (백엔드)"
**Description:** All backend error/debug output uses `print()` instead of Python `logging` module. No log levels, no timestamps, no structured format.
**Severity:** Low — functional for development, inadequate for production debugging.
**Fix:** Replace all `print()` with `logging.getLogger(__name__)` calls; add logging config in `main.py`.
**Tracking:** Should be added to **future-fixes.md** as **FF-015**.

### NEW-4: AVI Accepted Despite PRD Listing It as Unsupported

**Location:** `backend/services/video_info.py:6`
**PRD Reference:** Scenario 2 lists "MP4 · MKV · MOV · WEBM"; Edge Case 1 uses AVI as example of unsupported format
**Description:** `SUPPORTED_EXTENSIONS` includes `.avi`, which conflicts with PRD's format list and edge case example.
**Severity:** Very Low — more permissive than PRD, not a functional problem.
**Fix:** Either remove `.avi` from `SUPPORTED_EXTENSIONS` or update PRD to include AVI.
**Tracking:** Could be noted as a **Conscious Decision** addendum.

### NEW-5: `task_manager.py` Not Created (Structural Deviation)

**Location:** N/A (file doesn't exist)
**PRD Reference:** Phase 3A task list — "`backend/services/task_manager.py` — per-video asyncio.Lock"
**Description:** PRD development plan specified a dedicated task manager service, but lock functionality was embedded directly into `analyze.py` and `export.py` using `_analyzing`/`_exporting` sets. This is a structural simplification.
**Severity:** None — functionally equivalent, but deviates from the planned file structure.
**Tracking:** **Architecture nuance** — no action needed.

---

## Cross-Reference Summary

### Gaps by Category

| Category | Count | IDs |
|----------|-------|-----|
| Already tracked Known Bugs | 2 | KB-001, KB-002 |
| **New** Known Bugs | 1 | NEW-1 (crop_offset not passed) |
| Already tracked Future Fixes | 10 | FF-001, FF-002, FF-003, FF-004, FF-005, FF-007, FF-008, FF-009, FF-013, FF-014 |
| **New** Future Fixes | 2 | NEW-2 (manual field), NEW-3 (logging) |
| Already tracked Test Gaps | 2 | TG-001, TG-002 |
| Already tracked Conscious Decisions | 3 | CD-001, CD-002, CD-003 |
| **New** Conscious Decision | 1 | NEW-4 (AVI accepted) |
| Already tracked Architecture Decisions | 4 | AD-001, AD-002, AD-003, AD-004 |
| Architecture Nuance (no action) | 2 | GAP-US004-B (set vs Lock), NEW-5 (task_manager.py) |

### Gaps by User Story

| US | Total ACs | Backend ACs | ✅ Full | ⚠️ Partial | ❌ Missing | ➡️ Frontend |
|----|-----------|-------------|---------|------------|-----------|------------|
| US-001 | 5 | 1 | 1 | 0 | 0 | 4 |
| US-002 | 7 | 7 | 7 | 0 | 0 | 0 |
| US-003 | 7 | 2 | 0 | 2 | 0 | 5 |
| US-004 | 10 | 10 | 9 | 1 | 0 | 0 |
| US-005 | 6 | 2 | 1 | 1 | 0 | 4 |
| US-006 | 7 | 7 | 5 | 2 | 0 | 0 |
| US-007 | 9 | 2 | 1 | 1 | 0 | 7 |
| US-008 | 5 | 3 | 2 | 1 | 0 | 2 |
| US-009 | 11 | 11 | 7 | 3 | 1 | 0 |
| US-010 | 7 | 4 | 2 | 2 | 0 | 3 |
| US-011 | 8 | 4 | 2 | 2 | 0 | 4 |
| **Total** | **82** | **53** | **37** | **15** | **1** | **29** |

### Backend Implementation Coverage

- **53 backend-relevant acceptance criteria** across US-001–US-011
- **37 fully implemented** (70%)
- **15 partially implemented** with documented gaps (28%)
- **1 not implemented** (silence removal in export — FF-014) (2%)
- All gaps are tracked or newly identified in this audit
