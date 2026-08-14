#!/usr/bin/env bash
# 로컬 Compose Postgres → Supabase 이전
# 사용:
#   export SUPABASE_DATABASE_URL='postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres'
#   ./scripts/migrate_to_supabase.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP_DIR="${ROOT}/tmp/supabase_migrate"
mkdir -p "$DUMP_DIR"

if [[ -z "${SUPABASE_DATABASE_URL:-}" ]]; then
  echo "SUPABASE_DATABASE_URL 이 필요합니다."
  echo "Supabase → Project Settings → Database → URI (Session/Direct) 를 넣으세요."
  exit 1
fi

# SQLAlchemy 드라이버 접두사 제거 (pg_dump/psql용)
PG_URL="${SUPABASE_DATABASE_URL/postgresql+psycopg:\/\//postgresql:\/\/}"
PG_URL="${PG_URL/postgres:\/\//postgresql:\/\/}"

echo "==> 1) 로컬 DB 덤프 (schema+data)"
docker compose -f "$ROOT/docker-compose.yml" --profile local-db exec -T db \
  pg_dump -U vehicle -d vehicle --no-owner --no-acl -F c \
  > "$DUMP_DIR/vehicle.dump"

echo "==> 2) Supabase에 스키마·데이터 복원"
pg_restore --clean --if-exists --no-owner --no-acl -d "$PG_URL" "$DUMP_DIR/vehicle.dump" \
  || psql "$PG_URL" -c "SELECT 1" >/dev/null

echo "==> 3) 행 수 확인"
psql "$PG_URL" -c "SELECT 'vehicles' AS t, COUNT(*) FROM vehicles UNION ALL SELECT 'vehicle_maker', COUNT(*) FROM vehicle_maker;"

echo "완료. .env 의 DATABASE_URL 을 Supabase URI(postgresql+psycopg://...) 로 바꾼 뒤:"
echo "  docker compose up -d --build"
echo "로컬 Postgres는: docker compose --profile local-db up -d"
