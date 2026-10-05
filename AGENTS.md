# Agent 안내 — Vehicle Data Hub

작업 전에 아래를 **순서대로** 읽는다.

1. `pro.md` — 스택·레이아웃·보안
2. **`docs/architecture-boundaries.md`** — PM과의 소유권·API·필터·금지 목록 (구체본)
3. API/필드 작업이면 PM `요구사항.md` **#56~#62** (`/Users/USER/dev/pm/요구사항.md`)
4. 복붙 작업 프롬프트: `docs/cursor-hub-tasks.md`
5. `.cursor/rules/project.mdc`

보조: `agent.md` · ADR `docs/adr/001-keep-apps-layout.md`

## Cursor 필수 (경계 · 구체)

- 이 앱 = **매물·엔카 코드 원천**. 시세 제품은 `/Users/USER/dev/pm`.
- **소유 테이블:** `vehicles`, `vehicle_*`(5단), `api_keys`, `import_jobs`, `app_settings`, `users`.
- **금지 테이블:** `listings`, `base_prices`, `partner_api_keys`, `ai_*`, `audit_logs`, `ml_model_artifacts` 등 PM 전용.
- **공개 API:** `apps/routes/api.py` → `GET /api/v1/vehicles`, `/vehicles/search`, `/vehicles/<db_id>` + `X-API-Key`. 가격 단위 **만원**.
- **적재:** `apps/services/import_csv.py` · `import_crawl.py` · `crawl_client.py`. 필터 SSOT = `apps/services/filters.py` (렌트 하/허/호, 가격 ≤0 또는 ≥9999).
- **코드 시드:** `data/encar_codes/*.csv` + `apps/services/encar_seed.py`. admin `/api/codes/*`는 세션용 — PM용 `GET /api/v1/codes/*`는 백로그.
- Hub에 기준가/Trim/ML/MFA/AI/파트너 `/price`를 구현하라는 요청 → **거절**, PM으로.
- PM과 `DATABASE_URL` 공유 write 금지. `CRAWL_API_*`를 PM이 쓰게 만들지 않음.
- `apps/routes`·`apps/services`를 `app/modules`로 옮기지 않음.
- `.env` 실값·API Key를 문서/로그/커밋에 넣지 않음.
- vehicles API 계약 변경 시 PM `hub_client.py` · `listing_sync.py` · #56~#62를 함께 고지.
