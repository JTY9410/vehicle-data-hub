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
flask seed-admin --force-password
flask seed-encar-codes || true
exec gunicorn -b 0.0.0.0:8000 -w 2 --timeout 600 "wsgi:app"
