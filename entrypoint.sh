#!/bin/sh
set -e

# 기동 전 점검: TRUST_PROXY=1 이어도 플레이스홀더 SECRET_KEY 로 gunicorn 이
# 바로 죽으면 nginx 는 502 만 보인다. REQUIRE_PRODUCTION_ENV=1 이면 여기서 실패.
python - <<'PY'
import os
import sys

def truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in ("1", "true", "yes")

sk = (os.environ.get("SECRET_KEY") or "").strip()
bad = (not sk) or sk in ("dev-change-me", "change-me-in-production")
if truthy("REQUIRE_PRODUCTION_ENV") and bad:
    print(
        "FATAL: REQUIRE_PRODUCTION_ENV=1 인데 SECRET_KEY 가 비어 있거나 예시값입니다. "
        ".env 의 SECRET_KEY 를 실값으로 설정하세요.",
        file=sys.stderr,
    )
    raise SystemExit(1)
if truthy("TRUST_PROXY") and bad:
    print(
        "WARNING: TRUST_PROXY=1 인데 SECRET_KEY 가 예시값/비어 있습니다. "
        "사내 서버는 REQUIRE_PRODUCTION_ENV=1 과 실 SECRET_KEY 를 권장합니다.",
        file=sys.stderr,
    )
PY

python - <<'PY'
import os
import time

import sqlalchemy as sa

url = os.environ["DATABASE_URL"]
for _ in range(60):
    try:
        with sa.create_engine(url).connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("db not ready")
PY
flask db upgrade
if [ -n "${ADMIN_USERNAME:-}" ] && [ -n "${ADMIN_PASSWORD:-}" ]; then
  flask seed-admin || echo "seed-admin skipped"
fi
# 엔카 코드가 비어 있을 때만 시드 (매 기동 전체 upsert는 gunicorn 기동을 막음)
MAKERS=$(python - <<'PY'
import os
import sqlalchemy as sa

url = os.environ["DATABASE_URL"]
with sa.create_engine(url).connect() as conn:
    print(conn.execute(sa.text("SELECT COUNT(*) FROM vehicle_maker")).scalar() or 0)
PY
)
if [ "$MAKERS" = "0" ]; then
  flask seed-encar-codes || true
fi
exec gunicorn -b 0.0.0.0:8000 -w 2 --timeout 600 "wsgi:app"
