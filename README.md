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

Vercel은 서버리스라 **대용량 CSV 업로드·장기 DB**에는 Docker가 적합합니다.  
Vercel 배포 시 반드시 원격 Postgres `DATABASE_URL` 과 `SECRET_KEY` 를 프로젝트 Environment Variables에 설정하세요.

```bash
vercel --prod
```

## Supabase (선택 · 검토)

앱은 이미 `DATABASE_URL`로 Postgres에 붙습니다. Supabase는 호환 Postgres이므로 **스키마/ORM 변경 없이** URI만 교체해 쓸 수 있습니다.

권장 구성:

| 환경 | 연결 | 비고 |
|------|------|------|
| Docker Compose `web` | Session pooler 또는 Direct (`db.*.supabase.co:5432`) | 대용량 CSV 적재·배치 remap |
| Vercel 서버리스 | Transaction pooler (`:6543`, `?pgbouncer=true`) | 커넥션 수 제한 대응 |
| 로컬 개발 | 기존 Compose Postgres 유지 | 비용·지연 최소화 |

체크리스트:

1. Supabase 프로젝트에서 Database → Connection string 복사  
2. `postgresql://...` → 앱이 `postgresql+psycopg://`로 정규화 (`config.py`)  
3. `flask db upgrade`로 마이그레이션 적용  
4. 필요 시 `pg_dump`/`pg_restore` 또는 CSV 재적재로 데이터 이전  
5. Vercel·Compose 환경변수에 `DATABASE_URL`·`SECRET_KEY` 설정  

주의: ~20만 행·CSV 청크 upsert는 **Docker + Postgres(또는 Supabase Direct/Session)** 가 본체이고, Vercel은 조회 API용으로 두는 편이 안전합니다.  
현재 MCP로 연결된 Supabase 프로젝트(`zlotlpcgormyykllries`)는 존재하나, **자동 이전은 아직 하지 않았습니다.** 이전을 진행하려면 승인해 주세요.

## API

관리자 → API 키 → API 명세서 참고. 헤더 `X-API-Key` 필요.
