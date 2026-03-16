# Vaya MVP — Consolidated Gap Tracking Document

**Date:** 2026-03-16
**Scope:** All gaps between PRD (`docs/prd/20260309-vaya-mvp.md`) and implementation (11 user stories, US-001–US-011)
**Purpose:** Single auditable source of truth for every identified PRD-to-implementation gap

---

## How to Use This Document

1. **Every gap has a unique ID** (e.g., KB-001, FF-003) — use these for issue tracking and cross-references
2. **Categories are mutually exclusive** — each gap belongs to exactly one primary category
3. **Cross-references** link related items across categories (e.g., a future fix may relate to a test gap)
4. **Source documents** contain full detail; this document provides the classification index and summary

### Category Definitions

| Category | Prefix | Meaning | Action Required |
|----------|--------|---------|-----------------|
| **Known Bug** | KB- | Implemented but defective; deviates from PRD | Fix before production release |
| **Future Fix** | FF- | Not a bug, but missing or incomplete vs. PRD | Implement in post-MVP or near-term patch |
| **Test Gap** | TG- | Implementation exists but lacks test coverage | Add tests to prevent regressions |
| **Conscious Decision** | CD- | Intentional deviation with documented rationale | Revisit at specified trigger |
| **Architecture Decision** | AD- | Foundational choice shaping the system | Change only with significant rework |

### Source Documents

| Document | Path | Items |
|----------|------|-------|
| Known Bugs | `docs/design/known-bugs.md` | KB-001, KB-002 |
| Future Fixes | `docs/design/future-fixes.md` | FF-001 through FF-014 |
| Test Gaps | `docs/design/test-gaps.md` | TG-001, TG-002 |
| Conscious Decisions | `docs/design/conscious-decisions.md` | CD-001, CD-002, CD-003 |
| Architecture Decisions | `docs/design/architecture-decisions.md` | AD-001, AD-002, AD-003, AD-004 |
| Edge Case Classification | `docs/design/edge-cases.md` | EC-01 through EC-14 |

---

## Master Gap Registry

### Known Bugs (2 items)

| ID | Summary | Severity | PRD Section | Code Location | Fix Complexity |
|----|---------|----------|-------------|---------------|----------------|
| KB-001 | `analyze.py` missing `_exporting` cross-check — analysis can start during active export, causing data race | High | §Phase 5A "per-video lock (분석/내보내기 동시 불가)" | `backend/routers/analyze.py:30-31` | Low (3-line fix) |
| KB-002 | Long video warning modal fires after upload completes — resource leak on cancel (orphaned `_videos` entry + thumbnails) | Medium | §Scenario 2 Step 5, EC-2, EC-10 | `src/views/main/main.ts:1022-1032` | Medium (API refactor or cleanup endpoint) |

### Future Fixes (14 items)

| ID | Type | Summary | PRD Section | Code Location | Priority |
|----|------|---------|-------------|---------------|----------|
| FF-001 | Config gap | Output folder defaults to `storage/output` instead of `~/Videos/Vaya/` | §Scenario 5 output folder | `backend/services/exporter.py:12` | Medium |
| FF-002 | Missing feature | No output folder [변경] button functionality | §Scenario 5 [변경] 버튼 | Frontend export panel | Medium |
| FF-003 | Missing UI | `merge_gap` and `min_silence_duration` sliders missing from settings panel | §Scenario 4 settings table | `src/views/main/main.ts` (hardcoded values) | Medium |
| FF-004 | Missing feature | Whisper model download progress not shown | EC-11 | `backend/services/subtitle_generator.py` | Low (mitigated by AD-003 bundling) |
| FF-005 | Missing check | No disk space check before export | §Scenario 5 exception "디스크 공간 부족" | `backend/services/exporter.py` | Medium |
| FF-006 | Missing cleanup | Incomplete file cleanup on failed/interrupted export | EC-12 | `backend/services/exporter.py` | Low (MVP: manual cleanup per PRD) |
| FF-007 | Feature gap | English language support not implemented | Constraint: Korean default + English planned | `main.ts`, `subtitle_generator.py` (hardcoded `ko`) | Low (post-MVP) |
| FF-008 | Incomplete UI | Export does not disable full UI during encoding | §Scenario 5 "전체 UI 비활성화" | `src/views/main/main.ts` | High |
| FF-009 | Naming mismatch | File duplicate naming uses `_1` instead of `(2)` | §Scenario 5 file naming rule | `backend/services/exporter.py` `_unique_path()` | Low |
| FF-010 | Validation gap | Export `crop_offset` not validated against frame width | EC-14 | `backend/services/exporter.py`, `backend/models.py` | Medium |
| FF-011 | Build gap | Production PyInstaller exe branch not implemented in python-manager | Constraint: NSIS/Inno Setup installer | `src/bun/python-manager.ts` | High (blocks distribution) |
| FF-012 | Missing feature | No auto-reconnect to backend on HTTP connection loss | §Phase 6 "백엔드 연결 끊김 + 자동 재연결" | Frontend HTTP layer | Medium |
| FF-013 | Logic bug | Manual segments lost on re-analysis despite toast promising preservation | §Scenario 4 "수동 구간 유지" | `src/views/main/main.ts` `saveSettingsAndReanalyze()` | High |
| FF-014 | Feature gap | Silence removal within highlights not applied during export | §Scenario 5 "무음 제거: 하이라이트 구간 내부" | `backend/services/exporter.py` `_build_filter_complex()` | High |

### Test Gaps (2 items)

| ID | Summary | Priority | What's Untested | Recommended Tests |
|----|---------|----------|-----------------|-------------------|
| TG-001 | `config.py` has no unit tests — config persistence layer completely unverified | Medium | `load_config()`, `save_config()`, `AppConfig` defaults, corrupt YAML handling | 7 test cases (see source doc) |
| TG-002 | CUDA/CPU fallback paths untested — CPU fallback is the guaranteed deployment path | High | Whisper CPU fallback (`fp16=False`), NVENC→libx264 fallback, GPU memory error handling | 6 test cases (see source doc) |

### Conscious Decisions (3 items)

| ID | Decision | Rationale | Risk | Revisit Trigger |
|----|----------|-----------|------|-----------------|
| CD-001 | CORS `allow_origins=["*"]` | Desktop-only app, backend binds `127.0.0.1`, webview origin varies | Low | Network/cloud deployment |
| CD-002 | No formal NFR definitions until post-MVP | Solo dev MVP, hardware variability, soft PRD targets exist | Medium | Post-MVP phase start |
| CD-003 | Stateless sessions (`_videos` in-memory dict, no persistence) | PRD explicitly specifies no session restore for MVP | Low | Session restore feature planned |

### Architecture Decisions (4 items)

| ID | Decision | Scope | Reversibility | Priority to Change |
|----|----------|-------|---------------|-------------------|
| AD-001 | Windows-only target platform | Platform | High effort | Post-MVP (if ever) |
| AD-002 | CUDA included in bundle with CPU fallback guaranteed | Runtime | Low effort (stable) | Keep as-is |
| AD-003 | NSIS/Inno Setup installer with Whisper medium model bundled (5-7GB) | Distribution | Medium effort | Needs implementation (FF-011) |
| AD-004 | Relative storage paths (project-local) instead of `%APPDATA%/Vaya/` | File system | Medium effort | Should migrate for production |

---

## PRD Scenario Coverage Matrix

Cross-references every PRD normal scenario (12) and edge case (14) against identified gaps.

### Normal Scenarios (12)

| # | Scenario | Gaps Identified |
|---|----------|-----------------|
| 1 | App launch → loading → drag-and-drop | — (fully implemented) |
| 2 | MP4 file upload via file picker | — (fully implemented) |
| 3 | Auto-analysis start after upload | — (fully implemented) |
| 4 | Analysis complete → highlight display | — (fully implemented) |
| 5 | Timeline segment edge drag | — (fully implemented) |
| 6 | Empty area click → add segment | — (fully implemented) |
| 7 | Delete segment via Delete key | — (fully implemented) |
| 8 | Ctrl+Z undo | — (fully implemented) |
| 9 | Settings slider → re-analysis | FF-003 (missing `merge_gap`/`min_silence_duration` UI), FF-013 (manual segments lost) |
| 10 | YouTube + Shorts + subtitles export | FF-001 (wrong output dir), FF-002 (no folder change), FF-008 (incomplete UI disable), FF-014 (silence removal missing) |
| 11 | Export complete → completion card | — (fully implemented) |
| 12 | Open folder → return to initial screen | — (fully implemented) |

### Edge Cases (14)

| EC# | Edge Case | Status | Gap IDs |
|-----|-----------|--------|---------|
| 1 | Unsupported format upload | ✅ IMPLEMENTED | — |
| 2 | 3-hour video upload warning | ⚠️ PARTIAL | KB-002 |
| 3 | Zero highlights → full video | ✅ IMPLEMENTED | — |
| 4 | Analysis backend crash → toast + retry | ✅ IMPLEMENTED | — |
| 5 | Backend connection failure at startup | ✅ IMPLEMENTED | — |
| 6 | Port 8765 already in use | ✅ IMPLEMENTED | — |
| 7 | NVENC fallback to libx264 | ✅ IMPLEMENTED | TG-002 |
| 8 | Duplicate filename numbering | ⚠️ PARTIAL | FF-009 |
| 9 | Manual segments on settings change | ⚠️ PARTIAL | FF-013 |
| 10 | 10GB+ large file handling | ✅ IMPLEMENTED | — |
| 11 | Whisper model first download progress | ❌ NOT IMPLEMENTED | FF-004, AD-003 |
| 12 | Export + app close | ✅ MVP-SCOPED | FF-006, CD-003 |
| 13 | Korean/space paths | ✅ IMPLEMENTED | — |
| 14 | Shorts crop offset | ✅ IMPLEMENTED | FF-010 |

**Edge Case Summary:**
- ✅ Fully implemented: 9 / 14 (64%)
- ⚠️ Partially implemented: 3 / 14 (21%)
- ❌ Not implemented: 1 / 14 (7%)
- ✅ MVP-scoped (matches PRD intent): 1 / 14 (7%)

---

## Cross-Reference Matrix

Shows how gaps relate to each other across categories.

| Gap ID | Related Items | Relationship |
|--------|---------------|-------------|
| KB-001 | FF-008 | Both affect export-time safety; FF-008 (UI disable) would prevent user-triggered KB-001 |
| KB-002 | CD-003 | Stateless sessions (CD-003) bounds KB-002's leak impact to single session |
| FF-004 | AD-003 | AD-003 (model bundled) mitigates FF-004 in production; FF-004 only affects dev mode |
| FF-006 | CD-003 | Stateless sessions mean no auto-recovery; FF-006 adds startup cleanup |
| FF-008 | KB-001 | Disabling full UI during export (FF-008) would prevent triggering KB-001 |
| FF-011 | AD-003 | AD-003 requires FF-011 for implementation; FF-011 blocks production distribution |
| FF-013 | TG-001 | Config persistence (TG-001) affects re-analysis parameters that trigger FF-013 |
| TG-002 | AD-002 | TG-002 tests the guarantee that AD-002 promises |
| AD-004 | FF-001 | AD-004 (relative paths) is the root cause of FF-001 (wrong output folder) |

---

## Priority Summary

### Critical Path (blocks production release)

| ID | Item | Why Critical |
|----|------|-------------|
| KB-001 | Missing `_exporting` cross-check | Data race can produce corrupt export output |
| FF-008 | Export UI not fully disabled | Users can trigger inconsistent state during export |
| FF-011 | No PyInstaller exe branch | Cannot distribute production installer |
| FF-013 | Manual segments lost on re-analysis | Core editing promise broken |
| FF-014 | Silence removal not applied in export | Key export feature missing |
| TG-002 | CPU fallback untested | Guaranteed deployment path has no test coverage |

### Should Fix (quality / PRD compliance)

| ID | Item |
|----|------|
| KB-002 | Long video warning resource leak |
| FF-001 | Output folder default path |
| FF-002 | Output folder change button |
| FF-003 | Missing settings sliders |
| FF-005 | No disk space check |
| FF-010 | Crop offset validation |
| FF-012 | No HTTP auto-reconnect |
| TG-001 | Config unit tests missing |

### Low Priority (cosmetic / post-MVP)

| ID | Item |
|----|------|
| FF-004 | Whisper download progress (mitigated by bundling) |
| FF-006 | Partial file cleanup (MVP: manual per PRD) |
| FF-007 | English language support |
| FF-009 | Filename numbering format |

### Stable (no action needed)

| ID | Item |
|----|------|
| CD-001 | CORS wildcard (appropriate for desktop) |
| CD-002 | No NFRs (appropriate for MVP) |
| CD-003 | Stateless sessions (PRD-specified) |
| AD-001 | Windows-only (by design) |
| AD-002 | CUDA + CPU fallback (architecture stable) |
| AD-003 | NSIS installer design (pending FF-011 implementation) |
| AD-004 | Relative storage paths (acceptable for MVP) |

---

## Statistics

| Category | Count | High/Critical | Medium | Low |
|----------|-------|---------------|--------|-----|
| Known Bugs | 2 | 1 | 1 | 0 |
| Future Fixes | 14 | 4 | 5 | 5 |
| Test Gaps | 2 | 1 | 1 | 0 |
| Conscious Decisions | 3 | 0 | 1 | 2 |
| Architecture Decisions | 4 | 0 | 2 | 2 |
| **Total** | **25** | **6** | **10** | **9** |

---

## Audit Checklist

To verify this document remains current:

- [ ] Every PRD normal scenario (12) has been checked — see Scenario Coverage Matrix
- [ ] Every PRD edge case (14) has been classified — see Edge Cases section
- [ ] Every gap has a unique ID that matches its source document
- [ ] Cross-references between related gaps are bidirectional
- [ ] Priority classification reflects current project phase (MVP complete, pre-production)
- [ ] No gap exists in a source document that is missing from this registry
