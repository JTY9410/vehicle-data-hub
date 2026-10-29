# Vehicle Data Hub

Flask + PostgreSQL 매물 허브. **운영 런타임은 Docker Compose 내장 Postgres** (별도 Mac 서버 권장).

작업 전 `pro.md`를 읽는다. Hub↔PM 경계는 `docs/architecture-boundaries.md`.

## 로컬 / Mac 서버 (Docker Compose)

```bash
cp .env.example .env
# SECRET_KEY, ADMIN_*, CRAWL_API_KEY 를 채운다.
# DATABASE_URL 은 Compose가 db 서비스로 고정하므로 보통 그대로 둔다.
docker compose up -d --build
# http://127.0.0.1:8001/setup 에서 최초 관리자를 만든다 (이미 users가 있으면 생략)
```

서비스: `db`(Postgres 17) · `web`(8001→8000) · `scheduler`(크롤 증분).  
데이터 볼륨: `pgdata`. Postgres 포트는 외부에 열지 않는 것을 권장하고, `8001`만 LAN/리버스 프록시로 공개한다.

```bash
# 테스트 (SQLite, DATABASE_URL 없이)
pytest -q

# 마이그레이션 (컨테이너)
docker compose exec web flask db upgrade
docker compose exec web flask db current
```

관리자 계정은 제품에 넣지 않습니다. 빈 데이터베이스면 `/setup`에서 최초 관리자를 만들고, 이미 계정이 있으면 `.env`의 `ADMIN_USERNAME` / `ADMIN_PASSWORD`로 `flask seed-admin --force-password`만 사용하세요.

### 백업

```bash
docker compose exec -T db pg_dump -U vehicle -d vehicle -F c -f /tmp/vehicle.dump
docker compose cp db:/tmp/vehicle.dump ./tmp/vehicle-$(date +%Y%m%d).dump
```

## Supabase → 내장 DB 이전 (1회)

운영 DB는 Supabase를 쓰지 않습니다. 기존 Supabase 데이터가 있으면:

```bash
export SUPABASE_DATABASE_URL='postgresql://postgres.PROJECT:PASSWORD@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres'
./scripts/migrate_from_supabase.sh
docker compose up -d --build
```

- `docker-compose.supabase.yml` 은 **deprecated** (신규 운영 금지).
- 설계: `docs/superpowers/specs/2026-10-29-supabase-to-compose-db-design.md`

## 배포 (자동)

`main`에 push하면 GitHub Actions(`.github/workflows/ship.yml`)가 테스트 → GHCR 이미지 → Vercel 프로덕션을 시도합니다.

필요한 GitHub Secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`  
(`DATABASE_URL`로 Supabase migrate 하던 job은 제거됨. DB 마이그레이션은 Mac Compose에서 수행.)

로컬 원클릭:

```bash
./scripts/ship.sh
```

## Vercel

### 주소

**https://vehicle-data-hub-alpha.vercel.app**

- Hub **DB SSOT는 Mac Compose**입니다. Vercel에는 Supabase/`DATABASE_URL`을 두지 않습니다.
- 서버리스는 조회·관리 UI용으로만 남겨 둘 수 있으나, DB 없이 로그인·API는 실패할 수 있습니다. 운영 수집·API는 Compose `web`을 사용하세요.
- `/healthz` → `{"status":"ok"}` 이면 프로세스 기동은 정상

`https://vehicle-data-hub.vercel.app` 은 **다른 Next.js 프로젝트**라 이 앱과 무관합니다.

## API

관리자 → API 키 → API 명세서 참고. 헤더 `X-API-Key` 필요.  
Base (Compose 예): `http://<mac-host>:8001/api/v1`
