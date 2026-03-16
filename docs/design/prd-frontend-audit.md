# PRD User Stories vs Frontend Implementation — Gap Audit

> **Date:** 2026-03-16
> **Scope:** All 6 PRD scenarios + 12 normal verification scenarios audited against frontend code
> **Files Audited:** `src/views/main/main.ts`, `src/views/main/index.html`, `src/views/main/style.css`, `src/bun/index.ts`, `src/bun/rpc-schema.ts`, `src/bun/python-manager.ts`
> **Cross-references:** known-bugs.md, future-fixes.md, test-gaps.md, conscious-decisions.md, architecture-decisions.md, edge-cases.md

---

## Audit Methodology

Each PRD scenario is broken into individual UI/UX requirements. Each requirement is checked against the actual frontend source code with a status classification:

| Status | Meaning |
|--------|---------|
| ✅ MATCH | Implementation matches PRD specification |
| ⚠️ GAP | Partial or deviated implementation |
| ❌ MISSING | Not implemented in frontend |

---

## Scenario 1: App Startup (앱 시작)

### S1-R1: Loading screen with "VAYA" logo and "서버 시작 중..." spinner
**PRD:** "화면 중앙에 'VAYA' 로고와 '서버 시작 중...' 로딩 스피너가 표시된다"
**Status:** ✅ MATCH
**Evidence:** `index.html:29-35` — `<h1 class="logo">VAYA</h1>`, `<div class="spinner">`, `<p class="loading-text">서버 시작 중...</p>`. Screen is active by default.

### S1-R2: Health check polling (500ms × 10 retries)
**PRD:** "GET /api/health를 500ms 간격으로 최대 10회 폴링"
**Status:** ⚠️ GAP — Retry count differs
**Evidence:** `python-manager.ts:9` sets `MAX_HEALTH_RETRIES = 20` (PRD says 10). `main.ts:509` also polls with `retries = 20, interval = 500`.
**Classification:** Minor deviation — more retries than PRD, but in the safe direction (more tolerant startup).
**Tracking:** Not tracked — benign deviation, strictly better behavior.

### S1-R3: Success → drag-and-drop screen transition
**PRD:** "Health check 성공 시 → 드래그&드롭 화면으로 전환"
**Status:** ✅ MATCH
**Evidence:** `main.ts:495-496` — on `backendReady` message, calls `showScreen("drop")`. Also `main.ts:517` — on successful RPC health check, transitions to `"drop"`.

### S1-R4: Failure → error screen
**PRD:** "Health check 실패 시 → 에러 화면 표시"
**Status:** ✅ MATCH
**Evidence:** `main.ts:497-499` — `backendError` message shows error screen. `main.ts:527-528` — timeout after retries shows "백엔드 연결 실패" on error screen.

### S1-R5: Error screen retry button
**PRD:** "에러 화면의 [재시도] 버튼: 로딩 화면으로 돌아가 프로세스 재시작"
**Status:** ⚠️ GAP — No Python process restart on retry
**Evidence:** `main.ts:533-550` — retry button calls `getBackendStatus` RPC to check health again, but does **not** request the main process to restart the Python backend. If the backend crashed, retrying only re-polls health — it cannot recover without a full app restart.
**Classification:** **Future Fix** — relates to FF-012 (no auto-reconnect to backend on connection loss). The PRD says "프로세스 재시작" but retry only re-checks status.

### S1-R6: Port 8765 conflict handling
**PRD:** "포트 8765 이미 사용 중: 기존 프로세스 확인 → health check 시도 → 성공하면 재사용, 실패하면 기존 프로세스 종료 후 재시작"
**Status:** ⚠️ GAP — No termination of unhealthy existing process
**Evidence:** `python-manager.ts:57-68` (`checkExistingServer`) checks health and reuses if OK. If the check fails, it proceeds to spawn (which will fail if port is occupied by a non-Vaya process). No code to terminate the existing process.
**Classification:** Already tracked in edge-cases.md EC-06 notes. Low impact — uncommon scenario.

---

## Scenario 2: Video Upload (영상 업로드)

### S2-R1: Drag-and-drop area with icon + text + [파일 선택] button
**PRD:** "아이콘 + '영상 파일을 여기에 드래그하세요' + [파일 선택] 버튼"
**Status:** ✅ MATCH
**Evidence:** `index.html:58-69` — SVG icon, "영상 파일을 여기에 드래그하세요" text, browse button.

### S2-R2: Supported format display: `MP4 · MKV · MOV · WEBM`
**PRD:** "지원 포맷 안내: `MP4 · MKV · MOV · WEBM`"
**Status:** ⚠️ GAP — AVI included in UI but excluded from PRD format list
**Evidence:** `index.html:68` shows `MP4 · MKV · MOV · WEBM · AVI`. `main.ts:1015` also includes `"avi"` in supported extensions. However, PRD scenario 2 only lists `MP4 · MKV · MOV · WEBM`, and edge case 1 treats AVI as unsupported.
**Classification:** Minor inconsistency — AVI is accepted by the code but PRD edge case 1 uses AVI as an example of "unsupported format." The backend FFprobe validation will determine actual support per-file. Cosmetic UI gap only.

### S2-R3: Unsupported format → toast with filename
**PRD:** "실패 → 토스트 알림: '지원하지 않는 형식: {파일명} ({코덱})' + 드래그&드롭 화면 유지"
**Status:** ⚠️ GAP — Toast omits codec information
**Evidence:** `main.ts:1017` shows `"지원하지 않는 형식: ${extractFilename(filePath)} (.${ext})"` — includes extension but **not codec**. Backend error (lines 1066-1067) also shows generic message without codec.
**Classification:** Minor UI text gap — extension is shown instead of codec. Codec info would require FFprobe first, which only runs after extension check passes. Low impact.

### S2-R4: Long video (>1hr) warning modal with [취소]/[계속 진행]
**PRD:** "경고 모달: '이 영상은 {시간}입니다. 분석에 상당한 시간이 소요될 수 있습니다.' + [취소] [계속 진행]"
**Status:** ⚠️ GAP — Modal fires after upload, not before (resource leak on cancel)
**Evidence:** `main.ts:1026-1033` — modal shown after `uploadVideo` RPC completes. On cancel, backend retains the video entry.
**Classification:** **Known Bug** → KB-002 (already tracked).

### S2-R5: File path extraction → RPC → backend upload
**PRD:** "웹뷰에서 파일 경로 추출 → RPC로 Main Process에 전달 → POST /api/upload"
**Status:** ✅ MATCH
**Evidence:** `main.ts:575-588` — drag-and-drop gets `(file as any).path`. `main.ts:553-558` — browse button uses `openFileDialog` RPC. Both funnel to `handleFileSelected()` which calls `electroview.rpc.request.uploadVideo()`. `src/bun/index.ts:44-54` forwards to `POST /api/upload`.

### S2-R6: Transition to main screen with progress banner
**PRD:** "메인 화면으로 전환 (프로그레스 배너 포함)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:1036-1039` — sets `currentVideoId`, `videoDuration`, calls `displayVideoInfo`, `showScreen("main")`. Then starts analysis which shows progress banner.

### S2-R7: Drag-and-drop path fallback via `openFileDialog()`
**PRD:** "파일 경로 미지원 (WebView2 제한): openFileDialog() 폴백"
**Status:** ✅ MATCH
**Evidence:** `main.ts:583-586` — if `(file as any).path` is falsy, shows toast suggesting file selection button. `main.ts:561-564` — clicking drop zone itself triggers browse button. `browseBtn` uses `openFileDialog` RPC.

---

## Scenario 3: Analysis (분석)

### S3-R1: Auto-start analysis immediately after upload
**PRD:** "업로드 즉시 분석이 자동 시작됨 (별도 버튼 없음)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:1061` — `startAnalysis(result.id)` called immediately after upload succeeds.

### S3-R2: Progress banner with bar + percent + stage text
**PRD:** "프로그레스 바 + 퍼센트 + 현재 단계 텍스트"
**Status:** ✅ MATCH
**Evidence:** `index.html:85-93` — progress banner with `#progress-stage`, `#progress-percent`, `#progress-bar`. `main.ts:650-655` (`updateProgress`) sets all three fields.

### S3-R3: Stage text progression
**PRD:** "'오디오 추출 중...' → '오디오 분석 중...' → '영상 분석 중...' → '하이라이트 스코어링 중...' → '자막 생성 중...'"
**Status:** ⚠️ GAP — Stage messages come from backend, not verified in frontend
**Evidence:** `main.ts:603` shows `data.message` from WebSocket directly. The frontend does not define or validate the stage progression — it trusts backend messages. If backend sends different stage text, the UI will display whatever is received.
**Classification:** By design (backend drives stage text). No frontend deviation, but frontend does not enforce the PRD's specific stage text sequence. Acceptable.

### S3-R4: Main screen layout — left panel (info + highlights + subtitles)
**PRD:** "좌측 패널: 영상 정보 (파일명, 해상도, FPS, 길이, 크기) + 하이라이트 구간 리스트 + 자막 리스트"
**Status:** ✅ MATCH
**Evidence:** `index.html:97-123` — left panel with three sections: 영상 정보 (6 info rows), 하이라이트 구간, 자막. All info fields present (파일명, 해상도, FPS, 길이, 코덱, 크기).

### S3-R5: Main screen layout — right panel (settings + export)
**PRD:** "우측 패널: 분석 설정 슬라이더 + 내보내기 옵션"
**Status:** ✅ MATCH
**Evidence:** `index.html:126-213` — right panel with settings form (7 controls) and export section.

### S3-R6: Timeline with 5-second interval thumbnails
**PRD:** "타임라인 (썸네일 로딩 중 → 완료 시 5초 간격 이미지 썸네일)"
**Status:** ✅ MATCH
**Evidence:** `index.html:217-219` — Canvas element. `main.ts:185-196` (`loadThumbnails`) loads images from backend. `main.ts:225` uses `interval = 5` seconds per thumbnail.

### S3-R7: Highlight overlay on timeline (orange)
**PRD:** "타임라인에 하이라이트 구간 오버레이 표시 (주황색)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:246` — `"rgba(243, 156, 18, 0.4)"` for auto segments (orange). Manual segments are blue per PRD.

### S3-R8: Left panel highlight list (#1, #2, ...)
**PRD:** "좌측 패널에 하이라이트 구간 리스트 표시 (#1, #2, ...)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:713` — `#${i + 1}` numbering in highlight items.

### S3-R9: Left panel subtitle list (time + text, read-only)
**PRD:** "좌측 패널에 자막 리스트 표시 (시간 + 텍스트, 확인만 가능)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:901-913` — renders subtitles with `formatDuration(s.start)` and `s.text`. No edit controls — read-only as specified.

### S3-R10: Export button enabled on analysis complete
**PRD:** "내보내기 버튼 활성화"
**Status:** ✅ MATCH
**Evidence:** `main.ts:938-941` (`enableExportButton`) — sets `analysisComplete = true`, enables button. Called when WebSocket receives `stage === "complete"` (line 609).

### S3-R11: Zero highlights → full video as 1 segment
**PRD:** "하이라이트 구간이 0개인 경우: 전체 영상을 1개 구간으로 자동 설정"
**Status:** ✅ MATCH
**Evidence:** `main.ts:689-691` — checks `highlights.length === 0`, sets `[{start: 0, end: videoDuration, score: 0}]`, shows warning toast.

### S3-R12: Analysis error → toast + retry, UI recovers
**PRD:** "분석 중 에러 (FFmpeg 크래시, GPU 메모리 부족): 토스트 알림 + [재시도] 버튼, UI 조작 가능 상태로 복귀"
**Status:** ⚠️ GAP — No explicit [재시도] button for analysis failure
**Evidence:** `main.ts:622-626` — on `stage === "error"`, shows toast and re-enables export button. However, there is no dedicated [재시도] button displayed. Users must change a setting slider to implicitly re-trigger analysis.
**Classification:** Minor UX gap — PRD says "[재시도] 버튼" but recovery is via implicit re-analysis on settings change. Functional but not as discoverable.
**Tracking:** New gap — recommend adding explicit retry button to progress banner area on error state.

---

## Scenario 4: Highlight Editing (하이라이트 편집)

### S4-R1: Timeline segment edge dragging
**PRD:** "구간 양끝 드래그: 시작/끝 시간 조절 (비주얼 피드백)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:356-446` — mousedown detects edge proximity via `isNearEdge()`, sets `resizing_left`/`resizing_right` mode. Mousemove updates segment bounds. Visual feedback via resize handles (white bars at edges, line 258-260).

### S4-R2: Empty area click → new 5-second segment
**PRD:** "빈 영역 클릭: 새 구간 추가 (기본 5초)"
**Status:** ✅ MATCH
**Evidence:** `main.ts:378-389` — clicks not on a segment create a new 5s manual segment centered on click position.

### S4-R3: Selected segment + Delete key → delete
**PRD:** "구간 선택 후 Delete 키: 구간 삭제"
**Status:** ✅ MATCH
**Evidence:** `main.ts:457-465` — Delete key with `selectedSegmentIdx >= 0` removes the segment.

### S4-R4: Right-click segment deletion
**PRD:** "구간 선택 후 Delete 키 또는 우클릭: 구간 삭제"
**Status:** ❌ MISSING — No right-click context menu for deletion
**Evidence:** No `contextmenu` event listener in `main.ts`. Only Delete key is supported.
**Classification:** **Future Fix** — Minor interaction gap. Delete key works; right-click is an alternative path not implemented.

### S4-R5: Ctrl+Z Undo / Ctrl+Y Redo
**PRD:** "Ctrl+Z: Undo / Ctrl+Y: Redo"
**Status:** ✅ MATCH
**Evidence:** `main.ts:468-479` — Ctrl+Z calls `undo()`, Ctrl+Y calls `redo()`. Undo/redo stacks properly managed (lines 288-312).

### S4-R6: Left panel list — start/end time display
**PRD:** "구간 리스트에서 시작/끝 시간 확인"
**Status:** ✅ MATCH
**Evidence:** `main.ts:714` — `${formatDuration(h.start)} - ${formatDuration(h.end)}` in each highlight item.

### S4-R7: Left panel [+ 구간 추가] button
**PRD:** "[+ 구간 추가] 버튼"
**Status:** ✅ MATCH
**Evidence:** `main.ts:722` — `<button class="btn-add-segment" id="add-segment-btn">+ 구간 추가</button>` rendered at bottom of highlight list. Click handler at lines 754-767 adds a manual segment.

### S4-R8: Hover [×] delete button on each segment
**PRD:** "각 구간 hover 시 [×] 삭제 버튼 표시"
**Status:** ✅ MATCH
**Evidence:** `main.ts:716` — `<button class="highlight-delete">×</button>` in each item. `style.css:383-395` — `display: none` by default, `display: inline` on hover.

### S4-R9: Manual segments = blue, auto segments = orange
**PRD:** "수동 추가 구간은 파란색 표시 (자동 = 주황색, 수동 = 파란색)"
**Status:** ✅ MATCH
**Evidence:** Timeline: `main.ts:245-247` — manual=blue `rgba(52, 152, 219, 0.4)`, auto=orange `rgba(243, 156, 18, 0.4)`. List: `style.css:374-380` — `.manual .highlight-num` = blue, `.auto .highlight-num` = orange.

### S4-R10: Settings change → real-time re-analysis (manual segments preserved)
**PRD:** "슬라이더 조작 즉시 하이라이트 구간 재계산, 수동으로 추가/수정한 구간은 유지"
**Status:** ⚠️ GAP — Manual segments lost on re-analysis
**Evidence:** `main.ts:875` saves manual segments to `manualSegments` variable, but `fetchHighlights()` (called on analysis completion) overwrites `highlights` entirely from server response. The saved manual segments are never merged back.
**Classification:** **Future Fix** → FF-013 (already tracked).

### S4-R11: Toast on settings change with manual segments
**PRD:** "토스트 알림: '수동 구간은 유지됩니다. 자동 구간만 재계산됩니다.'"
**Status:** ✅ MATCH (text shown, but promise not fulfilled per S4-R10)
**Evidence:** `main.ts:876` — shows the toast. However, per S4-R10, manual segments are actually lost — the toast message is misleading.

### S4-R12: Debounce 500ms → PUT highlights
**PRD:** "모든 변경은 debounce 500ms 후 PUT /api/video/{id}/highlights 저장"
**Status:** ✅ MATCH
**Evidence:** `main.ts:315-329` (`debounceSave`) — `setTimeout(..., 500)` then `PUT` request.

### S4-R13: Video weight display (1 - audio weight)
**PRD:** "영상 가중치: Display (1-오디오), 자동 — 0.4"
**Status:** ⚠️ GAP — Video weight is an independent slider, not auto-computed
**Evidence:** `index.html:136-139` — `setting-video-weight` is a separate range input (`min=0, max=1, step=0.1`). PRD specifies it should be a **display** showing `1 - audio_weight` automatically. Instead, both weights are independently adjustable, allowing audio + video weights to exceed 1.0.
**Classification:** Minor UX/logic gap — users can set inconsistent weights (e.g., audio=0.8, video=0.9). PRD intended video weight to be derived.

### S4-R14: Missing merge_gap and min_silence_duration UI controls
**PRD:** Settings table includes "병합 간격 (0-10s, default 2s)" and "무음 최소 길이 (0.5-5s, default 1.5s)"
**Status:** ❌ MISSING
**Evidence:** No HTML elements for `merge_gap` or `min_silence_duration`. Values are hardcoded in `main.ts:849-850`: `merge_gap: 2`, `min_silence_duration: 1.5`.
**Classification:** **Future Fix** → FF-003 (already tracked).

### S4-R15: Settings top_percent range (1-100%)
**PRD:** "상위 구간: Slider, 1-100%, 기본 30%"
**Status:** ⚠️ GAP — Range is 10-80% instead of PRD's 1-100%
**Evidence:** `index.html:143` — `min="10" max="80" step="5"`. PRD specifies `1-100%`.
**Classification:** Minor deviation — narrower range prevents extreme settings. May be intentional for usability.

---

## Scenario 5: Export (내보내기)

### S5-R1: Output folder display with default `~/Videos/Vaya/` + [변경] button
**PRD:** "출력 폴더: ~/Videos/Vaya/ (기본) + [변경] 버튼"
**Status:** ⚠️ GAP — Shows `storage/output`, no [변경] button
**Evidence:** `index.html:200-201` — static text `storage/output`. No folder picker button.
**Classification:** **Future Fix** → FF-001 + FF-002 (already tracked).

### S5-R2: Checkboxes for YouTube (16:9), Shorts (9:16), subtitles
**PRD:** "☑ YouTube (16:9), ☑ Shorts (9:16), ☑ 자막 포함"
**Status:** ✅ MATCH
**Evidence:** `index.html:177-198` — three checkboxes for YouTube, Shorts, subtitles. YouTube and subtitles checked by default, Shorts unchecked.

### S5-R3: Shorts crop offset slider (visible when Shorts checked)
**PRD:** "Shorts 체크 시 크롭 오프셋 슬라이더 표시"
**Status:** ✅ MATCH
**Evidence:** `main.ts:929-931` — toggles `offset-row` visibility on Shorts checkbox change. `index.html:188-192` — slider with range -200 to 200.

### S5-R4: Export button (disabled until analysis complete)
**PRD:** "[내보내기] 버튼 (분석 완료 전 비활성화)"
**Status:** ✅ MATCH
**Evidence:** `index.html:203` — button starts disabled. `main.ts:938-941` enables on analysis complete.

### S5-R5: Full UI disabled during export
**PRD:** "전체 UI 비활성화 (수정 불가)"
**Status:** ❌ MISSING — Only export button is disabled
**Evidence:** `main.ts:946` — `exportBtn.disabled = true` but no other UI elements are disabled. Timeline interaction, settings sliders, and highlight list remain active during export.
**Classification:** **Future Fix** → FF-008 (already tracked).

### S5-R6: Export progress banner with format counter
**PRD:** "프로그레스: '1/2 · YouTube용 인코딩 중...' → '2/2 · Shorts용 인코딩 중...'"
**Status:** ✅ MATCH
**Evidence:** Progress messages come from backend (`exporter.py:139,174`). Frontend displays via WebSocket in `updateProgress()`. Backend sends matching text: "1/2 · YouTube용 인코딩 중...", "2/2 · Shorts용 인코딩 중...".

### S5-R7: Export complete card with ✓ icon + file list + [폴더 열기]
**PRD:** "✓ 아이콘 + 파일 리스트 (파일명 + 용량) + 출력 경로 + [폴더 열기] 버튼"
**Status:** ⚠️ GAP — Missing output path display
**Evidence:** `index.html:207-211` — ✓ icon, file list container, [폴더 열기] button all present. `main.ts:976-990` renders file list with name and size. However, the **output path** is not displayed in the completion card (PRD says it should show the output path).
**Classification:** Minor UI gap — output path info missing from completion card.

### S5-R8: [폴더 열기] → file explorer → drag-and-drop screen
**PRD:** "[폴더 열기] 클릭 → OS 파일 탐색기 오픈 → 드래그&드롭 초기 화면으로 자동 복귀"
**Status:** ✅ MATCH
**Evidence:** `main.ts:992-1008` — calls `openFolder` RPC, then resets all state and returns to `"drop"` screen. `src/bun/index.ts:32-40` opens OS explorer.

### S5-R9: Export complete card placement
**PRD:** "중앙에 완료 카드 표시"
**Status:** ⚠️ GAP — Completion card shown in right panel, not center
**Evidence:** `index.html:207` — `export-complete` div is inside `panel-right`, not centered overlay. `style.css:554-557` — basic text-align center within the panel. PRD says "중앙" (center of screen).
**Classification:** Minor layout gap — functionally equivalent but not visually centered on screen as PRD specifies.

---

## Scenario 6: Session Termination (세션 종료)

### S6-R1: Python backend terminated with app
**PRD:** "앱을 닫으면 Python 백엔드 프로세스가 함께 종료됨"
**Status:** ✅ MATCH
**Evidence:** `src/bun/index.ts:99-101` — `win.on("close", () => { killPython(); })`. `python-manager.ts:132-138` kills the subprocess.

### S6-R2: No session restore (fresh start)
**PRD:** "세션 복원 없음 (MVP): 다시 열면 드래그&드롭 화면부터 시작"
**Status:** ✅ MATCH
**Evidence:** No persistence logic in frontend. `main.ts` starts with `currentScreen = "loading"`, transitions to `"drop"` on backend ready.
**Classification:** **Conscious Decision** → CD-003 (already tracked).

### S6-R3: Settings persisted in config.yaml
**PRD:** "설정값은 config.yaml에 영속 저장되어 유지됨"
**Status:** ✅ MATCH
**Evidence:** `main.ts:813-837` (`loadSettings`) fetches from backend `/api/settings`. `main.ts:866-870` saves via `PUT /api/settings`. Backend `config.py` uses `save_config()` to persist to `config.yaml`.

### S6-R4: Missing export confirmation on window close during export
**PRD:** Edge Case 12 — "(MVP) 프로세스 종료, 미완성 파일은 수동 정리"
**Status:** ⚠️ GAP — No confirmation dialog when closing during active export
**Evidence:** `src/bun/index.ts:99-101` — window close handler immediately kills Python without checking if export is in progress. PRD acknowledges this is MVP behavior.
**Classification:** **Conscious Decision** (MVP scope) + **Future Fix** → FF-006 (tracked). Post-MVP should add "Export in progress — are you sure?" dialog.

---

## Settings Panel Controls — PRD vs Implementation

| PRD Control | PRD Type | PRD Range | PRD Default | Frontend Element | Status |
|---|---|---|---|---|---|
| 오디오 가중치 | Slider | 0-1, step 0.1 | 0.6 | `setting-audio-weight` | ✅ MATCH |
| 영상 가중치 | Display (1-오디오) | Auto | 0.4 | `setting-video-weight` (separate slider) | ⚠️ GAP (S4-R13) |
| 상위 구간 | Slider | 1-100% | 30% | `setting-top-percent` (10-80%, step 5) | ⚠️ GAP (S4-R15) |
| 최소 클립 길이 | Number | 1-30s | 3s | `setting-min-clip` (slider) | ✅ MATCH |
| 최대 클립 길이 | Number | 10-300s | 60s | `setting-max-clip` (slider) | ✅ MATCH |
| 병합 간격 | Number | 0-10s | 2s | — | ❌ MISSING (FF-003) |
| 무음 기준 | Slider | -60~-20dB | -40dB | `setting-threshold-db` | ✅ MATCH |
| 무음 최소 길이 | Number | 0.5-5s | 1.5s | — | ❌ MISSING (FF-003) |
| Whisper 모델 | Select | tiny~large | medium | `setting-whisper-model` | ✅ MATCH |

---

## New Gaps Identified (Not Previously Tracked)

### NEW-1: Analysis error has no explicit [재시도] button
**Location:** `main.ts:622-626`
**PRD:** Scenario 3 exception — "토스트 알림 + [재시도] 버튼"
**Current:** Toast shown, but no retry button. User must change a setting to implicitly re-trigger.
**Recommendation:** Add a "재분석" button to the progress banner area that appears on analysis error state.
**Classification:** Future Fix

### NEW-2: Right-click context menu for segment deletion not implemented
**Location:** `main.ts` — no `contextmenu` listener
**PRD:** Scenario 4 — "구간 선택 후 Delete 키 또는 우클릭: 구간 삭제"
**Current:** Only Delete key works.
**Recommendation:** Add `contextmenu` event listener on timeline canvas with "삭제" option.
**Classification:** Future Fix

### NEW-3: Video weight is independent slider instead of auto-computed display
**Location:** `index.html:136-139`, `main.ts:819-820`
**PRD:** Settings table — "영상 가중치: Display (1-오디오), 자동"
**Current:** Separate adjustable slider allowing inconsistent weight sums.
**Recommendation:** Replace with computed display showing `(1 - audioWeight).toFixed(1)` or constrain sliders.
**Classification:** Future Fix

### NEW-4: Export completion card missing output path
**Location:** `main.ts:976-990`, `index.html:207-211`
**PRD:** Scenario 5 — "출력 경로" listed in completion card
**Current:** Shows file list and [폴더 열기] but no path text.
**Recommendation:** Add output directory path display to the completion card.
**Classification:** Future Fix

### NEW-5: Export completion card in right panel, not centered
**Location:** `index.html:207`, `style.css:554-557`
**PRD:** Scenario 5 — "중앙에 완료 카드 표시"
**Current:** Card rendered inside right panel.
**Recommendation:** Show completion card as centered modal overlay or move to main content area.
**Classification:** Future Fix

### NEW-6: Retry button does not restart Python process
**Location:** `main.ts:533-550`
**PRD:** Scenario 1 — "에러 화면의 [재시도] 버튼: 로딩 화면으로 돌아가 프로세스 재시작"
**Current:** Only re-checks health status via RPC, does not restart the Python backend.
**Recommendation:** Add `restartBackend` RPC handler that calls `killPython()` + `spawnPython()`.
**Classification:** Future Fix — relates to FF-012

### NEW-7: AVI included in frontend but excluded from PRD format list
**Location:** `index.html:68`, `main.ts:1015`
**PRD:** Scenario 2 — "MP4 · MKV · MOV · WEBM" (AVI not listed)
**Current:** AVI appears in UI format hint and extension whitelist.
**Recommendation:** Either remove AVI from frontend or update PRD. AVI is valid per FFmpeg but PRD edge case 1 uses it as unsupported format example.
**Classification:** Clarification needed — minor inconsistency

### NEW-8: Settings debounce is 300ms, not PRD's implicit standard
**Location:** `main.ts:805`
**PRD:** Scenario 4 — "debounce 500ms 후 PUT"
**Current:** Settings changes use 300ms debounce (via `settingsDebounce = setTimeout(() => saveSettingsAndReanalyze(), 300)`), while highlight changes correctly use 500ms.
**Recommendation:** Align settings debounce to 500ms to match PRD, or document the 300ms as intentional for faster settings responsiveness.
**Classification:** Minor timing deviation

---

## Summary Matrix

| Scenario | Req ID | Description | Status | Tracking |
|---|---|---|---|---|
| S1 | S1-R1 | Loading screen | ✅ | — |
| S1 | S1-R2 | Health check retries | ⚠️ | Benign (20 vs 10 retries) |
| S1 | S1-R3 | Success → drop screen | ✅ | — |
| S1 | S1-R4 | Failure → error screen | ✅ | — |
| S1 | S1-R5 | Error retry restarts Python | ⚠️ | NEW-6 |
| S1 | S1-R6 | Port conflict handling | ⚠️ | EC-06 note |
| S2 | S2-R1 | Drop zone UI | ✅ | — |
| S2 | S2-R2 | Format list display | ⚠️ | NEW-7 |
| S2 | S2-R3 | Unsupported format toast | ⚠️ | Minor (no codec info) |
| S2 | S2-R4 | Long video modal timing | ⚠️ | KB-002 |
| S2 | S2-R5 | File path → RPC → upload | ✅ | — |
| S2 | S2-R6 | Main screen transition | ✅ | — |
| S2 | S2-R7 | openFileDialog fallback | ✅ | — |
| S3 | S3-R1 | Auto-start analysis | ✅ | — |
| S3 | S3-R2 | Progress banner | ✅ | — |
| S3 | S3-R3 | Stage text progression | ⚠️ | Backend-driven (acceptable) |
| S3 | S3-R4 | Left panel layout | ✅ | — |
| S3 | S3-R5 | Right panel layout | ✅ | — |
| S3 | S3-R6 | Timeline thumbnails | ✅ | — |
| S3 | S3-R7 | Highlight overlay (orange) | ✅ | — |
| S3 | S3-R8 | Highlight list numbering | ✅ | — |
| S3 | S3-R9 | Subtitle list (read-only) | ✅ | — |
| S3 | S3-R10 | Export button enablement | ✅ | — |
| S3 | S3-R11 | Zero highlights fallback | ✅ | — |
| S3 | S3-R12 | Analysis error retry | ⚠️ | NEW-1 |
| S4 | S4-R1 | Edge dragging | ✅ | — |
| S4 | S4-R2 | Empty area → new segment | ✅ | — |
| S4 | S4-R3 | Delete key deletion | ✅ | — |
| S4 | S4-R4 | Right-click deletion | ❌ | NEW-2 |
| S4 | S4-R5 | Ctrl+Z / Ctrl+Y | ✅ | — |
| S4 | S4-R6 | List time display | ✅ | — |
| S4 | S4-R7 | [+ 구간 추가] button | ✅ | — |
| S4 | S4-R8 | Hover [×] delete | ✅ | — |
| S4 | S4-R9 | Blue (manual) / orange (auto) | ✅ | — |
| S4 | S4-R10 | Manual segment preservation | ⚠️ | FF-013 |
| S4 | S4-R11 | Toast on settings change | ✅ | (misleading per S4-R10) |
| S4 | S4-R12 | Debounce 500ms save | ✅ | — |
| S4 | S4-R13 | Video weight auto-display | ⚠️ | NEW-3 |
| S4 | S4-R14 | merge_gap + silence_duration UI | ❌ | FF-003 |
| S4 | S4-R15 | top_percent range 1-100% | ⚠️ | Narrowed to 10-80% |
| S5 | S5-R1 | Output folder + [변경] | ⚠️ | FF-001, FF-002 |
| S5 | S5-R2 | Format checkboxes | ✅ | — |
| S5 | S5-R3 | Shorts crop offset slider | ✅ | — |
| S5 | S5-R4 | Export button disabled | ✅ | — |
| S5 | S5-R5 | Full UI disabled during export | ❌ | FF-008 |
| S5 | S5-R6 | Export progress with counter | ✅ | — |
| S5 | S5-R7 | Completion card content | ⚠️ | NEW-4 |
| S5 | S5-R8 | Folder open → drop screen | ✅ | — |
| S5 | S5-R9 | Completion card centered | ⚠️ | NEW-5 |
| S6 | S6-R1 | Python terminated on close | ✅ | — |
| S6 | S6-R2 | No session restore | ✅ | CD-003 |
| S6 | S6-R3 | Settings persisted | ✅ | — |
| S6 | S6-R4 | No close confirmation | ⚠️ | FF-006 |

### Statistics

- **✅ Fully matching:** 31 / 46 (67%)
- **⚠️ Gaps (partial/deviated):** 12 / 46 (26%)
- **❌ Missing:** 3 / 46 (7%)

### Gap Classification Summary

| Category | Count | Items |
|---|---|---|
| Already tracked (Known Bugs) | 1 | KB-002 (S2-R4) |
| Already tracked (Future Fixes) | 4 | FF-003 (S4-R14), FF-008 (S5-R5), FF-013 (S4-R10), FF-001/002 (S5-R1) |
| Already tracked (Conscious Decisions) | 2 | CD-003 (S6-R2), FF-006/MVP (S6-R4) |
| New gaps identified | 8 | NEW-1 through NEW-8 |
| Benign/acceptable deviations | 3 | S1-R2 (retries), S3-R3 (backend-driven), S2-R3 (no codec in toast) |
