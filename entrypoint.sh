#!/bin/sh
set -e
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
flask seed-admin
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
