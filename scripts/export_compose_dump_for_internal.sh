#!/usr/bin/env bash
# 사내 이전용: Compose 내장 db → tmp/ 에 fresh pg_dump (커밋 금지)
# 사용: ./scripts/export_compose_dump_for_internal.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=(docker compose -f "${ROOT}/docker-compose.yml")
OUT_DIR="${ROOT}/tmp/internal_migrate"
STAMP="$(date +%Y%m%d-%H%M%S)"
DUMP="${OUT_DIR}/vehicle-${STAMP}.dump"
META="${OUT_DIR}/vehicle-${STAMP}.meta.txt"

mkdir -p "$OUT_DIR"
"${COMPOSE[@]}" up -d db
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T db pg_isready -U vehicle -d vehicle >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
"${COMPOSE[@]}" exec -T db pg_isready -U vehicle -d vehicle

echo "==> pg_dump -> ${DUMP}"
"${COMPOSE[@]}" exec -T db \
  pg_dump -U vehicle -d vehicle --schema=public --no-owner --no-acl -F c \
  > "$DUMP"

{
  echo "created_at_kst=$(TZ=Asia/Seoul date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "commit=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "dump_bytes=$(wc -c < "$DUMP" | tr -d ' ')"
  echo "dump_file=$(basename "$DUMP")"
  echo "--- counts ---"
  "${COMPOSE[@]}" exec -T db psql -U vehicle -d vehicle -At -c "
SELECT 'vehicles='||COUNT(*) FROM vehicles
UNION ALL SELECT 'vehicle_maker='||COUNT(*) FROM vehicle_maker
UNION ALL SELECT 'users='||COUNT(*) FROM users
UNION ALL SELECT 'api_keys='||COUNT(*) FROM api_keys
UNION ALL SELECT 'import_jobs='||COUNT(*) FROM import_jobs;
SELECT 'alembic='||version_num FROM alembic_version;
"
} | tee "$META"

echo
echo "완료. 덤프와 meta 를 보안 채널로만 전달하세요. 레포에 커밋하지 마세요."
echo "  dump: $DUMP"
echo "  meta: $META"
