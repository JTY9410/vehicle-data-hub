# Vehicle Data Hub

Flask + PostgreSQL CSV 매물 허브. 운영 런타임은 **Docker Compose** 권장.

## 로컬 / Docker

```bash
cp .env.example .env
docker compose up -d --build
# http://127.0.0.1:8001
```

관리자 기본: `wecar` / `1004wecar`

## Vercel

**정상 접속 URL:** https://vehicle-data-hub-alpha.vercel.app/login  

주의: `https://vehicle-data-hub.vercel.app` 은 **다른 Next.js 프로젝트**가 점유 중이라 이 Flask 앱이 아닙니다(404).

Vercel은 서버리스라 **대용량 CSV 업로드·장기 DB**에는 Docker가 적합합니다.  
배포 시 `DATABASE_URL`(Supabase Session/Transaction pooler)·`SECRET_KEY` 환경변수가 필요합니다.

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
4. 필요 시 CSV 재적재로 데이터 보완  
5. Vercel·Compose 환경변수에 `DATABASE_URL`·`SECRET_KEY` 설정  

주의: ~20만 행·CSV 청크 upsert는 **Docker + Postgres(또는 Supabase Direct/Session)** 가 본체이고, Vercel은 조회 API용으로 두는 편이 안전합니다.

## API

관리자 → API 키 → API 명세서 참고. 헤더 `X-API-Key` 필요.
