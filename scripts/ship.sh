#!/bin/sh
# 로컬에서 테스트 후 GitHub / Docker / Vercel / Supabase(마이그레이션) 반영
set -e
cd "$(dirname "$0")/.."
. .venv/bin/activate
pytest -q
git push origin HEAD
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
if docker info >/dev/null 2>&1; then
  docker compose --env-file .env -f docker-compose.yml -f docker-compose.supabase.yml up -d --build web
else
  echo "docker daemon not ready; skip compose"
fi
if command -v vercel >/dev/null 2>&1; then
  vercel --prod --yes
  vercel alias set --yes vehicle-data-hub-alpha.vercel.app >/dev/null 2>&1 || true
fi
echo "ship done"
