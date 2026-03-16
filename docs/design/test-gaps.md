# Test Gaps — PRD vs Implementation

> Classification: **Test Gaps**
> Date: 2026-03-16
> Scope: Vaya MVP (11 user stories, US-001–US-011)

---

## TG-001: config.py Unit Tests Missing

**PRD Reference**: "설정값은 `config.yaml`에 영속 저장되어 유지됨" (PRD §설정 패널 컨트롤)

**Gap Description**:
`backend/config.py` defines `AppConfig` (Pydantic model), `load_config()`, and `save_config()` — the core configuration persistence layer used by analysis, export, and settings routers. However, **no unit tests exist** for this module. The project has no `tests/unit/` directory at all; only E2E tests exist under `tests/e2e/`.

**What Is Untested**:
| Function / Class | Risk | Notes |
|---|---|---|
| `load_config()` with existing YAML file | Medium | Could silently return defaults on malformed YAML |
| `load_config()` with missing file | Low | Returns `AppConfig()` defaults — logic is simple but unverified |
| `save_config()` roundtrip | Medium | YAML serialization of Pydantic `model_dump()` — could lose types |
| `AppConfig` default values | Medium | 6+ numeric defaults (thresholds, weights, durations) used by analysis pipeline |
| `HighlightConfig` / `SilenceConfig` / `SubtitleConfig` | Low | Pydantic validation covers basic typing, but boundary values are not tested |
| Corrupt/partial YAML handling | High | `yaml.safe_load()` on malformed input could raise or return unexpected types |

**Impact**: Config values directly control highlight detection sensitivity, silence thresholds, and subtitle generation. Incorrect defaults or serialization bugs would silently produce wrong editing results with no test catching the regression.

**Recommended Tests**:
1. `test_load_config_missing_file` — returns valid `AppConfig` with expected defaults
2. `test_load_config_valid_yaml` — roundtrip: save then load, assert equality
3. `test_load_config_partial_yaml` — only some keys present, others use defaults
4. `test_load_config_empty_yaml` — empty file returns defaults
5. `test_load_config_malformed_yaml` — graceful error or defaults
6. `test_save_config_creates_file` — file is created with correct YAML content
7. `test_config_default_values` — assert all numeric defaults match PRD expectations

**Priority**: Medium — config is stable but any regression would cascade to all analysis results.

---

## TG-002: CUDA/CPU Fallback Verification Missing

**PRD Reference**:
- "GPU 미사용 시: Whisper CPU 폴백 (느리지만 동작)" (PRD §에러/엣지 케이스 처리)
- "NVENC 미지원 GPU | 경고 토스트 + libx264 폴백으로 내보내기 계속" (PRD Edge Case #7)
- Constraint: "CUDA included in bundle with CPU fallback guaranteed"

**Gap Description**:
The codebase has two distinct CUDA→CPU fallback paths, neither of which is tested:

### Fallback Path A: Whisper STT (`subtitle_generator.py:50`)
```python
device = "cuda" if torch.cuda.is_available() else "cpu"
result = model.transcribe(tmp_path, language=language, fp16=(device == "cuda"))
```
- The `fp16` flag is set based on device — using `fp16=True` on CPU would crash
- All existing tests mock the entire `whisper.load_model` / `model.transcribe` chain, so neither the CUDA path nor the CPU fallback path is ever exercised
- No test verifies that `torch.cuda.is_available() == False` correctly triggers `fp16=False`

### Fallback Path B: NVENC → libx264 (`health.py` + exporter)
```python
# health.py
def _check_nvenc() -> bool:
    result = subprocess.run(["ffmpeg", "-encoders"], ...)
    return "h264_nvenc" in result.stdout
```
- Health endpoint reports NVENC availability, but the exporter's actual fallback from `h264_nvenc` to `libx264` is not tested
- No test simulates a scenario where `_check_nvenc()` returns `False` and verifies the export still succeeds with libx264

**What Is Untested**:
| Scenario | Location | Risk |
|---|---|---|
| `torch.cuda.is_available()` returns `False` → CPU transcription works | `subtitle_generator.py:50` | High — core functionality on non-GPU machines |
| `fp16=False` set correctly on CPU path | `subtitle_generator.py:56` | High — `fp16=True` on CPU causes RuntimeError |
| `_check_gpu()` returns `False` in health check | `health.py:10-15` | Low — simple boolean |
| NVENC unavailable → libx264 fallback in export | `exporter.py` (FFmpeg cmd) | Medium — affects all exports on non-NVIDIA GPUs |
| GPU memory exhaustion → graceful degradation | Not implemented | Medium — PRD mentions "GPU 메모리 부족" error handling |

**Impact**: The CPU fallback is the guaranteed deployment path — many users will not have NVIDIA GPUs. Without tests, a regression in the fallback logic would break the app for all non-GPU users with no CI protection.

**Recommended Tests**:
1. `test_subtitle_cpu_fallback` — mock `torch.cuda.is_available()` to return `False`, verify `transcribe()` called with `fp16=False`
2. `test_subtitle_gpu_path` — mock `torch.cuda.is_available()` to return `True`, verify `transcribe()` called with `fp16=True`
3. `test_health_no_gpu` — mock `torch.cuda.is_available()` to return `False`, verify health response `gpu_available=False`
4. `test_health_no_nvenc` — mock FFmpeg encoder list without `h264_nvenc`, verify `nvenc_available=False`
5. `test_export_libx264_fallback` — verify export succeeds with libx264 when NVENC unavailable
6. `test_gpu_memory_error_handling` — simulate CUDA OOM, verify graceful error (PRD edge case)

**Priority**: High — CPU fallback is a bundle guarantee and must work reliably on all target machines.

---

## Summary

| ID | Gap | Priority | PRD Edge Cases Affected |
|---|---|---|---|
| TG-001 | config.py has no unit tests | Medium | EC-9 (설정 변경 시 수동 구간 유지) |
| TG-002 | CUDA/CPU fallback paths untested | High | EC-7 (NVENC 미지원 GPU), error handling (GPU 메모리 부족) |
