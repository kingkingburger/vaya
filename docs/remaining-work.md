# Vaya — 남은 작업 목록

**마지막 업데이트:** 2026-02-26
**현재 상태:** Phase 1 진행 중 (90% 완료)

---

## Phase 1 잔여 이슈 (우선 해결)

### 1. 웹뷰 main.ts 로드 실패

**문제:** Electrobun이 `views://main/main.ts`를 빌드 시 JS로 변환하지 않아 웹뷰에서 스크립트 로드 실패.

**로그:**
```
ERROR: Could not open views file: ...\Resources\app\views\main/main.ts
```

**해결 방안:**
- `electrobun.config.ts`의 `views.main.entrypoint`가 TS → JS 번들링을 처리해야 함
- `index.html`에서 `<script src="main.ts">` 대신 빌드된 JS 파일을 참조하도록 수정
- 또는 Electrobun의 views 빌드 파이프라인이 자동으로 TS를 컴파일하는지 확인 필요
- 참고: Electrobun 문서의 views entrypoint 설정 확인 → https://blackboard.sh/electrobun/docs/apis/cli/build-configuration/

### 2. RPC 메시지 전송 실패 (`backendReady` / `backendError`)

**문제:** `win.webview.rpc.backendReady()`가 `undefined` — 웹뷰 스크립트가 로드되지 않아 RPC 핸들러 미등록.

**원인:** 이슈 1이 해결되면 자동으로 해결될 가능성 높음. 추가로 웹뷰 로드 완료를 기다리는 로직 필요할 수 있음.

**해결 방안:**
- 이슈 1 해결 후 재테스트
- `setTimeout(2000)` 대신 웹뷰 로드 완료 이벤트 사용 (Electrobun API 확인)
- 웹뷰에서 `electroview.rpc.send.log({ msg: "ready" })` 로 준비 신호를 보내고, bun 측에서 수신 후 상태 전송

### 3. 포트 충돌 (8765)

**문제:** 이전 테스트에서 종료되지 않은 Python 프로세스가 포트를 점유.

**해결 방안:**
- `python-manager.ts`에서 시작 전 기존 프로세스 확인 및 종료
- 또는 포트 사용 중이면 health check로 기존 서버 재사용

---

## Phase 1 완료된 항목

- [x] Backend: FastAPI 앱 (health, settings 라우터) — 테스트 통과
- [x] Backend: `uv sync` — 70개 패키지 설치 성공 (torch 2.10.0 포함)
- [x] Backend: config.yaml YAML 영속화 — GET/PUT 동작 확인
- [x] Backend: Health 엔드포인트 — `{status: ok, gpu_available, nvenc_available}` 반환
- [x] Frontend: Electrobun 윈도우 생성 및 실행
- [x] Frontend: python-manager.ts — 프로젝트 루트 경로 자동 감지 (빌드 디렉토리에서도 동작)
- [x] Frontend: uv run으로 Python 백엔드 자동 시작
- [x] Frontend: HTML/CSS 웹뷰 로드 성공 (다크 테마)
- [x] Infrastructure: .gitignore, setup-backend.sh

---

## Phase 1 게이트 체크 결과

| 항목 | 결과 | 비고 |
|------|------|------|
| Python subprocess 시작 | **PASS** | uv run으로 정상 시작 |
| RPC 메시징 | **PENDING** | 웹뷰 스크립트 로드 이슈 해결 후 재테스트 |
| 드래그&드롭 경로 추출 | **CONFIRMED NOT WORKING** | WebView2 한정. `openFileDialog()` 폴백 사용 |
| 3일 타임박스 | 1일차 | 남은 이슈는 설정 문제이므로 프레임워크 자체 문제 아님 |

---

## Phase 2~7 요약 (전체 계획: `.omc/plans/vaya-ralplan.md`)

### Phase 2: 영상 업로드, 메타데이터, 썸네일
- POST /api/upload (파일 경로 전달)
- FFprobe 메타데이터 추출
- 타임라인 썸네일 생성 (5초 간격)
- Canvas 기반 타임라인 UI

### Phase 3: 오디오/영상 분석, 하이라이트 추출
- librosa 오디오 볼륨 분석
- OpenCV 프레임 변화량 분석
- 복합 스코어링 + 구간 선택
- WebSocket 실시간 진행률

### Phase 4: 타임라인 인터랙션, 수동 편집
- Canvas 세그먼트 추가/삭제/리사이즈/드래그
- 설정 패널 (슬라이더)
- Undo/Redo

### Phase 5: 자막 생성 (Whisper STT)
- Whisper 로컬 실행 (CUDA)
- 한국어 음성인식 → SRT 생성
- Phase 3/4와 병렬 개발 가능

### Phase 6: 영상 내보내기 파이프라인
- YouTube 16:9 (1920x1080 60fps 8Mbps NVENC)
- Shorts 9:16 (1080x1920 60fps 6Mbps 센터 크롭)
- 자막 번인 (FFmpeg subtitles 필터)

### Phase 7: 통합, 폴리시, 에러 핸들링
- 전체 워크플로우 연결
- 에러 상태 처리
- 다크 테마 폴리시
- 키보드 단축키

---

## 기술 참고사항

### Electrobun 관련
- **패키지:** `electrobun@1.14.4`
- **Windows CLI 압축 해제 이슈:** `npx electrobun dev` 시 tar 경로 문제 → 수동 `cd .cache && tar -xzf` 로 해결
- **WebView2:** `dataTransfer.files[0].path` 미지원 (Electron 전용 API). `openFileDialog()` 사용
- **RPC:** `BrowserView.defineRPC<T>()` / `Electroview.defineRPC<T>()` 패턴
- **빌드 경로:** `{projectRoot}/build/dev-win-x64/Vaya-dev/Resources/app/`

### Python 백엔드
- **uv 0.9.27** — `uv sync`로 의존성 관리, `uv run`으로 실행
- **torch 2.10.0** — PyPI 기본 (CUDA 12.x Windows 휠 포함)
- **openai-whisper 20250625** — 최신 버전
- **FastAPI 0.133.1** / **uvicorn 0.41.0**
