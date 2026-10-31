#!/usr/bin/env bash
# Supabase Postgres → Docker Compose 내장 db 이전 (schema + data)
# 사용:
#   export SUPABASE_DATABASE_URL='postgresql://postgres.PROJECT:PASSWORD@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres'
#   ./scripts/migrate_from_supabase.sh
#
# 컷오버: 이 스크립트 실행 직전부터 Supabase(구 Hub DB) 쓰기를 중단할 것.
# Direct(db.*.supabase.co)도 가능. Session pooler(5432) 권장.
# 덤프(tmp/)는 개인정보 포함 가능 — 레포 커밋 금지.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP_DIR="${ROOT}/tmp/supabase_migrate"
DUMP_FILE="${DUMP_DIR}/vehicle.dump"
COMPOSE=(docker compose -f "${ROOT}/docker-compose.yml")
PG_IMAGE="${PG_DUMP_IMAGE:-postgres:17-alpine}"

mkdir -p "$DUMP_DIR"

if [[ -z "${SUPABASE_DATABASE_URL:-}" ]]; then
  echo "SUPABASE_DATABASE_URL 이 필요합니다."
  echo "Supabase → Project Settings → Database → URI (Session/Direct) 를 넣으세요."
  exit 1
fi

# SQLAlchemy 드라이버 접두사 제거 + 호스트만 표시 (비밀번호 미출력)
eval "$(
  SUPABASE_DATABASE_URL="$SUPABASE_DATABASE_URL" python3 <<'PY'
import os
from urllib.parse import urlparse
raw = os.environ["SUPABASE_DATABASE_URL"].strip()
if raw.startswith("postgresql+psycopg://"):
    raw = "postgresql://" + raw[len("postgresql+psycopg://"):]
elif raw.startswith("postgres://"):
    raw = "postgresql://" + raw[len("postgres://"):]
u = urlparse(raw)
host = u.hostname or "(unknown)"
port = u.port or "-"
# shell-escape PG_URL via %q equivalent: single-quote
def sh_single(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"
print(f"PG_URL={sh_single(raw)}")
print(f"HOST_ONLY={sh_single(f'{host} port={port}')}")
PY
)"
echo "==> Supabase dump source: ${HOST_ONLY}"

echo "==> 1) Supabase public 스키마 덤프 (schema+data)"
# URL은 환경변수로만 전달 (argv에 비밀번호 노출 방지)
docker run --rm \
  -e "PGSSLMODE=require" \
  -e "DATABASE_URL=${PG_URL}" \
  "$PG_IMAGE" \
  sh -c 'pg_dump "$DATABASE_URL" --schema=public --no-owner --no-acl -F c' \
  > "$DUMP_FILE"

if [[ ! -s "$DUMP_FILE" ]]; then
  echo "덤프 파일이 비어 있습니다: $DUMP_FILE"
  exit 1
fi
echo "    dump size: $(wc -c < "$DUMP_FILE") bytes"

echo "==> 2) Compose 내장 db 기동"
"${COMPOSE[@]}" up -d db
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T db pg_isready -U vehicle -d vehicle >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
"${COMPOSE[@]}" exec -T db pg_isready -U vehicle -d vehicle

DB_CID="$("${COMPOSE[@]}" ps -q db)"
if [[ -z "$DB_CID" ]]; then
  echo "db 컨테이너를 찾을 수 없습니다."
  exit 1
fi

echo "==> 3) 내장 db에 복원 (--clean)"
docker cp "$DUMP_FILE" "${DB_CID}:/tmp/vehicle.dump"
set +e
"${COMPOSE[@]}" exec -T db \
  pg_restore --clean --if-exists --no-owner --no-acl \
    -U vehicle -d vehicle /tmp/vehicle.dump
RESTORE_RC=$?
set -e
# pg_restore는 extension/comment 경고로 1을 반환하는 경우가 많음
if [[ "$RESTORE_RC" -gt 1 ]]; then
  echo "pg_restore 실패 (exit=${RESTORE_RC})"
  exit "$RESTORE_RC"
fi

echo "==> 4) 행 수·alembic 확인"
"${COMPOSE[@]}" exec -T db psql -U vehicle -d vehicle -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'vehicles' AS t, COUNT(*)::bigint AS n FROM vehicles
UNION ALL SELECT 'vehicle_maker', COUNT(*) FROM vehicle_maker
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'api_keys', COUNT(*) FROM api_keys
UNION ALL SELECT 'import_jobs', COUNT(*) FROM import_jobs
ORDER BY 1;
SELECT version_num FROM alembic_version;
SQL

echo "완료. supabase overlay 없이 기동하세요:"
echo "  docker compose -f docker-compose.yml up -d --build"
echo "  (.env DATABASE_URL 은 postgresql+psycopg://vehicle:vehicle@db:5432/vehicle )"
