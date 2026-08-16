#!/bin/sh
# 로컬 원클릭 배포: 테스트 → GitHub push → Supabase migrate → Docker → Vercel
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi

echo "== pytest =="
env -u DATABASE_URL -u SUPABASE_DATABASE_URL pytest -q

echo "== git push =="
git push origin HEAD

echo "== supabase migrate =="
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
export FLASK_APP="${FLASK_APP:-wsgi:app}"
if [ -n "${DATABASE_URL:-}" ]; then
  flask db upgrade
  echo "db upgrade ok"
else
  echo "DATABASE_URL missing; skip migrate"
fi

echo "== docker =="
if docker info >/dev/null 2>&1; then
  docker compose --env-file .env -f docker-compose.yml -f docker-compose.supabase.yml up -d --build web
  for i in 1 2 3 4 5 6 7 8 9 10; do
    body=$(curl -4 -sS -m 5 http://127.0.0.1:8001/healthz 2>/dev/null || true)
    echo "health $i $body"
    echo "$body" | grep -q '"status":"ok"' && break
    sleep 2
  done
else
  echo "docker daemon not ready; skip compose"
fi

echo "== vercel =="
if command -v vercel >/dev/null 2>&1; then
  vercel --prod --yes | tee /tmp/vh_ship_vercel.txt
  DEPLOY=$(grep -Eo 'https://vehicle-data-[a-z0-9]+-jeong-tai-youngs-projects\.vercel\.app' /tmp/vh_ship_vercel.txt | head -1 || true)
  if [ -n "$DEPLOY" ]; then
    vercel alias set "$DEPLOY" vehicle-data-hub-alpha.vercel.app || true
  fi
  curl -4 -sS -m 15 https://vehicle-data-hub-alpha.vercel.app/healthz || true
  echo
else
  echo "vercel cli missing; skip"
fi

echo "ship done ($ROOT)"
