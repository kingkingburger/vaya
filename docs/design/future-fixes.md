# Vaya MVP — Future Fix Items

**Date:** 2026-03-16
**Status:** Identified from PRD-to-implementation gap analysis
**Scope:** Items that are not bugs but need implementation in post-MVP or near-term patches

---

## FF-001: Output folder defaults to `storage/output` instead of `~/Videos/Vaya/`

**PRD Reference:** Scenario 5 — "출력 폴더: `~/Videos/Vaya/` (기본) + [변경] 버튼"
**Current Implementation:** `backend/services/exporter.py` line 12 uses `STORAGE_DIR / "output"` (relative path inside project). Frontend `openFolder` call passes `"storage/output"` hardcoded.
**Impact:** Export files end up in project-internal directory, not user-friendly location.
**Fix:** Set default output to `Path.home() / "Videos" / "Vaya"`, persist in `AppConfig`, and expose via settings API. Frontend should display the resolved path and support the [변경] button via `openFolderDialog()`.

---

## FF-002: No output folder [변경] (Change) button functionality

**PRD Reference:** Scenario 5 — "[변경] 버튼"
**Current Implementation:** The export panel shows a static path but no folder picker dialog is wired up.
**Impact:** Users cannot change the export destination folder.
**Fix:** Add `openFolderDialog` RPC handler in `src/bun/index.ts` and wire to the [변경] button in the export panel. Persist chosen path in `AppConfig.output_dir`.

---

## FF-003: Missing `merge_gap` and `min_silence_duration` UI controls

**PRD Reference:** Scenario 4 settings table — "병합 간격 (0-10s, default 2s)" and "무음 최소 길이 (0.5-5s, default 1.5s)"
**Current Implementation:** `main.ts` hardcodes `merge_gap: 2` and `min_silence_duration: 1.5` in `saveSettingsAndReanalyze()`. No slider/input elements exist in the HTML for these settings.
**Impact:** Users cannot adjust merge gap or minimum silence duration.
**Fix:** Add input controls for `merge_gap` and `min_silence_duration` to the settings panel HTML. Wire to the existing `saveSettingsAndReanalyze()` flow.

---

## FF-004: Whisper model download progress not shown

**PRD Reference:** Edge Case 11 — "Whisper 모델 첫 다운로드: 프로그레스에 'Downloading medium model (1.5GB)...' 표시"
**Current Implementation:** `subtitle_generator.py` calls `whisper.load_model()` which downloads internally without progress reporting. The analysis progress jumps from 95% to 99% during subtitle generation.
**Impact:** First-time users see a long stall at 95% with no explanation.
**Fix:** Intercept Whisper's download via `torch.hub` download hooks or pre-check model existence, then send a dedicated WebSocket progress message before loading.

---

## FF-005: No disk space check before export

**PRD Reference:** Scenario 5 exception — "디스크 공간 부족: 에러 토스트 + UI 복귀"
**Current Implementation:** `exporter.py` does not check available disk space before starting FFmpeg. If disk is full, FFmpeg will fail mid-process.
**Impact:** Unhelpful FFmpeg error instead of user-friendly disk space warning.
**Fix:** Before export, estimate required space (input file size * number of formats) and check `shutil.disk_usage()`. Return HTTP 400 with a clear message if insufficient.

---

## FF-006: Incomplete file cleanup on failed/interrupted export

**PRD Reference:** Edge Case 12 — "인코딩 중 앱 종료: 다음 실행 시 미완성 파일 정리 (MVP에서는 수동)"
**Current Implementation:** No cleanup logic exists. If export fails mid-process or app closes during export, partial `.mp4` files remain in the output directory.
**Impact:** Users accumulate corrupted partial files.
**Fix:** On app startup, scan output directory for files with `.tmp` extension (rename FFmpeg output to `.tmp` during encoding, rename to `.mp4` on success). Delete any `.tmp` files found on startup.

---

## FF-007: English language support not implemented

**PRD Reference:** Constraint — "Korean default language with English support planned"
**Current Implementation:** All UI strings are hardcoded Korean in `main.ts` and `index.html`. `subtitle_generator.py` hardcodes `language="ko"`. Config has `language: str = "ko"` but no UI to change it.
**Impact:** Non-Korean users cannot use the app effectively.
**Fix:** Extract all UI strings to a locale file (`i18n/ko.json`, `i18n/en.json`). Add language selector to settings. Pass selected language to Whisper transcription.

---

## FF-008: Export does not disable full UI during encoding

**PRD Reference:** Scenario 5 — "전체 UI 비활성화 (수정 불가)"
**Current Implementation:** `main.ts` disables only the export button during export. Timeline interaction, settings sliders, and highlight editing remain active.
**Impact:** Users can modify highlights/settings during export, causing potential inconsistency.
**Fix:** Add a global `isExporting` flag. When true, disable all interactive elements (timeline mousedown, settings inputs, highlight list actions). Re-enable on export complete or error.

---

## FF-009: File duplicate naming uses underscore instead of parentheses

**PRD Reference:** Scenario 5 — "동일 파일 존재 시: `gameplay_20260309_youtube(2).mp4` 번호 붙이기"
**Current Implementation:** `exporter.py` `_unique_path()` generates `filename_1.mp4`, `filename_2.mp4` (underscore + number, no parentheses).
**Impact:** Minor naming convention mismatch with PRD specification.
**Fix:** Change `_unique_path()` to use `f"{stem}({i}){suffix}"` format to match PRD.

---

## FF-010: Export `crop_offset` not passed from frontend correctly

**PRD Reference:** Scenario 5 & Edge Case 14 — Shorts crop offset slider for left/right adjustment
**Current Implementation:** Frontend sends `crop_offset` as integer from slider. Backend `exporter.py` uses it directly in FFmpeg `crop=608:1080:{crop_offset}:0`. However, the `ExportRequest` model in `models.py` may not include `crop_offset`, and the relationship between slider value and pixel offset needs validation.
**Impact:** Shorts crop offset may not work correctly or may be ignored.
**Fix:** Verify `ExportRequest` Pydantic model includes `crop_offset: int = 0`. Add validation that offset keeps crop window within source frame width. Test with actual video files.

---

## FF-011: Production PyInstaller exe branch not implemented in python-manager

**PRD Reference:** Constraint — "NSIS/Inno Setup installer with Whisper medium model included"
**Current Implementation:** `python-manager.ts` only supports `uv run` (dev) and `.venv/Scripts/python.exe` (fallback). No code path for a bundled PyInstaller `.exe`.
**Impact:** Production builds cannot start the Python backend without `uv` installed.
**Fix:** Add a third spawn branch: detect if `backend.exe` exists in the app resources directory, and spawn it directly. This is needed for the NSIS/Inno Setup installer distribution.

---

## FF-012: No auto-reconnect to backend on connection loss

**PRD Reference:** Phase 6 task — "백엔드 연결 끊김 상태 + 자동 재연결"
**Current Implementation:** WebSocket has auto-reconnect (2s delay). However, if the HTTP backend itself goes down, there is no detection or recovery. The frontend continues to show the main screen without realizing the backend is unavailable.
**Impact:** Users may attempt actions (analyze, export) that silently fail.
**Fix:** Add periodic health check polling (every 10s) when on main screen. On failure, show a reconnecting banner. After N consecutive failures, transition to error screen with retry button.

---

## FF-013: Manual segments not properly preserved on re-analysis

**PRD Reference:** Scenario 4 — "수동으로 추가/수정한 구간은 유지 (자동 구간만 재계산)"
**Current Implementation:** `saveSettingsAndReanalyze()` in `main.ts` filters `highlights.filter(h => h.manual)` but then calls `startAnalysis()` which replaces all highlights from server response in `fetchHighlights()`. The saved manual segments are never merged back.
**Impact:** Manual segments are lost when settings change triggers re-analysis.
**Fix:** After re-analysis completes and `fetchHighlights()` receives new auto-segments, merge the previously saved manual segments back into the highlights array. Alternatively, send manual segments to the backend so the analysis pipeline can exclude and re-append them.

---

## FF-014: Silence removal within highlights not applied during export

**PRD Reference:** Scenario 5 — "무음 제거: 하이라이트 구간 내부에서만 무음 구간 제거"
**Current Implementation:** `exporter.py` receives `silence_segments` parameter but `_build_filter_complex()` never uses it. The filter only trims and concatenates highlight segments without removing internal silence.
**Impact:** Exported videos retain silent pauses within highlight clips.
**Fix:** In `_build_filter_complex()`, for each highlight segment, intersect with silence segments and split the highlight into sub-segments excluding silence. Apply appropriate `trim`/`atrim` filters for each sub-segment before concatenation.
