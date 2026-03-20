# Vaya — 게임 영상 자동 편집 데스크톱 앱

게임 영상을 드래그&드롭하면, AI가 하이라이트를 자동 감지하고 자막을 생성하여 YouTube/Shorts용으로 내보내는 올인원 편집 도구.

![Electrobun](https://img.shields.io/badge/Electrobun-WebView2-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-green)
![Whisper](https://img.shields.io/badge/Whisper-STT-orange)
![FFmpeg](https://img.shields.io/badge/FFmpeg-Video-red)

## 주요 기능

- **자동 하이라이트 감지** — 오디오 에너지 + 프레임 변화량 분석으로 킬/이벤트 구간 자동 탐지
- **AI 자막 생성** — OpenAI Whisper (CUDA 가속) 한국어 음성 인식
- **타임라인 편집** — 줌/스크롤 가능한 타임라인에서 하이라이트 구간 확인 및 수동 조정
- **YouTube & Shorts 내보내기** — NVENC 하드웨어 인코딩, 자막 번인, 세로 크롭 지원
- **실시간 진행 표시** — WebSocket 기반 분석/내보내기 프로그레스 + 유쾌한 로딩 메시지

## 기술 스택

| 영역 | 기술 |
|------|------|
| 데스크톱 | [Electrobun](https://electrobun.dev/) (Bun + WebView2) |
| 프론트엔드 | TypeScript, HTML/CSS, Canvas API |
| 백엔드 | Python FastAPI (REST + WebSocket) |
| 영상 처리 | FFmpeg / FFprobe, NVENC 하드웨어 인코딩 |
| 영상 분석 | OpenCV (프레임 차이), librosa (오디오 에너지) |
| 음성 인식 | OpenAI Whisper (CUDA 가속, 한국어) |
| 패키지 매니저 | bun (프론트), uv (백엔드) |

## 시작하기

### 사전 요구사항

- Python 3.10+, [uv](https://docs.astral.sh/uv/)
- [Bun](https://bun.sh/), Node.js
- [FFmpeg](https://ffmpeg.org/) (PATH에 등록)
- NVIDIA GPU (선택, CUDA/NVENC 가속용)

### 실행

```bash
# 원클릭 실행 (백엔드 + 프론트엔드 동시)
bash start.sh
```

또는 수동으로:

```bash
# 1. 백엔드
cd backend && uv sync && uv run uvicorn main:app --host 127.0.0.1 --port 8765

# 2. 프론트엔드 (별도 터미널)
bun install && npx electrobun dev
```

### 테스트

```bash
cd backend && uv run pytest           # 유닛 테스트 (34개)
cd backend && uv run pytest ../tests/e2e/ -v  # E2E 테스트 (30개)
```

## 프로젝트 구조

```
src/bun/              # Electrobun 메인 프로세스
src/views/main/       # WebView 프론트엔드 (HTML/CSS/TS)
backend/              # Python FastAPI 서버
  routers/            # API 엔드포인트
  services/           # 비즈니스 로직 (분석, 자막, 내보내기)
  ws/                 # WebSocket 프로그레스 매니저
tests/e2e/            # E2E 테스트 (백엔드 + Playwright)
docs/                 # PRD, 요구사항 문서
start.sh              # 원클릭 실행 스크립트
```

## 사용 흐름

1. **영상 드래그&드롭** 또는 **파일 선택** 으로 게임 영상 업로드
2. **자동 분석** — 오디오/영상 분석 → 하이라이트 스코어링 → 무음 감지 → 자막 생성
3. **타임라인에서 편집** — 하이라이트 구간 확인, 추가/삭제/리사이즈
4. **내보내기** — YouTube (16:9) / Shorts (9:16) 선택, 자막 포함 옵션

## 라이선스

MIT
