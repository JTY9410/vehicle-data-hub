# Vehicle Data Hub

Flask + PostgreSQL 매물 허브. 운영 런타임은 **Docker Compose** 권장.

작업 전 `pro.md`를 읽는다. 실행·설정·마이그레이션·테스트는 아래를 따른다.

## 로컬 / Docker

```bash
cp .env.example .env
# SECRET_KEY, DATABASE_URL 을 채운다. 관리자 비밀번호는 저장소 기본값이 없다.
docker compose up -d --build
# http://127.0.0.1:8001/setup 에서 최초 관리자를 만든다
```

```bash
# 테스트 (SQLite, DATABASE_URL 없이)
pytest -q

# 마이그레이션
export FLASK_APP=wsgi:app
flask db migrate -m "reason"
flask db upgrade
```

관리자 계정은 제품에 넣지 않습니다. 빈 데이터베이스면 `/setup`에서 최초 관리자를 만들고, 이미 계정이 있으면 `.env`의 `ADMIN_USERNAME` / `ADMIN_PASSWORD`로 `flask seed-admin --force-password`만 사용하세요.

## 배포 (자동)

`main`에 push하면 GitHub Actions(`.github/workflows/ship.yml`)가 테스트 → Docker 이미지 빌드 → Supabase `flask db upgrade` → Vercel 프로덕션을 시도합니다.

필요한 GitHub Secrets: `DATABASE_URL`, `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`

로컬 원클릭:

```bash
./scripts/ship.sh
```

## Vercel

### 반드시 이 주소로 접속하세요

**https://vehicle-data-hub-alpha.vercel.app/login**

- 계정은 저장소에 없습니다. 운영 담당자가 개별 전달한 아이디/비밀번호를 사용하세요.
- `/healthz` → `{"status":"ok"}` 이면 정상

### 잘못된 주소 (404 나는 곳)

`https://vehicle-data-hub.vercel.app` 은 **다른 Next.js 프로젝트**(“Vehicle Data Info”)가 사용 중입니다.  
이 Flask 앱이 아니므로 `/login`, `/vehicles` 에서 404가 납니다.

짧은 도메인(`vehicle-data-hub.vercel.app`)을 이 앱에 쓰려면 Vercel 대시보드에서 해당 Next.js 프로젝트를 삭제하거나 도메인을 해제한 뒤, 이 프로젝트에 도메인을 다시 연결해야 합니다.

Vercel은 서버리스라 **전량 크롤 동기화**는 Docker가 적합합니다.  
환경변수: `DATABASE_URL`(Supabase pooler), `SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `CRAWL_API_KEY`

## Supabase (선택 · 검토)

앱은 이미 `DATABASE_URL`로 Postgres에 붙습니다. Supabase는 호환 Postgres이므로 **스키마/ORM 변경 없이** URI만 교체해 쓸 수 있습니다.

권장 구성:

| 환경 | 연결 | 비고 |
|------|------|------|
| Docker Compose `web` | Session pooler 또는 Direct (`db.*.supabase.co:5432`) | 대용량 CSV 적재·배치 remap |
| Vercel 서버리스 | Transaction pooler (`:6543`, `?pgbouncer=true`) | 커넥션 수 제한 대응 |
| 로컬 개발 | 기존 Compose Postgres 유지 | 비용·지연 최소화 |

### 이전 절차

1. Supabase Dashboard → **Project Settings → Database** → Connection string (URI) 복사 (비밀번호 포함)
2. 로컬 덤프·복원:
   ```bash
   export SUPABASE_DATABASE_URL='postgresql://postgres:YOUR_PASSWORD@db.PROJECT.supabase.co:5432/postgres'
   ./scripts/migrate_to_supabase.sh
   ```
3. `.env`의 `DATABASE_URL`을 `postgresql+psycopg://...` 형태로 설정
4. Supabase만으로 기동:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.supabase.yml up -d --build
   ```
5. Vercel Environment Variables에 동일 `DATABASE_URL`·`SECRET_KEY` 설정

체크리스트:

1. Supabase 프로젝트에서 Database → Connection string 복사  
2. `postgresql://...` → 앱이 `postgresql+psycopg://`로 정규화 (`config.py`)  
3. `flask db upgrade`로 마이그레이션 적용 (또는 `migrate_to_supabase.sh`)  
4. 필요 시 `flask import-crawl`로 데이터 재적재  
5. Vercel·Compose 환경변수에 `DATABASE_URL`·`SECRET_KEY` 설정  

주의: ~20만 행·CSV 청크 upsert는 **Docker + Postgres(또는 Supabase Direct/Session)** 가 본체이고, Vercel은 조회 API용으로 두는 편이 안전합니다.

## API

관리자 → API 키 → API 명세서 참고. 헤더 `X-API-Key` 필요.
