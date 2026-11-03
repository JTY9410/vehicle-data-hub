#!/usr/bin/env bash
# Docker Desktop CLI 가 PATH 에 없을 때 사용.
#   ./scripts/dc.sh up -d --build db web
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/Applications/Docker.app/Contents/Resources/bin:${HOME}/.docker/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"
if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI 를 찾을 수 없습니다. Docker Desktop 을 설치·실행하세요." >&2
  exit 127
fi
cd "$ROOT"
exec docker compose -f docker-compose.yml "$@"
