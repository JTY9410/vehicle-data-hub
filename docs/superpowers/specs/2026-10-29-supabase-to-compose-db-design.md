# Supabase → Docker Compose 내장 DB 전환

**날짜:** 2026-10-29  
**상태:** 승인됨 (사용자: 스키마+전체 데이터, Vercel은 Mac Compose 본체·Supabase DB 연결 중단)

## 목표

운영 DB를 Supabase에서 끊고, 별도 Mac 서버의 **Docker Compose 내장 Postgres(`db`)** 로 이전한다. 스키마와 전체 데이터를 옮긴다.

## 결정

| 항목 | 선택 |
|------|------|
| 이전 범위 | 스키마 + 전체 데이터 (`vehicles`, 엔카 코드, `users`, `api_keys`, `import_jobs`, `app_settings` 등) |
| 런타임 | 기본 `docker-compose.yml`만 (`web` + `scheduler` + `db`) |
| Vercel | 배포는 유지하되 Supabase `DATABASE_URL` 제거. DB SSOT는 Mac Compose |
| 이전 방식 | `pg_dump` (Supabase) → `pg_restore --clean` (Compose `db`) |

## 비목표

- Supabase 프로젝트 삭제(대시보드에서 사용자 결정)
- Vercel을 Mac Postgres에 직접 연결
- ORM/테이블 구조 변경
- PM과 DB URL 공유

## 아키텍처

```
[크롤 API] ← scheduler/web (Compose)
                 ↓
            Postgres 17 (volume: pgdata; Supabase와 맞춤)
                 ↑
         (1회) migrate_from_supabase.sh
                 ↑
            Supabase (읽기 덤프 후 운영 중단)
```

- Compose는 `DATABASE_URL=postgresql+psycopg://vehicle:vehicle@db:5432/vehicle` 고정.
- `docker-compose.supabase.yml`은 deprecated(문서·헤더만, 운영 경로에서 제거).
- Mac 서버: 동일 레포 + `.env` + `docker compose up -d`. Postgres 포트는 외부 비공개, `8001`만 노출.

## 이전 절차 (요약)

1. Supabase URI를 `SUPABASE_DATABASE_URL`로 준비 (Direct 또는 Session, dump용).
2. `./scripts/migrate_from_supabase.sh` 실행 → `tmp/supabase_migrate/vehicle.dump`.
3. Compose `db`에 restore 후 행 수·`alembic_version` 검증.
4. `.env`의 `DATABASE_URL`을 내장 DB로. supabase overlay 없이 `docker compose up -d --build`.
5. Vercel env에서 Supabase `DATABASE_URL` 제거. GitHub Actions `supabase` migrate job 제거.
6. README를 Mac Compose 운영 중심으로 갱신.

## 성공 기준

- `docker compose`만으로 web/scheduler/db healthy.
- 내장 DB `vehicles` 등 행 수가 Supabase 덤프 시점과 일치(또는 허용 오차 문서화).
- `flask db current`가 head.
- 로컬 `/healthz` 200, 관리자 로그인·목록 조회 가능.
- CI가 Supabase에 `db upgrade`를 시도하지 않음.
- Vercel이 더 이상 Supabase URI를 갖지 않음(또는 문서상 비활성).

## 위험

- restore `--clean`이 기존 로컬 `pgdata`를 덮어씀 → 사전 안내.
- dump 중 쓰기 → 가능하면 scheduler 일시 중지 후 dump.
- Vercel은 DB 없이 API/로그인이 실패할 수 있음 → README에 Mac이 SSOT임을 명시.
