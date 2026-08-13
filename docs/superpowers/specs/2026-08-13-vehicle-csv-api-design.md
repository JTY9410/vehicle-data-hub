# Vehicle CSV → PostgreSQL API Hub — Design Spec

**Date:** 2026-08-13  
**Status:** Approved (brainstorming)  
**Stack SSOT:** `/agent.md` (Flask 3.1.x, SQLAlchemy 2.0, Flask-Migrate, Bootstrap 5.3.8, Docker Compose)

---

## 1. Goal

CSV 크롤링 매물 데이터를 필터링해 PostgreSQL에 저장하고, 관리자 UI에서 업로드·API 키를 관리하며, 타 프로그램이 API 키로 조회할 수 있는 허브를 제공한다. 완료 후 Docker Compose로 `web`+`db`를 기동하고 제공된 CSV 두 파일을 적재한다.

### Success criteria

- 관리자 로그인 후 CSV 웹 업로드 및 진행률 확인 가능
- CLI로 대용량 CSV 적재 가능
- 렌트카 번호·비정상 가격 행은 DB에 저장되지 않음
- `(site_type, site_id)` 중복 시 최근 스크래핑 데이터로 upsert
- API 키 발급 후 `X-API-Key`로 차량 목록/상세/검색 가능
- `docker compose up`으로 서비스 기동, `/healthz` 정상, 두 CSV 적재 완료

---

## 2. Architecture

```text
[Admin browser] ──► Flask web (Gunicorn)
                       ├─ Session auth + CSRF (admin UI)
                       ├─ REST API /api/v1/* (X-API-Key, read-only)
                       └─ CLI: flask import-csv
                       ▼
                 PostgreSQL 16
```

**Compose services:** `web`, `db`  
**Config SSOT:** `.env` + `config.py`  
**No separate worker** in v1 (chunked in-process import). Celery/RQ is out of scope unless load requires it later.

---

## 3. Data model

### 3.1 `users`

| Column | Notes |
|--------|--------|
| id | PK |
| username | unique |
| password_hash | scrypt |
| created_at | |

Default seed (dev): `ADMIN_USERNAME` / `ADMIN_PASSWORD` from env, fallback `wecar` / `1004wecar`.

### 3.2 `vehicles`

Stores accepted CSV rows. Price unit is **만원 (integer)**.

| Column | Source / notes |
|--------|----------------|
| id | PK (internal) |
| site_type | CSV |
| site_id | CSV; unique with site_type |
| car_no | |
| car_year | raw string OK |
| car_km | normalized integer when possible |
| car_price | integer, 만원 |
| car_maker, car_model, car_submodel, car_grade, car_subgrade | |
| car_fuel, car_mission, car_color, car_location | |
| car_import_yn, car_cc, car_type, car_seat | |
| detail_info, option_info, diag_info | JSON/text |
| url_link | |
| scraped_at | from CSV `created_at` (timezone-aware UTC) |
| created_at, updated_at | server timestamps |

**Unique constraint:** `(site_type, site_id)`  
**Indexes:** `(car_maker, car_model)`, `car_price`, `scraped_at`, `car_no` (for search)

### 3.3 `api_keys`

| Column | Notes |
|--------|--------|
| id | PK |
| name | label for admin |
| key_prefix | first 8 chars for UI display |
| key_hash | hash of full secret (never store plaintext) |
| is_active | bool |
| last_used_at | nullable |
| created_at | |

Plaintext key shown **once** at creation.

### 3.4 `import_jobs`

| Column | Notes |
|--------|--------|
| id | PK |
| source | `web` \| `cli` |
| filename | |
| status | `pending` \| `running` \| `completed` \| `failed` |
| total_rows, processed_rows, saved_rows, skipped_rows, rejected_rows | |
| error_message | nullable |
| started_at, finished_at | |

---

## 4. Import filters & upsert

Shared pipeline for web upload and CLI.

### Reject (do not store)

1. **Rental plate:** `car_no` contains any of `하`, `허`, `호`
2. **Abnormal price:** after parsing to integer 만원, `car_price <= 0` OR `car_price >= 9999`
3. **Missing keys:** empty `site_type` or `site_id`

### Price parsing

- Strip commas/spaces/`만원` suffixes; parse to int
- Unit remains **만원** in DB and API (document in API responses as `price_unit: "만원"`)
- Unparseable price → reject

### Upsert rule

- Match on `(site_type, site_id)`
- If existing row’s `scraped_at` is **older** than incoming → overwrite all mapped fields, bump `updated_at`
- If existing is **newer or equal** → count as skip (do not overwrite)

### CSV inputs (initial load)

- `/Users/USER/dev/기초테이터/20260730_크롤링데이터.csv`
- `/Users/USER/dev/기초테이터/20260813_크롤링데이터_7일분.csv`

Mounted into container (e.g. `/data/*.csv`) for CLI import after migrate/seed.

---

## 5. API (external, read-only)

Auth: header `X-API-Key: <secret>`  
Inactive/unknown key → `401`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/vehicles` | List with filters + pagination |
| GET | `/api/v1/vehicles/<id>` | Detail by internal id |
| GET | `/api/v1/vehicles/search?q=` | Search car_no / model text |

**List query params (v1):** `page`, `per_page` (cap e.g. 100), `maker`, `model`, `site_type`, `price_min`, `price_max`, `year` (substring match on `car_year` if needed)

**Response shape (list item):** core scalar fields + `price_unit: "만원"`; large JSON blobs optional via `?include=detail` or always included in detail endpoint only (list omits heavy `detail_info`/`option_info`/`diag_info` by default).

**Out of scope for v1:** write/upload API, incremental sync (`updated_since`), rate-limit UI (basic optional later).

---

## 6. Admin UI

Stack: Bootstrap 5.3.8, side nav, cards, progress (Mobbin Quicken), oklch tokens, PWA + in-app browser escape per `agent.md`.

| Screen | Actions |
|--------|---------|
| Login | session auth |
| Dashboard | vehicle count, recent import jobs |
| CSV Upload | multipart upload → import job + progress |
| API Keys | create (show once), revoke/deactivate |
| Health | `GET /healthz` (no auth) |

---

## 7. CLI

```text
flask seed-admin
flask import-csv /path/to/file.csv
```

Import creates/updates `import_jobs` and uses the same filter/upsert service as web.

---

## 8. Docker

- Multi-stage Dockerfile, base `python:3.12-slim-bookworm`, non-root user
- Gunicorn: `wsgi:app` on `0.0.0.0:8000`
- Compose: `web` + `db` (Postgres 16), named volume for PG data, bind/volume for `/data` CSV
- Startup: wait for DB → `flask db upgrade` → `flask seed-admin` → optional import
- Healthcheck: `GET /healthz`

---

## 9. Project layout (per agent.md)

```text
project-root/
├── agent.md
├── .env.example
├── config.py
├── app.py / wsgi.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── apps/
│   ├── __init__.py
│   ├── models.py
│   ├── services/import_csv.py   # SSOT filter + upsert
│   ├── routes/admin.py
│   ├── routes/api.py
│   └── auth.py
├── migrations/
├── static/ ...
├── templates/ ...
└── tests/
```

---

## 10. Testing & verification

- Unit: rental plate filter, price parse/reject, upsert newer/older
- API: 401 without key; 200 with key; filters
- Manual: compose up, import both CSVs, spot-check counts and rejected rental/9999 samples
- 3-loop review before calling done

---

## 11. Explicit non-goals (v1)

- Celery/Redis workers
- External write API
- Incremental sync API
- Price floor below 0 besides `<= 0` (no extra “too cheap” rule)
- Changing price unit to won (keep 만원)
