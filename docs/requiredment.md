# Vaya — 요구사항 정의서

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | Vaya |
| **목적** | 게임 영상 자동 편집 데스크톱 앱 (개인용 MVP) |
| **비용 목표** | 0원 (오픈소스만 사용) |

---

## 1. 입력

- OBS 등으로 PC 녹화한 게임 영상
- 게임 장르: 특정 장르 한정 아님 (FPS, MOBA, 샌드박스 등 혼합)
- 파일 형식: MP4, MKV 등 FFmpeg 지원 포맷

---

## 2. 자동 컷편집

### 2-1. 하이라이트 구간 추출

- **오디오 분석**: 볼륨 급등 구간 감지 (함성, 효과음, 긴박한 BGM 등)
- **영상 분석**: 프레임 변화량 급등 구간 감지 (킬, 이펙트, 장면 전환 등)
- **복합 스코어링**: 오디오 + 영상 점수를 가중합산하여 하이라이트 판단
- 상위 N% 구간을 자동 선택 (설정으로 조절 가능)
- 최소/최대 클립 길이 제한
- 근접 구간 자동 병합

### 2-2. 무음 구간 제거

- 일정 데시벨 이하인 구간을 무음으로 판단
- 무음 구간의 최소 길이 설정 가능
- 앞뒤 패딩(여유)을 두어 자연스러운 컷

---

## 3. 자막 처리

- **방식**: OpenAI Whisper 로컬 실행 (CUDA 가속)
- **대상**: 내 음성 (게임 중 말하는 것)
- **출력**: SRT 파일 생성 → FFmpeg으로 영상에 번인
- **스타일**: 기본 흰색 자막 + 검정 테두리 (MVP)
- **모델**: medium 권장 (한국어 인식 성능과 속도 균형)
- **언어**: 한국어 (ko)

---

## 4. 출력 형식

### 4-1. 유튜브용 (16:9)

- 해상도: 1920x1080
- FPS: 60
- 코덱: H.264 (NVENC GPU 인코딩)
- 비트레이트: 8Mbps
- 자막: 하단 중앙

### 4-2. 유튜브 쇼츠용 (9:16)

- 해상도: 1080x1920
- FPS: 60
- 코덱: H.264 (NVENC GPU 인코딩)
- 비트레이트: 6Mbps
- 크롭: 중앙 크롭 (MVP) → 스마트 크롭 (향후)
- 자막: 하단

---

## 5. UI 요구사항

### 5-1. 프레임워크

- Electrobun (TypeScript + Bun)
- Webview 기반 UI (HTML/CSS/JS)

### 5-2. 핵심 화면

**드래그&드롭 업로드**
- 영상 파일을 끌어다 놓거나 클릭하여 선택
- 업로드 후 메타데이터 표시 (길이, 해상도, FPS)

**타임라인 + 썸네일**
- 일정 간격으로 추출한 썸네일을 타임라인에 나열
- 하이라이트 구간을 색상 오버레이로 시각화
- 구간 수동 추가/제거/드래그 조정 가능

**설정 패널**
- 오디오/영상 가중치 슬라이더
- 상위 구간 비율 (%)
- Whisper 모델 선택 (tiny ~ large)
- 무음 기준 데시벨
- 무음 최소 길이

**내보내기 패널**
- 유튜브용 (16:9) 체크박스
- 쇼츠용 (9:16) 체크박스
- 자막 포함 여부
- 내보내기 버튼

**진행률 표시**
- WebSocket으로 실시간 진행률 수신
- 프로그레스 바 + 현재 작업 단계 메시지

---

## 6. 아키텍처

### 6-1. 통신 방식

- Electrobun Main Process ↔ Webview: Electrobun RPC (typed)
- Electrobun Main Process ↔ Python Server: HTTP (REST API) + WebSocket
- Python Server: FastAPI + uvicorn, localhost:8765

### 6-2. 앱 시작 시퀀스

1. Electrobun 앱 실행
2. Main Process가 Python 자식 프로세스 실행
3. FastAPI 서버가 localhost:8765에서 대기
4. Health check 통과 후 Webview UI 활성화

---

## 7. 개발 환경

| 항목 | 내용 |
|------|------|
| OS | Windows |
| GPU | NVIDIA (CUDA 지원) |
| Python | 3.10+ |
| Node/Bun | Bun 최신 |
| 프레임워크 | Electrobun |

---

## 8. API 엔드포인트

```
POST   /api/upload                → 영상 업로드
GET    /api/video/{id}/info       → 영상 메타데이터
POST   /api/video/{id}/analyze    → 분석 시작
GET    /api/video/{id}/highlights → 하이라이트 구간 목록
PUT    /api/video/{id}/highlights → 구간 수동 수정
POST   /api/video/{id}/export     → 내보내기 시작
GET    /api/video/{id}/thumbnails → 타임라인 썸네일
GET    /api/settings              → 설정값 조회
PUT    /api/settings              → 설정값 변경
GET    /api/health                → 서버 상태 확인

WS     /ws/progress/{id}          → 실시간 진행률
```

---

## 9. 기술 스택

### 프론트엔드

| 도구 | 역할 |
|------|------|
| Electrobun | 데스크톱 앱 쉘 |
| Bun | 메인 프로세스 런타임 |
| TypeScript | 전체 프론트 코드 |
| HTML + CSS | Webview UI |
| Canvas API | 타임라인 렌더링 |

### 서버 (Python)

| 도구 | 역할 |
|------|------|
| FastAPI + uvicorn | REST API + WebSocket |
| FFmpeg + ffmpeg-python | 영상 처리 |
| librosa | 오디오 분석 |
| OpenCV (cv2) | 영상 분석 |
| Whisper (로컬) | 음성인식 (CUDA) |
| PyYAML | 설정 관리 |

---

## 10. 설정 기본값

```yaml
highlight:
  audio_weight: 0.6
  video_weight: 0.4
  top_percent: 30
  min_clip_duration: 3
  max_clip_duration: 60
  merge_gap: 2

silence:
  threshold_db: -40
  min_silence_duration: 1.5
  padding: 0.3

subtitle:
  model: "medium"
  language: "ko"
  font_size: 24
  font_color: "white"
  outline_color: "black"
  position: "bottom"
```

---

## 11. 향후 확장 (MVP 이후)

- 앱 내 영상 플레이어 미리보기
- 장르 자동 감지 + 프리셋
- 썸네일 자동 생성
- 유튜브 API 연동 (앱에서 바로 업로드)
- BGM 자동 삽입
- 자막 스타일 커스터마이징
- 스마트 크롭 (관심 영역 감지)
- 다국어 자막 지원