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

## API

관리자 → API 키 → API 명세서 참고. 헤더 `X-API-Key` 필요.
