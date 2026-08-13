# Vehicle CSV API Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CSV 매물을 필터·upsert 해 PostgreSQL에 저장하고, 관리자 UI·API 키·조회 API·Docker Compose 배포까지 완성한다.

**Architecture:** Flask 3.1 Application Factory + Blueprints; 적재 로직은 `apps/services/import_csv.py` SSOT; Postgres 16; 관리자는 세션+CSRF, 외부 API는 `X-API-Key` 읽기 전용.

**Tech Stack:** Python 3.12+, Flask≥3.1.3,<3.2, SQLAlchemy 2.0, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, Gunicorn, Bootstrap 5.3.8, PostgreSQL 16, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-13-vehicle-csv-api-design.md`

## Global Constraints

- Follow `agent.md` stack pins exactly (no Bootstrap 6, no Flask 2.x, SQLAlchemy 2.0 `select()`/`execute` only).
- `car_price` unit is **만원** (integer); reject if `<= 0` or `>= 9999`.
- Reject `car_no` containing `하`, `허`, or `호`.
- Upsert key: `(site_type, site_id)`; overwrite only when incoming `scraped_at` is newer.
- Secrets only in `.env`; never commit `.env` or plaintext API keys.
- Admin seed default: `wecar` / `1004wecar` (env override).
- Templates must include `[UI Flow]` comment; PWA + in-app escape required.
- Do not commit `*.csv` (gitignored).

## File map

| Path | Responsibility |
|------|----------------|
| `requirements.txt` | Pinned deps |
| `.env.example` / `config.py` | Config SSOT |
| `app.py` / `wsgi.py` | Entry / gunicorn |
| `apps/__init__.py` | `create_app`, extensions, CLI |
| `apps/extensions.py` | `db`, `migrate`, `login_manager`, `csrf` |
| `apps/models.py` | User, Vehicle, ApiKey, ImportJob |
| `apps/services/filters.py` | Plate/price parse+reject (pure) |
| `apps/services/import_csv.py` | Chunked CSV import + upsert |
| `apps/services/api_keys.py` | Generate/hash/verify keys |
| `apps/auth.py` | Login helpers / user loader |
| `apps/routes/admin.py` | Dashboard, upload, keys, login |
| `apps/routes/api.py` | `/api/v1/*` |
| `apps/routes/health.py` | `/healthz` |
| `templates/*`, `static/*` | Admin UI + PWA |
| `Dockerfile`, `docker-compose.yml`, `entrypoint.sh` | Deploy |
| `tests/*` | Unit + API tests |

---

### Task 1: Project scaffold + healthz

**Files:**
- Create: `requirements.txt`, `.env.example`, `config.py`, `app.py`, `wsgi.py`, `apps/__init__.py`, `apps/extensions.py`, `apps/routes/health.py`, `tests/conftest.py`, `tests/test_health.py`, `pyproject.toml`
- Create: `.cursorrules` (one-line pointer to agent.md) optional

**Interfaces:**
- Produces: `create_app(config_object=None) -> Flask`; route `GET /healthz` → `{"status":"ok"}`

- [ ] **Step 1: Write failing health test**

```python
# tests/conftest.py
import pytest
from apps import create_app

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with application.app_context():
        from apps.extensions import db
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
```

```python
# tests/test_health.py
def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
```

- [ ] **Step 2: Run test — expect fail**

Run: `pytest tests/test_health.py -v`  
Expected: FAIL (import/create_app missing)

- [ ] **Step 3: Implement scaffold**

`requirements.txt`:
```text
Flask>=3.1.3,<3.2
SQLAlchemy>=2.0.36,<2.1
Flask-SQLAlchemy>=3.1.1,<3.2
Flask-Migrate>=4.1,<5
Flask-Login>=0.6.3,<0.7
Flask-WTF>=1.2,<2
python-dotenv>=1.0,<2
gunicorn>=23,<25
Werkzeug>=3.1,<4
psycopg[binary]>=3.2,<4
pytest>=8,<9
```

`config.py`:
```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "wecar")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "1004wecar")
    MAX_CONTENT_LENGTH = 512 * 1024 * 1024  # 512MB uploads
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    API_PER_PAGE_MAX = 100
```

`apps/extensions.py`:
```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
```

`apps/routes/health.py`:
```python
from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)

@bp.get("/healthz")
def healthz():
    return jsonify(status="ok")
```

`apps/__init__.py`:
```python
from flask import Flask
from apps.extensions import db, migrate, login_manager, csrf

def create_app(config_object="config.Config"):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_object)
    app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)
    (app.instance_path and __import__("pathlib").Path(app.instance_path).mkdir(parents=True, exist_ok=True))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "admin.login"
    csrf.init_app(app)

    from apps.routes.health import bp as health_bp
    app.register_blueprint(health_bp)
    return app
```

`app.py`:
```python
from apps import create_app
app = create_app()
```

`wsgi.py`:
```python
from apps import create_app
app = create_app()
```

`.env.example`:
```text
SECRET_KEY=change-me
DATABASE_URL=postgresql+psycopg://vehicle:vehicle@db:5432/vehicle
ADMIN_USERNAME=wecar
ADMIN_PASSWORD=1004wecar
```

- [ ] **Step 4: Run test — expect pass**

Run: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && pytest tests/test_health.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example config.py app.py wsgi.py apps tests pyproject.toml
git commit -m "chore: scaffold Flask app with healthz"
```

---

### Task 2: Models + migration path

**Files:**
- Create: `apps/models.py`, `tests/test_models.py`
- Modify: `apps/__init__.py` (import models)
- Create: `migrations/` via `flask db init` + migrate

**Interfaces:**
- Produces: `User`, `Vehicle`, `ApiKey`, `ImportJob` mapped classes
- Unique: `Vehicle(site_type, site_id)`

- [ ] **Step 1: Write failing model test**

```python
# tests/test_models.py
from apps.extensions import db
from apps.models import Vehicle

def test_vehicle_unique_site(app):
    with app.app_context():
        v1 = Vehicle(site_type="encar", site_id="1", car_no="12가3456", car_price=1000)
        v2 = Vehicle(site_type="encar", site_id="1", car_no="12가3457", car_price=2000)
        db.session.add(v1)
        db.session.commit()
        db.session.add(v2)
        try:
            db.session.commit()
            raised = False
        except Exception:
            db.session.rollback()
            raised = True
        assert raised
```

- [ ] **Step 2: Run — expect fail** (models missing)

- [ ] **Step 3: Implement models**

```python
# apps/models.py
from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import String, Text, Integer, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from apps.extensions import db

def utcnow():
    return datetime.now(timezone.utc)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Vehicle(db.Model):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("site_type", "site_id", name="uq_vehicle_site"),
        Index("ix_vehicle_maker_model", "car_maker", "car_model"),
        Index("ix_vehicle_price", "car_price"),
        Index("ix_vehicle_scraped_at", "scraped_at"),
        Index("ix_vehicle_car_no", "car_no"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    site_type: Mapped[str] = mapped_column(String(32), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    car_no: Mapped[str | None] = mapped_column(String(32))
    car_year: Mapped[str | None] = mapped_column(String(64))
    car_km: Mapped[int | None] = mapped_column(Integer)
    car_price: Mapped[int | None] = mapped_column(Integer)  # 만원
    car_maker: Mapped[str | None] = mapped_column(String(64))
    car_model: Mapped[str | None] = mapped_column(String(128))
    car_submodel: Mapped[str | None] = mapped_column(String(128))
    car_grade: Mapped[str | None] = mapped_column(String(128))
    car_subgrade: Mapped[str | None] = mapped_column(String(128))
    car_fuel: Mapped[str | None] = mapped_column(String(32))
    car_mission: Mapped[str | None] = mapped_column(String(32))
    car_color: Mapped[str | None] = mapped_column(String(32))
    car_location: Mapped[str | None] = mapped_column(String(64))
    car_import_yn: Mapped[str | None] = mapped_column(String(8))
    car_cc: Mapped[str | None] = mapped_column(String(32))
    car_type: Mapped[str | None] = mapped_column(String(64))
    car_seat: Mapped[str | None] = mapped_column(String(32))
    detail_info: Mapped[str | None] = mapped_column(Text)
    option_info: Mapped[str | None] = mapped_column(Text)
    diag_info: Mapped[str | None] = mapped_column(Text)
    url_link: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class ApiKey(db.Model):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ImportJob(db.Model):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # web|cli
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    saved_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Import models in `create_app` before migrate. Run:

```bash
export FLASK_APP=app:app
flask db init
flask db migrate -m "initial users vehicles api_keys import_jobs"
```

For tests keep `db.create_all()` in conftest.

- [ ] **Step 4: pytest tests/test_models.py -v** — PASS

- [ ] **Step 5: Commit**

```bash
git add apps/models.py migrations tests/test_models.py apps/__init__.py
git commit -m "feat: add User Vehicle ApiKey ImportJob models"
```

---

### Task 3: Filter helpers (TDD)

**Files:**
- Create: `apps/services/__init__.py`, `apps/services/filters.py`, `tests/test_filters.py`

**Interfaces:**
- Produces:
  - `is_rental_plate(car_no: str | None) -> bool`
  - `parse_price_manwon(raw: str | int | None) -> int | None`
  - `is_abnormal_price(price: int | None) -> bool`  # True if reject
  - `parse_km(raw: str | int | None) -> int | None`
  - `should_reject_row(car_no, car_price_raw, site_type, site_id) -> tuple[bool, str | None]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_filters.py
from apps.services.filters import (
    is_rental_plate, parse_price_manwon, is_abnormal_price, should_reject_row
)

def test_rental_ha_heo_ho():
    assert is_rental_plate("12하3456")
    assert is_rental_plate("88허1234")
    assert is_rental_plate("01호9999")
    assert not is_rental_plate("12가3456")
    assert not is_rental_plate(None)

def test_price_parse_and_reject():
    assert parse_price_manwon("1,740") == 1740
    assert parse_price_manwon(3250) == 3250
    assert is_abnormal_price(0)
    assert is_abnormal_price(-1)
    assert is_abnormal_price(9999)
    assert is_abnormal_price(10000)
    assert not is_abnormal_price(9998)
    assert not is_abnormal_price(1)

def test_should_reject():
    assert should_reject_row("12하1111", "1000", "encar", "1")[0]
    assert should_reject_row("12가1111", "9999", "encar", "1")[0]
    assert should_reject_row("12가1111", "1000", "", "1")[0]
    ok, reason = should_reject_row("12가1111", "1000", "encar", "1")
    assert ok is False and reason is None
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

```python
# apps/services/filters.py
import re

RENTAL_CHARS = ("하", "허", "호")

def is_rental_plate(car_no: str | None) -> bool:
    if not car_no:
        return False
    return any(ch in car_no for ch in RENTAL_CHARS)

def parse_price_manwon(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().replace(",", "").replace(" ", "").replace("만원", "")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None

def is_abnormal_price(price: int | None) -> bool:
    if price is None:
        return True
    return price <= 0 or price >= 9999

def parse_km(raw: str | int | None) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw).strip().replace(",", "").replace("km", "").replace("KM", "").replace(" ", "")
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None

def should_reject_row(car_no, car_price_raw, site_type, site_id) -> tuple[bool, str | None]:
    if not site_type or not site_id:
        return True, "missing_site_key"
    if is_rental_plate(car_no):
        return True, "rental_plate"
    price = parse_price_manwon(car_price_raw)
    if is_abnormal_price(price):
        return True, "abnormal_price"
    return False, None
```

- [ ] **Step 4: pytest tests/test_filters.py -v** — PASS

- [ ] **Step 5: Commit** `feat: add rental/price import filters`

---

### Task 4: Import service + upsert

**Files:**
- Create: `apps/services/import_csv.py`, `tests/test_import_csv.py`, `tests/fixtures/sample.csv`

**Interfaces:**
- Consumes: filters + `Vehicle`, `ImportJob`, `db`
- Produces: `import_csv_file(path: str | Path, source: str, filename: str | None = None) -> ImportJob`
- Upsert: overwrite only if incoming `scraped_at` > existing `scraped_at` (None treated as oldest)

- [ ] **Step 1: Fixture + failing tests**

`tests/fixtures/sample.csv` (header matching production + 4 rows):
1. normal keep  
2. rental `하` reject  
3. price 9999 reject  
4. same site newer price overwrite  

```python
# tests/test_import_csv.py
from pathlib import Path
from apps.services.import_csv import import_csv_file
from apps.models import Vehicle
from apps.extensions import db

FIXTURE = Path(__file__).parent / "fixtures" / "sample.csv"

def test_import_filters_and_upsert(app):
    with app.app_context():
        job = import_csv_file(FIXTURE, source="cli")
        assert job.status == "completed"
        assert job.saved_rows >= 1
        assert job.rejected_rows >= 2
        cars = db.session.execute(db.select(Vehicle)).scalars().all()
        assert all("하" not in (c.car_no or "") for c in cars)
        assert all(c.car_price is not None and 0 < c.car_price < 9999 for c in cars)
```

Include two rows same `site_type`/`site_id` with different `created_at` and assert final `car_price` is the newer one.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `import_csv_file`**

Use Python `csv` module, `DictReader`, chunk commit every 500 rows. Map columns from CSV header. Parse `created_at` with `datetime.fromisoformat` fallback. On conflict select existing by site keys; compare `scraped_at`; update fields or skip. Update `ImportJob` counters. Never store rejected rows.

Pseudo-core (full implementation in code):

```python
def import_csv_file(path, source, filename=None) -> ImportJob:
    job = ImportJob(source=source, filename=filename or Path(path).name, status="running", started_at=utcnow())
    db.session.add(job)
    db.session.commit()
    # open csv, for each row:
    #   reject via should_reject_row → rejected_rows++
    #   else upsert → saved or skipped
    #   processed_rows++; periodic commit + job progress
    job.status = "completed"
    job.finished_at = utcnow()
    db.session.commit()
    return job
```

Handle multiline JSON fields in CSV carefully — use stdlib csv which handles quoted newlines.

- [ ] **Step 4: pytest tests/test_import_csv.py -v** — PASS

- [ ] **Step 5: Commit** `feat: chunked CSV import with upsert`

---

### Task 5: Auth, seed-admin, API key service

**Files:**
- Create: `apps/auth.py`, `apps/services/api_keys.py`, `apps/cli.py`
- Modify: `apps/__init__.py` register CLI + user_loader
- Test: `tests/test_api_keys.py`, `tests/test_auth_seed.py`

**Interfaces:**
- `create_api_key(name: str) -> tuple[ApiKey, str]`  # returns plaintext once
- `verify_api_key(raw: str) -> ApiKey | None`
- CLI: `flask seed-admin`, `flask import-csv PATH`

- [ ] **Step 1: Tests**

```python
def test_api_key_roundtrip(app):
    with app.app_context():
        from apps.services.api_keys import create_api_key, verify_api_key
        row, raw = create_api_key("partner")
        assert raw.startswith(row.key_prefix) or row.key_prefix in raw
        assert verify_api_key(raw) is not None
        assert verify_api_key("bogus") is None

def test_seed_admin(app):
    with app.app_context():
        from apps.cli import seed_admin_user
        from apps.models import User
        seed_admin_user()
        u = db.session.execute(db.select(User).filter_by(username="wecar")).scalar_one()
        assert u.password_hash
```

- [ ] **Step 2–4: Implement with Werkzeug `generate_password_hash(..., method="scrypt")` and `check_password_hash`; API keys `secrets.token_urlsafe(32)`, store `hashlib.sha256(raw.encode()).hexdigest()`**

Register:

```python
@app.cli.command("seed-admin")
def seed_admin():
    ...

@app.cli.command("import-csv")
@click.argument("path")
def import_csv_cmd(path):
    import_csv_file(path, source="cli")
```

- [ ] **Step 5: Commit** `feat: admin seed and API key hashing`

---

### Task 6: Admin routes + templates (login, dashboard, upload, keys)

**Files:**
- Create: `apps/routes/admin.py`
- Create: `templates/base.html`, `login.html`, `dashboard.html`, `upload.html`, `api_keys.html`
- Create: `static/css/style.css`, `static/js/app.js`, `static/js/sw-register.js`, `static/manifest.json`, `static/service-worker.js`, `static/icons/` (simple SVG/PNG placeholders)
- Modify: `apps/__init__.py` register admin bp; exempt API from CSRF later
- Test: `tests/test_admin.py` (login + upload small fixture)

**Interfaces:**
- `POST /login`, `POST /logout`, `GET /`, `GET|POST /upload`, `GET /upload/<job_id>/status` JSON, `GET|POST /api-keys`, `POST /api-keys/<id>/revoke`

- [ ] **Step 1: Test login required and upload creates job**

```python
def test_dashboard_requires_login(client):
    assert client.get("/").status_code in (302, 401)

def test_login_and_upload(client, app):
    # seed admin first
    r = client.post("/login", data={"username": "wecar", "password": "1004wecar"}, follow_redirects=True)
    assert r.status_code == 200
    data = {"file": (open(FIXTURE, "rb"), "sample.csv")}
    r = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
```

- [ ] **Step 2–4: Implement Mobbin Quicken layout** — side nav, glass cards, progress bar for job counters; `[UI Flow]` comments; Bootstrap 5.3.8 CDN; Pretendard; oklch tokens from agent.md; PWA manifest + SW + Kakao/Naver escape in `app.js`.

Upload handler: save to `UPLOAD_FOLDER`, call `import_csv_file` (sync in v1), show result counts.

API keys page: form name → create → flash plaintext once; list with revoke.

- [ ] **Step 5: Commit** `feat: admin UI for upload and API keys`

---

### Task 7: External read API

**Files:**
- Create: `apps/routes/api.py`, `tests/test_api.py`
- Modify: `apps/__init__.py` — register api bp; `csrf.exempt(api_bp)`

**Interfaces:**
- `GET /api/v1/vehicles`
- `GET /api/v1/vehicles/<int:id>`
- `GET /api/v1/vehicles/search?q=`
- Auth decorator reads `X-API-Key`, calls `verify_api_key`, updates `last_used_at`

- [ ] **Step 1: Tests**

```python
def test_api_unauthorized(client):
    assert client.get("/api/v1/vehicles").status_code == 401

def test_api_list_and_detail(client, app):
    with app.app_context():
        _, raw = create_api_key("t")
        # insert one vehicle...
    r = client.get("/api/v1/vehicles", headers={"X-API-Key": raw})
    assert r.status_code == 200
    body = r.get_json()
    assert "items" in body and body.get("price_unit") == "만원"
```

List JSON omit heavy `detail_info`/`option_info`/`diag_info`; detail includes them. Pagination `page`/`per_page` capped by `API_PER_PAGE_MAX`.

- [ ] **Step 2–4: Implement**

- [ ] **Step 5: Commit** `feat: read-only vehicles API with API keys`

---

### Task 8: Docker Compose + entrypoint

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `.dockerignore`
- Modify: `.env` locally (not committed) from `.env.example`

**Interfaces:**
- Services: `db` (postgres:16-alpine), `web` (build .)
- Volumes: `pgdata`, `./uploads`, mount host CSV dir to `/data:ro`
- Entrypoint: wait for Postgres → `flask db upgrade` → `flask seed-admin` → exec gunicorn

- [ ] **Step 1: Write Dockerfile multi-stage**

```dockerfile
FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim-bookworm
RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN mkdir -p /app/uploads /app/instance && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
```

`entrypoint.sh` (executable):
```bash
#!/bin/sh
set -e
python - <<'PY'
import time, os
import sqlalchemy as sa
url = os.environ["DATABASE_URL"]
for i in range(60):
    try:
        sa.create_engine(url).connect().close()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("db not ready")
PY
flask db upgrade
flask seed-admin
exec gunicorn -b 0.0.0.0:8000 -w 2 --timeout 600 "wsgi:app"
```

`docker-compose.yml`:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: vehicle
      POSTGRES_PASSWORD: vehicle
      POSTGRES_DB: vehicle
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vehicle -d vehicle"]
      interval: 5s
      timeout: 5s
      retries: 10
  web:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg://vehicle:vehicle@db:5432/vehicle
    volumes:
      - ./uploads:/app/uploads
      - .:/data:ro
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]
      interval: 10s
      timeout: 5s
      retries: 10
volumes:
  pgdata:
```

- [ ] **Step 2: Build & up**

```bash
cp .env.example .env
# set SECRET_KEY
docker compose build
docker compose up -d
curl -s http://127.0.0.1:8000/healthz
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: Commit** `chore: add Docker Compose stack`

---

### Task 9: Load production CSVs + smoke verify

**Files:** none new (ops)

- [ ] **Step 1: Import both files inside web container**

```bash
docker compose exec web flask import-csv "/data/20260813_크롤링데이터_7일분.csv"
docker compose exec web flask import-csv "/data/20260730_크롤링데이터.csv"
```

Note: large file may take long; gunicorn timeout is for HTTP — CLI runs in exec so OK. Ensure import uses efficient commits.

- [ ] **Step 2: Verify**

```bash
docker compose exec db psql -U vehicle -d vehicle -c "SELECT COUNT(*) FROM vehicles;"
docker compose exec db psql -U vehicle -d vehicle -c "SELECT COUNT(*) FROM vehicles WHERE car_no ~ '[하허호]';"
# expect 0 rental
docker compose exec db psql -U vehicle -d vehicle -c "SELECT COUNT(*) FROM vehicles WHERE car_price <= 0 OR car_price >= 9999;"
# expect 0
```

Create API key via admin UI (http://localhost:8000) login `wecar` / `1004wecar`, then:

```bash
curl -s -H "X-API-Key: $KEY" "http://127.0.0.1:8000/api/v1/vehicles?per_page=2"
```

- [ ] **Step 3: Run full pytest on host**

```bash
pytest -v
```

- [ ] **Step 4: 3-loop self-review** (agent.md) — filters, upsert, API auth, docker health

- [ ] **Step 5: Commit any fixes** `fix: post-load smoke adjustments` if needed

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Postgres + Compose web/db | 8 |
| Users / Vehicles / ApiKeys / ImportJobs | 2 |
| Rental + price filters | 3 |
| Upsert by site + newer scraped_at | 4 |
| Web upload + CLI | 6, 5, 9 |
| API list/detail/search + keys | 5, 7 |
| Admin UI Quicken + PWA | 6 |
| healthz / seed / gunicorn | 1, 5, 8 |
| Load two CSVs | 9 |
| Read-only API (no write API) | 7 |
| Price unit 만원 documented | 7 |

## Self-review notes

- No incremental sync / Celery (explicit non-goals).
- `csrf.exempt` only on API blueprint.
- Large CSV: chunk commits; CLI preferred for initial load.
- SQLite in pytest; Postgres in Docker — keep SQLAlchemy portable (no PG-only upsert syntax required; select+update is fine).
