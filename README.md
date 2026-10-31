# Vehicle Data Hub

Flask + PostgreSQL 매물 허브. **운영 SSOT = Mac 서버 Docker Compose 내장 Postgres.**  
Vercel·Supabase 런타임은 사용하지 않는다.

Hub↔PM 경계: `docs/architecture-boundaries.md`.

## Mac 서버 (운영)

- nginx(https) → `127.0.0.1:${WEB_PORT}` → 컨테이너. 앱 포트는 루프백만 바인딩.
- 레포 `docker-compose.yml` + 서버 `docker-compose.override.yml` + 서버 `.env`.
- push → 웹훅 pull·배포. 시크릿은 서버 `.env`에만 (커밋 금지).

```bash
cp .env.example .env   # SECRET_KEY, CRAWL_API_* 등 채움
docker compose up -d --build
# 스케줄러(매일 00:00 KST 증분)는 메모리 제약으로 수동:
docker compose --profile scheduler up -d
```

기본 바인딩: `127.0.0.1:8010` (`WEB_BIND` / `WEB_PORT`).  
`TRUST_PROXY` 기본 `1` (nginx 뒤 https·Secure 쿠키).

공개 API base: `https://vdh.wecarmobility.co.kr/api/v1`  
인증: 관리자 → API 키 화면에서 발급한 값을 `X-API-Key`로 전달.  
PM은 그 키를 `VEHICLE_DATA_HUB_API_KEY`에 넣는다.  
`VEHICLE_DATA_HUB_BASE_URL`은 `https://vdh.wecarmobility.co.kr/api/v1` 이다. PM 클라이언트가 이 주소 뒤에 `/vehicles`를 붙이므로 호스트만 넣으면 경로가 어긋난다.

서비스: `db`(Postgres **17**, 볼륨 **`pgdata`**) · `web` · `scheduler`(profile).

### Postgres 메이저 / 볼륨 변경

`pgdata` 이름이나 Postgres 메이저 버전을 바꾸면 기존 데이터를 읽지 못한다. 변경 시:

```bash
docker compose exec -T db pg_dump -U vehicle -d vehicle -F c -f /tmp/vehicle.dump
docker compose cp db:/tmp/vehicle.dump ./tmp/vehicle-backup.dump
# 이미지/볼륨 변경 후 db 기동
docker compose up -d db
docker compose cp ./tmp/vehicle-backup.dump db:/tmp/vehicle.dump
docker compose exec -T db pg_restore --clean --if-exists --no-owner --no-acl -U vehicle -d vehicle /tmp/vehicle.dump
```

덤프에 개인정보·키가 포함될 수 있다. **레포에 커밋하지 말고** 별도 채널로만 전달.

### 스케줄러·메모리

| 항목 | 대략 |
|------|------|
| DB 매물 규모 (이전 기준) | ~11만 행 (`vehicles`) |
| 일일 증분 1회 | 보통 수백~2,000행/요청 (API limit 최대 2,000) |
| 첫 전체 이전(dump→restore) | 덤프 ~20MB급, restore 수 분 |
| `web` (gunicorn -w 2) | 피크 대략 **300–600MB** |
| `scheduler` 수집 중 | 피크 대략 **200–500MB** (페이지 버퍼·upsert) |
| `db` | 데이터·캐시에 따라 **0.5–2GB+** |

서버 메모리 여유가 적을 때는 `web`+`db`만 상시 기동하고, 수집이 필요할 때만 `--profile scheduler`로 켠다.

## 로컬 개발

```bash
cp .env.example .env
# 로컬에서 8001을 쓰려면: WEB_PORT=8001
# HTTP만 쓰면: TRUST_PROXY=0
docker compose up -d --build
docker compose --profile scheduler up -d   # 수집 필요 시
pytest -q
```

web 기동 시 `entrypoint.sh`가 `flask db upgrade`를 1회 실행한다.

## Supabase → 내장 DB 이전 (1회)

```bash
export SUPABASE_DATABASE_URL='postgresql://postgres.PROJECT:PASSWORD@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres'
./scripts/migrate_from_supabase.sh
docker compose up -d --build
```

- **쓰기 중단 시점:** `migrate_from_supabase.sh` 실행 **직전**부터 Supabase(구 Hub DB)에 대한 쓰기를 중단한다. 중단 없이 이원 기동하면 데이터가 어긋난다.
- 개발 Mac에서 이미 전환한 시각: **2026-10-29 16:28 KST** (이후 수집은 내장 `db`만). 운영 Mac 서버는 배포 후 **새 dump**로 다시 이전한다 — 그 서버 스크립트 시작 시각이 그 서버의 컷오버다.
- 덤프 파일(`tmp/`)은 gitignore. 커밋 금지.
- `docker-compose.supabase.yml` deprecated.

## PM 연동 값 (서버 .env에 넣을 Hub 쪽)

| 변수 | 설명 |
|------|------|
| `SECRET_KEY` | 세션·CSRF (필수, 기본값 금지) |
| `TRUST_PROXY` | 서버 `1` |
| `WEB_BIND` / `WEB_PORT` | 기본 `127.0.0.1` / `8010` |
| `CRAWL_API_URL` | `https://crawl.wecarmobility.co.kr` |
| `CRAWL_API_KEY` | 별도 채널 (스케줄러 필수) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 선택 (seed/setup) |
| `DATABASE_URL` | Compose가 `db`로 고정 |

Hub가 PM에 주는 키는 **관리자 → API 키**에서 발급한 값이 맞다. PM의 `VEHICLE_DATA_HUB_API_KEY`에 넣는다.

## CI

`main` push → GitHub Actions 테스트·GHCR. DB 마이그레이션은 Mac Compose에서 수행.
