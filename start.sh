#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Vaya 시작 ==="

# 1. 의존성 설치 (없으면 설치, 있으면 스킵)
echo "[1/2] 의존성 확인..."
cd "$ROOT_DIR/backend" && uv sync --quiet
cd "$ROOT_DIR" && bun install --silent 2>/dev/null

# 2. Tauri 실행
echo "[2/2] Tauri 앱 시작..."
cd "$ROOT_DIR"
bun run start

echo "종료 중..."
echo "=== Vaya 종료 ==="
