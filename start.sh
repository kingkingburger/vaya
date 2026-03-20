#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Vaya 시작 ==="

# 0. 이전 프로세스 정리 + 빌드 캐시 삭제
echo "[0/3] 이전 프로세스 정리..."
taskkill //F //IM electrobun.exe 2>/dev/null || true
taskkill //F //IM bun.exe 2>/dev/null || true
# 기존 백엔드 서버 종료 (port 8765)
for pid in $(netstat -ano 2>/dev/null | grep ":8765 " | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID "$pid" 2>/dev/null || true
done
rm -rf "$ROOT_DIR/build"

# 1. 의존성 설치 (없으면 설치, 있으면 스킵)
echo "[1/3] 의존성 확인..."
cd "$ROOT_DIR/backend" && uv sync --quiet
cd "$ROOT_DIR" && bun install --silent 2>/dev/null

# 2. 백엔드 서버 (백그라운드)
echo "[2/3] 백엔드 서버 시작 (port 8765)..."
cd "$ROOT_DIR/backend"
uv run uvicorn main:app --host 127.0.0.1 --port 8765 &
BACKEND_PID=$!

# 백엔드 준비 대기
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:8765/api/health > /dev/null 2>&1; then
        echo "  백엔드 준비 완료!"
        break
    fi
    sleep 1
done

# 3. 프론트엔드 실행
echo "[3/3] 프론트엔드 시작..."
cd "$ROOT_DIR"
npx electrobun dev

# 프론트엔드 종료 시 백엔드도 정리
echo "종료 중..."
kill $BACKEND_PID 2>/dev/null
echo "=== Vaya 종료 ==="
