# Conscious Decisions — PRD vs Implementation

> Classification: **Conscious Decisions**
> Date: 2026-03-16
> Scope: Vaya MVP (11 user stories, US-001–US-011)

These are intentional deviations or design choices made during MVP implementation that differ from production best practices. Each was deliberately chosen to reduce complexity, and should be revisited in post-MVP phases.

---

## CD-001: CORS Wildcard (`allow_origins=["*"]`)

**PRD Reference**: PRD §Phase 6 — "CORS 미들웨어 확인" (listed as a polish task, no specific origin restrictions defined)

**Implementation** (`backend/main.py:12-18`):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Decision Rationale**:
Vaya is a **desktop-only** application where the FastAPI backend runs on `127.0.0.1:8765` as a child process of Electrobun. The only client is the Electrobun webview running on the same machine. In this architecture:

- The backend is **not exposed to the network** — it binds to `127.0.0.1` (localhost only)
- The Electrobun webview's origin varies depending on the webview implementation (could be `file://`, a custom scheme, or a localhost port), making a fixed origin list fragile
- There is **no multi-user or multi-tenant concern** — the app serves a single local user
- Restricting CORS origins would add maintenance burden with no security benefit in this deployment model

**Risk Assessment**: **Low**. The backend is not network-accessible. If the app were ever converted to a web service, this would need to be changed to explicit origin allowlisting.

**When to Revisit**: If Vaya ever exposes the backend over a network interface (e.g., remote editing, cloud deployment), CORS origins must be restricted to specific allowed domains.

---

## CD-002: No NFR (Non-Functional Requirements) Definitions Until Post-MVP

**PRD Reference**: PRD §Definition of Done lists performance targets (e.g., "30분 영상 분석 2분 이내", "5분 하이라이트 인코딩 1분 이내") but does not define formal NFRs for:
- Memory usage limits
- Startup time SLA
- Concurrent operation limits
- Disk space management
- Error rate thresholds
- Accessibility standards

**Decision Rationale**:
The MVP focuses on **functional correctness** across 12 normal scenarios and 14 edge cases. Formal NFR definitions were deferred because:

1. **Solo developer context** — NFR enforcement (monitoring, benchmarks, CI gates) requires infrastructure investment disproportionate to MVP scope
2. **Hardware variability** — Performance targets depend heavily on user hardware (GPU model, CPU cores, RAM). Defining hard SLAs before real-world testing would produce arbitrary numbers
3. **Iterative discovery** — Actual performance characteristics and bottlenecks are better identified through user testing than upfront specification
4. **PRD performance targets exist informally** — The Definition of Done section provides soft targets (analysis < 2min for 30min video, encoding < 1min for 5min highlights) that serve as guidelines without formal enforcement

**What This Means in Practice**:
| Area | Current State | Post-MVP Target |
|---|---|---|
| Memory | No limits; Python process grows as needed | Define max RSS, implement cleanup |
| Startup | Health check timeout = 5s (10 polls × 500ms) | Formal SLA + cold start benchmarks |
| Disk | No temp file cleanup strategy | Auto-cleanup of `storage/` on session end |
| Concurrency | Single-video assumption | Define max concurrent videos |
| Error rates | No tracking | Structured logging + error rate monitoring |

**Risk Assessment**: **Medium**. Without NFRs, performance regressions can creep in unnoticed. The informal PRD targets partially mitigate this.

**When to Revisit**: Post-MVP phase, once real-world usage patterns and hardware profiles are established. Priority: define memory limits and disk cleanup first (highest user-impact).

---

## CD-003: Stateless Sessions (`_videos` In-Memory Dict, No Persistence)

**PRD Reference**: PRD §시나리오 6 (세션 종료) — "**세션 복원 없음** (MVP): 다시 열면 드래그&드롭 화면부터 시작"

**Implementation** (`backend/routers/upload.py:12-13`):
```python
# In-memory video store (MVP — no database)
_videos: dict[str, dict] = {}
```

All video state (metadata, highlights, subtitles path, thumbnails) is stored in a plain Python dictionary. When the app closes, the Electrobun main process terminates the Python child process, and all state is lost.

**Decision Rationale**:
1. **PRD explicitly specifies no session restoration** — This is not a bug or oversight; the PRD Phase 2 decision table records "세션 복원 | 없음 (MVP) | 복잡도 절감" (Session restoration: None for MVP, to reduce complexity)
2. **Single-session workflow** — The user flow is linear: upload → analyze → edit → export → done. There is no use case for resuming a half-edited video after app restart in the MVP
3. **No database overhead** — Avoiding SQLite/filesystem persistence eliminates schema management, migration tooling, and data corruption edge cases
4. **Config is persisted separately** — User preferences (analysis weights, silence thresholds, export settings) are saved to `config.yaml` via `AppConfig` Pydantic model, so settings survive across sessions even though video state does not
5. **Test simplicity** — The `autouse` fixture in `conftest.py` clears `_videos` between tests, providing perfect isolation without database teardown

**What Is Lost on App Close**:
| Data | Persistence | Impact |
|---|---|---|
| Video metadata (resolution, FPS, etc.) | Lost — re-extracted on next upload | Low — FFprobe extraction is fast |
| Analysis results (highlights, scores) | Lost — must re-analyze | Medium — analysis takes 1-2 minutes |
| Whisper subtitles | Lost — must re-generate | Medium — STT takes 1-2 minutes |
| Thumbnails on disk | Persist in `storage/thumbnails/` but orphaned | Low — disk space waste |
| User highlight edits (manual segments) | Lost | High — user effort is discarded |
| Export output files | Persist in output folder | None — already saved to disk |
| User settings (config.yaml) | Persisted | None — survives app restart |

**Risk Assessment**: **Low for MVP**. The PRD explicitly chose this trade-off. The highest-impact loss is manual highlight edits, but the MVP workflow assumes users complete the full cycle in one session.

**When to Revisit**: Post-MVP, when implementing:
- Session save/restore (SQLite or JSON file)
- Multi-video management
- "Resume where you left off" feature
- Crash recovery (auto-save analysis results)

---

## Summary

| ID | Decision | Rationale | Risk | Revisit Trigger |
|---|---|---|---|---|
| CD-001 | CORS `allow_origins=["*"]` | Desktop-only, localhost binding, no network exposure | Low | Network/cloud deployment |
| CD-002 | No formal NFR definitions | Solo dev MVP, hardware variability, iterative discovery | Medium | Post-MVP phase start |
| CD-003 | Stateless sessions (in-memory dict) | PRD-specified, single-session workflow, no DB overhead | Low | Session restore feature |
