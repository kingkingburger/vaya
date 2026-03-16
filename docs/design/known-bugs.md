# Known Bugs — PRD vs Implementation

> Classification: **Known Bugs**
> Date: 2026-03-16
> Scope: Vaya MVP (11 user stories, US-001–US-011)

---

## KB-001: analyze.py Missing `_exporting` Cross-Check

**PRD Reference**: "per-video lock (분석/내보내기 동시 불가)" (PRD §Phase 5A)

**Bug Description**:
The export router (`backend/routers/export.py:35-37`) correctly cross-checks the `_analyzing` set before starting an export:

```python
# export.py — correctly checks both locks
if video_id in _exporting:
    raise HTTPException(status_code=409, detail="Export already in progress")

from routers.analyze import _analyzing
if video_id in _analyzing:
    raise HTTPException(status_code=409, detail="Analysis in progress, cannot export")
```

However, the analyze router (`backend/routers/analyze.py:30-31`) only checks its own `_analyzing` set and does **not** cross-check `_exporting`:

```python
# analyze.py — missing _exporting cross-check
if video_id in _analyzing:
    raise HTTPException(status_code=409, detail="Analysis already in progress")

# BUG: No check for _exporting — analysis can start while export is running
_analyzing.add(video_id)
```

**Root Cause**: Asymmetric lock checking — export guards against analysis, but analysis does not guard against export.

**Impact**: If a user triggers a settings change (which re-runs analysis via `POST /api/video/{id}/analyze`) while an export is in progress, both operations will run concurrently on the same video. This can cause:
1. **Data race on `store[video_id]["highlights"]`** — analysis overwrites highlights while export reads them
2. **Resource contention** — both FFmpeg export and CPU-bound analysis compete for GPU/CPU, potentially causing OOM or slowdowns
3. **Inconsistent state** — export completes with stale highlights, then analysis updates them, confusing the user

**Reproduction Steps**:
1. Upload a video and complete analysis
2. Start export (`POST /api/video/{id}/export`)
3. While export is in progress, change a setting slider (triggers `POST /api/video/{id}/analyze`)
4. Both requests succeed with HTTP 200 — analysis starts despite active export

**Expected Behavior**: `POST /api/video/{id}/analyze` should return HTTP 409 with "Export in progress, cannot analyze" when `video_id in _exporting`.

**Fix**:
Add the following cross-check to `backend/routers/analyze.py`, after the existing `_analyzing` check (line 31):

```python
# Add after line 31 in analyze.py
from routers.export import _exporting
if video_id in _exporting:
    raise HTTPException(status_code=409, detail="Export in progress, cannot analyze")
```

**Priority**: High — data race can produce corrupt export output.

**Affected PRD Edge Cases**: EC-9 (settings change during active session), EC-12 (export in progress)

---

## KB-002: Long Video Warning Modal Shows After Upload Completes

**PRD Reference**: PRD §Scenario 2, Step 5: "영상이 1시간 이상이면: 경고 모달 [...] 취소 → 드래그&드롭 화면 유지"

**Bug Description**:
The PRD specifies that the long-video warning modal should appear as a gate **before proceeding** with the upload workflow. The intent is: if the user cancels, the system should remain in the drag-and-drop state with no side effects.

However, in the current implementation (`src/views/main/main.ts:1022-1032`), the flow is:

```typescript
// Step 1: Upload ALREADY happens (RPC call, backend creates UUID, generates thumbnails)
const result = await electroview.rpc.request.uploadVideo({ filePath });
const info = result.info;

// Step 2: Warning modal shown AFTER upload is complete
if (info.duration > 3600) {
    const proceed = await showModal("긴 영상 경고", `이 영상은 약 ${hours}시간입니다...`);
    if (!proceed) return;  // BUG: upload already completed, resources leaked
}
```

**Root Cause**: The warning check requires `info.duration` from the backend response, so the upload must happen first to get metadata. However, when the user cancels:

1. **Backend resource leak**: The video entry remains in the in-memory `_videos` dict with UUID, metadata, and generated thumbnails. There is no cleanup API call, and since session persistence is intentionally absent, this orphaned entry persists until the app is restarted.
2. **Thumbnail disk waste**: 5-second interval JPEG thumbnails have already been written to `storage/thumbnails/{id}/` and are never cleaned up.
3. **Inconsistent UI state**: The frontend returns to drag-and-drop, but the backend still holds the video. If the user uploads the same file again, a new UUID is created (duplicate entry).

**Impact**:
- For a 3-hour video, thumbnail generation produces ~2,160 thumbnails before the user even sees the warning
- Memory accumulates with each cancelled upload (no garbage collection on `_videos` dict)
- Minor UX confusion: the PRD promises "드래그&드롭 화면 유지" on cancel, implying no side effects occurred

**Reproduction Steps**:
1. Drag a 3+ hour video file onto the app
2. Wait for upload to complete (thumbnails generate)
3. Warning modal appears: "이 영상은 약 3.0시간입니다..."
4. Click [취소] (Cancel)
5. Observe: drag-and-drop screen returns, but `GET /api/video/{id}/info` still returns the video; `storage/thumbnails/{id}/` contains orphaned files

**Expected Behavior (two options)**:
- **Option A (Preferred)**: Split upload into two phases — (1) lightweight metadata-only probe via FFprobe (no UUID, no thumbnails), (2) show warning if >1hr, (3) on confirm, proceed with full upload + thumbnail generation
- **Option B (Quick fix)**: On modal cancel, call a cleanup endpoint (`DELETE /api/video/{id}`) to remove the orphaned entry and thumbnails

**Priority**: Medium — resource leak is bounded by app restart cycle (stateless session design), but UX contract with PRD is violated.

**Affected PRD Edge Cases**: EC-2 (3시간 영상 업로드), EC-10 (10GB+ 대용량 파일)

---

## Summary

| ID | Bug | Severity | PRD Section | Fix Complexity |
|---|---|---|---|---|
| KB-001 | `analyze.py` missing `_exporting` cross-check → data race | High | §Phase 5A per-video lock | Low (3-line fix) |
| KB-002 | Long video warning modal fires after upload completes → resource leak on cancel | Medium | §Scenario 2 Step 5, EC-2 | Medium (API refactor or cleanup endpoint) |
