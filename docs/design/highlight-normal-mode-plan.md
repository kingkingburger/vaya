# Vaya 하이라이트/일반 모드 분리 계획

**작성일:** 2026-06-29
**상태:** 계획
**범위:** 구현 전 설계. 이 문서는 코드 변경 없이 모드 분리 방향만 정의한다.

## 목표

Vaya의 분석 흐름을 두 가지 사용 모드로 분리한다.

- **하이라이트 모드:** 현재 자동 편집 흐름을 유지한다. 오디오 에너지, 화면 변화량, 무음 구간, 자막을 분석하고 highlight 구간만 잘라 YouTube/Shorts로 내보낸다.
- **일반 모드:** highlight 탐지를 생략한다. 전체 영상을 유지하고, 필요한 경우 Whisper 자막만 생성해서 원본 전체 길이에 자막을 입혀 내보낸다.

핵심 목표는 긴 영상에서 불필요한 전체 분석 비용을 줄이고, 사용자가 “그냥 자막만 달린 원본 영상”을 빠르게 만들 수 있게 하는 것이다.

## 현재 구조 요약

현재 업로드 이후 프론트엔드는 `POST /api/video/{video_id}/analyze`를 자동 호출한다. 백엔드는 `backend/routers/analyze.py`에서 다음 작업을 순서대로 수행한다.

1. `services.audio_analysis.analyze_audio_energy`
2. `services.video_analysis.analyze_frame_difference`
3. `services.highlight_scorer.compute_highlights`
4. `services.silence_detector.detect_silence`
5. `services.subtitle_generator.generate_subtitles`

내보내기는 `backend/routers/export.py`를 통해 `services.exporter.export_video`를 호출한다. 현재 exporter는 highlight 구간을 기준으로 `trim`, `atrim`, `concat` filter graph를 만든다.

이 구조는 하이라이트 모드에는 맞지만, 일반 모드에서는 불필요하게 무겁다. 일반 모드는 highlight 점수 계산과 화면 변화량 분석이 필요 없다.

## 대상 사용자 흐름

### 하이라이트 모드

1. 사용자가 파일을 선택한다.
2. 앱이 metadata를 읽고 메인 화면으로 전환한다.
3. 하이라이트 모드가 선택되어 있으면 자동 highlight 분석을 시작한다.
4. 분석 완료 후 highlight 목록과 timeline overlay를 표시한다.
5. 사용자가 구간을 수정한다.
6. export 시 선택된 highlight 구간만 이어 붙인다.
7. 자막 옵션이 켜져 있으면 export timeline에 맞춰 자막을 remap한 뒤 burn-in한다.

### 일반 모드

1. 사용자가 파일을 선택한다.
2. 앱이 metadata를 읽고 메인 화면으로 전환한다.
3. 일반 모드가 선택되어 있으면 highlight 분석을 시작하지 않는다.
4. 사용자가 자막 생성을 켜면 Whisper 자막만 생성한다.
5. export 시 전체 영상 구간 `[0, duration]`을 사용한다.
6. 자막 옵션이 켜져 있으면 전체 영상 기준 SRT를 burn-in한다.

## 설계 원칙

- 모드 선택은 프론트 UI 상태만으로 끝내지 않고, 백엔드 요청에도 명시한다.
- 일반 모드는 highlight가 없어도 export 가능해야 한다.
- 하이라이트 모드의 기존 동작은 회귀시키지 않는다.
- Whisper 자막 생성은 highlight 분석과 분리 가능한 작업으로 만든다.
- 긴 영상 UX를 위해 upload 직후 무거운 분석을 강제하지 않는 방향을 우선한다.

## API 계획

### 1. 자막 생성 전용 endpoint 추가

새 endpoint:

```http
POST /api/video/{video_id}/subtitles/generate
```

역할:

- `video_id`가 존재하는지 확인한다.
- 해당 영상에 대해 Whisper 자막 생성만 수행한다.
- 진행률은 기존 `/ws/progress/{video_id}`를 재사용한다.
- 결과는 `store[video_id]["subtitles"]`와 `storage/analysis/{video_id}/subtitles.srt`에 저장한다.

분리 이유:

- `POST /api/video/{video_id}/analyze`는 하이라이트 탐지 책임을 유지한다.
- 일반 모드는 `analyze`를 호출하지 않고 자막만 생성할 수 있다.

### 2. export 요청에 mode 추가

`ExportRequest`에 `mode`를 추가한다.

```python
class ExportRequest(BaseModel):
    mode: Literal["highlight", "normal"] = "highlight"
    youtube: bool = True
    shorts: bool = False
    subtitles: bool = True
    crop_offset: int = 0
```

동작:

- `mode == "highlight"`: 기존처럼 `store[video_id]["highlights"]`를 사용한다.
- `mode == "normal"`: 내부적으로 전체 구간을 하나의 segment로 만든다.

```python
HighlightSegment(start=0, end=info.duration, score=0, manual=True)
```

이렇게 하면 exporter의 기존 trim/concat 구조를 재사용할 수 있다.

### 3. 분석 상태 lock 분리

현재 `_analyzing`, `_exporting` set이 있다. 자막 전용 작업이 추가되면 다음 중 하나를 선택한다.

- 간단한 방식: `_analyzing`을 자막 생성에도 같이 사용한다.
- 명확한 방식: `_subtitle_generating: set[str]`를 새로 둔다.

초기 구현은 간단한 방식을 권장한다. 자막 생성과 export가 같은 파일/자막 상태를 공유하므로 동시에 돌리지 않는 편이 안전하다.

## 백엔드 변경 계획

### `backend/routers/subtitle.py`

- `POST /api/video/{video_id}/subtitles/generate` 추가
- `routers.analyze._generate_subtitles` 또는 공통 service helper를 호출
- WebSocket으로 `subtitle` 진행률 broadcast
- 완료 시 `store[video_id]["subtitles"]` 저장

### `backend/routers/analyze.py`

- 하이라이트 분석 endpoint로 책임을 좁힌다.
- 기존처럼 분석 마지막에 자막까지 자동 생성할지 여부는 옵션화한다.
- 권장: request body에 `generate_subtitles: bool = True`를 추가하고, 하이라이트 모드 기본값만 true로 둔다.

### `backend/routers/export.py`

- `ExportRequest.mode`를 읽는다.
- 일반 모드에서는 highlight가 없어도 export를 허용한다.
- 일반 모드의 `silence` 제거는 기본 off로 둔다. 전체 원본 보존이 일반 모드의 의미이기 때문이다.

### `backend/services/exporter.py`

- 가능한 한 기존 `export_video`를 유지한다.
- 일반 모드 segment는 router에서 만들어 넘긴다.
- exporter에는 “주어진 segment를 자르고 이어 붙인다”는 책임만 남긴다.

## 프론트엔드 변경 계획

### UI

파일 업로드 화면 또는 메인 화면 상단에 모드 선택을 추가한다.

```text
[하이라이트] [일반]
```

권장 기본값:

- 짧은 영상 또는 기존 동작 유지가 중요하면 `하이라이트`
- 긴 영상 UX를 우선하면 `일반`

초기 MVP에서는 사용자가 직접 선택하게 두는 편이 안전하다.

### `src/views/main/main.ts`

- `currentMode: "highlight" | "normal"` 상태 추가
- 업로드 완료 후:
  - `highlight`: 기존처럼 `startAnalysis(videoId)`
  - `normal`: 분석 자동 시작 생략
- 일반 모드에서는 highlight list와 timeline editing UI를 숨기거나 read-only 상태로 둔다.
- 일반 모드에는 `자막 생성` 버튼을 제공한다.
- export 요청 body에 `mode`를 포함한다.

## 자막 처리 정책

### 하이라이트 모드

- 자막은 원본 전체에서 생성할 수 있다.
- export 시 현재 구현처럼 highlight timeline에 맞춰 remap한다.
- 나중에 속도를 더 줄이고 싶으면 highlight 구간만 잘라 Whisper를 돌리는 최적화를 추가한다.

### 일반 모드

- 자막은 원본 전체 기준으로 생성한다.
- export도 전체 영상 기준이므로 remap이 사실상 필요 없다.
- 기존 exporter 구조를 재사용하면 `[0, duration]` 단일 segment 기준 remap을 거쳐도 결과는 동일해야 한다.

## 단계별 구현 계획

### Phase 1: 최소 모드 분리

- `ExportRequest.mode` 추가
- 일반 모드 export 시 전체 구간 segment 생성
- 프론트에서 export body에 mode 전달
- 일반 모드에서 highlight 분석 자동 시작을 막음

완료 기준:

- 일반 모드에서 highlight 없이 export 요청이 성공한다.
- 하이라이트 모드 기존 export가 그대로 동작한다.

### Phase 2: 자막 생성 전용 endpoint

- `POST /api/video/{video_id}/subtitles/generate` 추가
- 일반 모드 UI에 `자막 생성` 버튼 추가
- WebSocket 진행률은 기존 progress banner 재사용

완료 기준:

- 일반 모드에서 오디오/화면 분석 없이 자막만 생성된다.
- 생성된 자막이 subtitle list에 표시된다.
- export 시 자막이 전체 영상에 burn-in된다.

### Phase 3: 긴 영상 UX 정리

- upload는 metadata 중심으로 빠르게 끝내는 방향 검토
- 썸네일 lazy/background 생성 검토
- 1시간 이상 영상에서는 기본 모드 추천 또는 경고 문구 조정

완료 기준:

- 긴 영상 업로드 후 사용자가 빠르게 메인 화면에 진입한다.
- 일반 모드에서는 highlight 분석 비용이 발생하지 않는다.

### Phase 4: 성능 최적화

- `video_analysis.py`의 JPEG 임시파일 방식 개선 검토
- FFmpeg raw stream 기반 프레임 비교로 디스크 I/O 제거
- 하이라이트 모드에서 자막 생성 optional 처리
- highlight 구간만 Whisper 처리하는 fast subtitle mode 검토

완료 기준:

- 하이라이트 모드 분석 시간이 기존보다 줄어든다.
- 일반 모드와 하이라이트 모드의 비용 차이가 명확해진다.

## 테스트 계획

### 백엔드

- 일반 모드 export는 highlight가 없어도 성공해야 한다.
- 일반 모드 export는 전체 duration segment를 사용해야 한다.
- 하이라이트 모드 export는 highlight가 없으면 기존처럼 실패해야 한다.
- 자막 생성 endpoint는 subtitles를 store와 SRT 파일에 저장해야 한다.
- export 중 분석 또는 자막 생성이 동시에 시작되지 않도록 lock 동작을 확인한다.

### 프론트엔드

- 모드 선택 UI가 현재 모드를 정확히 반영해야 한다.
- 일반 모드 업로드 후 자동 highlight 분석이 시작되지 않아야 한다.
- 하이라이트 모드 업로드 후 기존처럼 자동 분석이 시작되어야 한다.
- 일반 모드에서 자막 생성 후 export 버튼 흐름이 동작해야 한다.

### E2E

- 일반 모드: sample.mp4 업로드 → 자막 생성 → YouTube export
- 하이라이트 모드: sample.mp4 업로드 → 자동 분석 → highlight 표시 → export

## 비목표

- 이번 계획은 실제 구현을 포함하지 않는다.
- ML 기반 장면 이해 모델 추가는 포함하지 않는다.
- Whisper 모델 최적화, GPU 메모리 관리, installer packaging 개선은 별도 주제로 둔다.
- 일반 모드에서 timeline 편집 기능을 제공하는 것은 초기 범위에서 제외한다.

## 주요 위험

- 일반 모드에서도 현재 exporter를 그대로 쓰면 전체 영상을 한 번 trim/concat하므로 stream copy가 아니라 재인코딩된다.
- 긴 영상 전체 자막 생성은 여전히 오래 걸릴 수 있다. 다만 highlight 분석 비용은 제거된다.
- 자막 생성과 export를 동시에 허용하면 SRT 파일 상태가 꼬일 수 있다.
- 기존 문서에는 Electrobun 시절 설명이 남아 있어, 구현 시 Tauri 기준 코드만 신뢰해야 한다.

## 권장 구현 순서

1. export 일반 모드 지원
2. 프론트 모드 상태 추가
3. 일반 모드에서 자동 highlight 분석 생략
4. 자막 생성 전용 endpoint 추가
5. 일반 모드 UI에 자막 생성 버튼 추가
6. 백엔드/프론트/E2E 테스트 추가

이 순서가 가장 작고 안전하다. 먼저 “일반 모드도 전체 영상 export가 된다”는 서버 invariant를 만든 뒤, UI를 붙이고, 마지막에 자막 전용 흐름을 분리한다.
