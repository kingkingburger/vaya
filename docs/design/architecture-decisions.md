# Vaya MVP — Architecture Decisions

**Date:** 2026-03-16
**Status:** Documented from PRD and implementation analysis
**Scope:** Foundational architecture choices that shape the system design and cannot be changed without significant rework

---

## AD-001: Windows-Only Target Platform

**Decision:** Vaya targets Windows exclusively. No macOS or Linux support.

**PRD Reference:** Requirements doc Section 7 — "OS | Windows"; PRD Phase 1 decision table — "Electrobun (Tauri v2 폴백)"

**Evidence in Codebase:**
- `docs/requiredment.md` line 130: `OS | Windows`
- `electrobun.config.ts` line 24: `win: { bundleCEF: false, defaultRenderer: "native" }` — Windows-specific build config with no macOS/Linux equivalents
- `src/bun/python-manager.ts` line 36-37: Windows-specific paths using `USERPROFILE` and `LOCALAPPDATA` environment variables
- `src/bun/python-manager.ts` line 94: Fallback venv path uses `Scripts/python.exe` (Windows convention, not `bin/python` for Unix)
- `bun.lock`: Contains `cross-spawn-windows-exe` dependency

**Rationale:**
- Target user is a solo Korean game YouTuber on a Windows gaming PC with NVIDIA GPU
- CUDA/NVENC GPU acceleration requires NVIDIA hardware (overwhelmingly Windows in gaming)
- Electrobun's Windows support aligns with the single-platform strategy
- Reduces testing matrix and CI complexity for a solo developer
- No demand signal for macOS/Linux from the target user base

**Implications:**
- All path handling uses Windows conventions (`\` separators, drive letters, `pathlib.Path` for safety)
- `uv` executable discovery checks Windows-specific locations (`%LOCALAPPDATA%\uv\uv.exe`)
- Installer tooling (NSIS/Inno Setup) is Windows-only
- No need for platform-conditional code paths in the frontend or backend

---

## AD-002: CUDA Included in Bundle with CPU Fallback Guaranteed

**Decision:** The application bundles PyTorch with CUDA support for GPU acceleration, but guarantees full functionality on CPU-only systems via automatic fallback.

**PRD Reference:**
- Requirements doc Section 7: "GPU | NVIDIA (CUDA 지원)"
- PRD Scenario 3 예외 처리: "GPU 미사용 시: Whisper CPU 폴백 (느리지만 동작)"
- PRD Edge Case 7: "NVENC 미지원 GPU → 경고 토스트 + libx264 폴백으로 내보내기 계속"

**Evidence in Codebase:**

1. **Whisper STT fallback** (`backend/services/subtitle_generator.py` lines 48-56):
   ```python
   device = "cuda" if torch.cuda.is_available() else "cpu"
   result = model.transcribe(tmp_path, language=language, fp16=(device == "cuda"))
   ```
   - Automatically selects CUDA when available, falls back to CPU
   - Disables fp16 on CPU (fp16 requires CUDA)

2. **NVENC encoder fallback** (`backend/services/exporter.py` lines 15-33):
   ```python
   def _detect_encoder() -> str:
       # ... checks if h264_nvenc is available and functional ...
       return "libx264"  # fallback
   ```
   - Probes NVENC availability with a real encode test (`nullsrc` → `h264_nvenc`)
   - Falls back to `libx264` software encoding if NVENC fails

3. **Health endpoint reports GPU status** (`src/bun/python-manager.ts` lines 140-154):
   ```typescript
   async function getBackendHealth(): Promise<{
     status: string; gpu_available: boolean; nvenc_available: boolean;
   } | null>
   ```

**Rationale:**
- CUDA acceleration provides 5-10x speedup for Whisper transcription
- NVENC provides hardware-accelerated H.264 encoding (faster, lower CPU usage)
- Not all users have NVIDIA GPUs; CPU fallback ensures universal compatibility
- Bundle includes CUDA runtime so users don't need separate CUDA Toolkit installation
- `torch` 2.10.0 Windows wheels include CUDA 12.x support (see `backend/uv.lock`)

**Implications:**
- Bundle size is 5-7GB due to PyTorch+CUDA and Whisper medium model
- First-time startup may be slower on CPU-only systems (no CUDA warmup needed, but transcription takes longer)
- Two distinct fallback paths exist: Whisper (CUDA→CPU) and FFmpeg encoding (NVENC→libx264)
- Test gap identified: neither fallback path is currently unit-tested with mocked `torch.cuda.is_available() == False` (see TG-002)

---

## AD-003: NSIS/Inno Setup Installer with Whisper Medium Model Included

**Decision:** Distribution uses a Windows installer (NSIS or Inno Setup) that bundles the complete application including the Whisper `medium` model, resulting in a 5-7GB installer package.

**PRD Reference:**
- PRD Scenario 3 예외 처리: "Whisper 첫 실행 시 모델 다운로드: 프로그레스에 'Downloading medium model (1.5GB)...' 표시"
- Requirements doc Section 3: "모델: medium 권장 (한국어 인식 성능과 속도 균형)"
- Constraint: "NSIS/Inno Setup installer with Whisper medium model included (5-7GB allowed)"

**Evidence in Codebase:**
- `backend/services/subtitle_generator.py` line 12-23: Model loading with caching (`_cached_model`) — designed for pre-bundled model that loads from local cache
- `backend/config.py` line 26: Default model is `"medium"` in `SubtitleConfig`
- `docs/design/future-fixes.md` FF-011: Documents that `python-manager.ts` needs a PyInstaller exe branch for production distribution
- `docs/remaining-work.md` line 119: "torch 2.10.0 — PyPI 기본 (CUDA 12.x Windows 휠 포함)"

**Rationale:**
- Bundling the model eliminates first-run download friction (1.5GB download would fail on poor connections)
- `medium` model balances Korean speech recognition accuracy vs. size/speed
- NSIS/Inno Setup are proven Windows installer frameworks supporting large payloads
- PyInstaller bundles the Python backend + all dependencies into a single exe
- 5-7GB is acceptable for a desktop app with ML capabilities (comparable to game installs)

**Bundle Contents:**
| Component | Approximate Size |
|-----------|-----------------|
| PyTorch + CUDA runtime | ~2.5GB |
| Whisper medium model | ~1.5GB |
| FFmpeg binaries | ~150MB |
| Python runtime + deps | ~500MB |
| Electrobun + frontend | ~100MB |
| OpenCV, librosa, etc. | ~200MB |

**Implications:**
- Production build requires PyInstaller packaging step (not yet implemented — see FF-011)
- `python-manager.ts` needs a third spawn branch for bundled `backend.exe` (future fix)
- Installer must handle Windows Defender SmartScreen warnings (code signing recommended)
- Update mechanism not defined for MVP — full reinstall required for updates

---

## AD-004: Relative Storage Paths (project-local) Instead of %APPDATA%/Vaya/

**Decision:** All application storage (thumbnails, analysis results, config, exports) uses paths relative to the backend directory rather than the Windows standard `%APPDATA%/Vaya/` user data location.

**PRD Reference:**
- PRD Scenario 5: "출력 폴더: `~/Videos/Vaya/` (기본)" — PRD intended user-facing paths
- PRD Scenario 6: "설정값은 `config.yaml`에 영속 저장되어 유지됨"

**Evidence in Codebase:**

1. **Static file storage** (`backend/main.py` lines 21-23):
   ```python
   storage_path = Path(__file__).parent / "storage"
   storage_path.mkdir(parents=True, exist_ok=True)
   app.mount("/static", StaticFiles(directory=str(storage_path)), name="static")
   ```

2. **Thumbnails** (`backend/routers/upload.py` lines 15-16):
   ```python
   STORAGE_DIR = Path(__file__).parent.parent / "storage"
   THUMBNAILS_DIR = STORAGE_DIR / "thumbnails"
   ```

3. **Analysis results** (`backend/routers/analyze.py` lines 10-11):
   ```python
   STORAGE_DIR = Path(__file__).parent.parent / "storage"
   ANALYSIS_DIR = STORAGE_DIR / "analysis"
   ```

4. **Export output** (`backend/services/exporter.py` lines 11-12):
   ```python
   STORAGE_DIR = Path(__file__).parent.parent / "storage"
   OUTPUT_DIR = STORAGE_DIR / "output"
   ```

5. **Config file** (`backend/config.py` line 7):
   ```python
   CONFIG_PATH = Path(__file__).parent / "config.yaml"
   ```

**Current Path Layout:**
```
backend/
├── config.yaml              # Settings persistence
├── storage/
│   ├── thumbnails/{id}/     # 5-second interval JPEGs
│   ├── analysis/{id}/       # Highlight data + subtitles.srt
│   └── output/              # Exported MP4 files
```

**Rationale:**
- Simplifies development — no platform-specific path resolution needed
- Works identically in dev mode (`uv run`) and test environments
- Config file co-located with backend code for easy access
- MVP prioritizes simplicity over production-grade file organization
- Session data is intentionally not persisted (conscious decision — see CD-003), so temporary storage location is acceptable

**Trade-offs vs. %APPDATA%/Vaya/:**
| Aspect | Current (Relative) | %APPDATA%/Vaya/ |
|--------|-------------------|-----------------|
| Dev simplicity | ✅ No path config needed | ❌ Needs env detection |
| Multi-user support | ❌ Single location | ✅ Per-user isolation |
| Uninstall cleanup | ❌ Manual | ✅ Standard Windows cleanup |
| Permissions | ⚠️ May fail in Program Files | ✅ Always writable |
| Production readiness | ❌ Not production-grade | ✅ Windows standard |

**Implications:**
- Export output goes to `backend/storage/output/` instead of `~/Videos/Vaya/` (documented as FF-001)
- Config file lives inside the project, not in user profile directory
- If installed to `C:\Program Files\`, write permissions may fail (production blocker)
- Migration to `%APPDATA%/Vaya/` will require centralizing all `STORAGE_DIR` references into `AppConfig`
- Thumbnails and analysis data accumulate in the project directory without cleanup

---

## Summary Matrix

| ID | Decision | Scope | Reversibility | Priority to Change |
|----|----------|-------|---------------|-------------------|
| AD-001 | Windows-only | Platform | High effort | Post-MVP (if ever) |
| AD-002 | CUDA + CPU fallback | Runtime | Low effort | Stable — keep as-is |
| AD-003 | NSIS installer + Whisper model | Distribution | Medium effort | Needs implementation (FF-011) |
| AD-004 | Relative storage paths | File system | Medium effort | Should migrate for production |
