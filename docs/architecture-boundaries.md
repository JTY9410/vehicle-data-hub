# Vehicle Data Hub — 아키텍처 경계 (구체본)

**상태:** Accepted (Hybrid keep-separate) · **갱신:** 2026-10-05  
**대상:** Cursor / 후속 개발자  
**짝 문서:** WeCar PM `/Users/USER/dev/pm/docs/architecture-boundaries.md`  
**계약 SSOT:** PM `요구사항.md` **#56~#62** (Hub API·필드·제외 규칙)

이 저장소는 **매물·엔카 taxonomy 원천(SSOT)** 이다. WeCar PM은 시세·기준가·파트너 API 제품이며 **별도 앱·별도 DB**다. 하나로 합치지 않는다.

관련: `pro.md` · `AGENTS.md` · `docs/cursor-hub-tasks.md` · ADR `docs/adr/001-keep-apps-layout.md`

---

## 1. 이 앱의 역할 (한 줄 + 표)

**한 줄:** Crawl/CSV → `vehicles` upsert → `GET /api/v1/vehicles*` (X-API-Key) → PM이 미러.

| 한다 | 하지 않는다 |
|------|-------------|
| 크롤/CSV 적재 · `vehicles` upsert | 기준가 · Trim · TWH · Ensemble · CatBoost |
| 1차 품질 필터(렌트 하/허/호, 가격 ≤0 또는 ≥9999) | MFA · AI/RAG · 감사 로그(제품급) · 파트너 시세 |
| `/api/v1/vehicles*` 읽기 API (`X-API-Key`) | PM `listings` / `base_prices` / `partner_api_keys` |
| 엔카 코드 5단 **쓰기** (CSV 시드 + admin codes) | 크롤 API를 PM이 직접 호출하도록 유도 |
| 읽기 API 키 발급·관리 (`api_keys`) | PM과 **동일 `DATABASE_URL`에 함께 write** |

```text
Crawl API / CSV
    → apps/services/import_crawl.py | import_csv.py
    → apps/services/filters.py (should_reject_row)
    → apps/models.Vehicle  (테이블 vehicles)
    → apps/routes/api.py   GET /api/v1/vehicles*
    → PM hub_client → listings 미러 → Trim / 기준가 / /api/v1/price/*
```

---

## 2. 소유 테이블·모델 (코드 경로)

소스: `apps/models.py`

| 테이블 | 모델 클래스 | 소유 | 비고 |
|--------|-------------|------|------|
| `vehicles` | `Vehicle` | **Hub WRITE SSOT** | UK `uq_vehicle_site` = `(site_type, site_id)` |
| `vehicle_maker` | `VehicleMaker` | **Hub WRITE** | PK `maker_no` |
| `vehicle_model` | `VehicleModel` | **Hub WRITE** | PK `model_no` |
| `vehicle_model_detail` | `VehicleModelDetail` | **Hub WRITE** | PK `mdetail_no` |
| `vehicle_grade` | `VehicleGrade` | **Hub WRITE** | PK `grade_no` |
| `vehicle_grade_detail` | `VehicleGradeDetail` | **Hub WRITE** | PK `gdetail_no` |
| `api_keys` | `ApiKey` | **Hub** | PM 파트너 키와 **별개** |
| `app_settings` | `AppSetting` | **Hub** | crawl URL/key 등 |
| `import_jobs` | `ImportJob` | **Hub** | CSV/crawl 적재 이력 |
| `users` | `User` | **Hub** | 관리자 로그인 (MFA 없음) |

### `Vehicle` 핵심 컬럼 (PM 매핑 대상)

| 컬럼 | 의미 |
|------|------|
| `site_type`, `site_id` | 유니크 키 (upsert) |
| `source_id` | CSV 원본 id → API 응답 `id` |
| `car_no`, `car_year`, `car_km`, `car_price` | 번호·연식·km·가격(**만원**) |
| `car_maker`~`car_subgrade` | 표시명 5단 |
| `maker_no`~`gdetail_no` | 엔카 코드 5단 |
| `car_fuel`, `car_mission`, `car_color`, `car_location` | 연료·미션·색·지역 |
| `detail_info`, `option_info`, `unique_option_info`, `diag_info` | 텍스트 (목록은 `include=text` 시에만) |
| `scraped_at` | CSV/크롤 저장일 → API `created_at` |
| `url_link`, `car_cc`, `car_type`, `car_seat`, `car_import_yn` | 부가 |
| 한글 별칭 컬럼 (`색상`, `미션`, `차종`, `인승`, `성능점검일`, `옵션정보`, `유용옵션`, `진단정보`) | API에 영문과 병행 노출 |

### Hub에 **만들지 말 것** (Forbidden tables / modules)

다음 이름·개념을 Hub `apps/models.py` / migrations / services에 **추가하지 않는다.**

- `listings`, `listing_price_history`, `sync_logs` (PM 미러/동기화)
- `base_prices`, `ml_model_artifacts`, `price_setting_definitions`
- `partner_api_keys`, `analysis_logs`
- `ai_connections`, `ai_policy`, `ai_usage`, `knowledge_docs`, `audit_logs`
- `login_attempts`(MFA 계열), `translation_cache`, `learned_glossary`, `car_info_cache`, `code_crosswalk`
- `app/services/base_price.py`, `trim.py`, `harmonic.py`, `catboost_model.py`, `hub_client.py` 류 시세 모듈
- Hub에 `/api/v1/price/*` 파트너 시세 엔드포인트

---

## 3. 모듈·파일 소유 맵 (실제 경로)

### 3.1 Ingest (Hub only)

| 파일 | 역할 |
|------|------|
| `apps/services/crawl_client.py` | 외부 크롤 API HTTP |
| `apps/services/import_crawl.py` | 크롤 → `should_reject_row` → `vehicles` upsert · `ImportJob` |
| `apps/services/import_csv.py` | CSV → 동일 필터 → upsert · `(site_type,site_id)` |
| `apps/services/filters.py` | **1차 품질 필터 SSOT** |
| `apps/services/scheduler.py` · `apps/scheduler.py` | 주기 적재 |
| `apps/routes/admin.py` | `/upload`, crawl 수동, settings, API keys UI |
| `config.py` | `CRAWL_API_URL`, `CRAWL_API_KEY`, `API_PER_PAGE_MAX` |

### 3.2 Codes (Hub WRITE)

| 파일 | 역할 |
|------|------|
| `apps/services/encar_seed.py` | `data/encar_codes/*.csv` → DB upsert |
| `apps/services/encar_codes.py` | 코드 조회/인덱스 |
| `apps/services/encar_fuel.py` · `encar_attrs.py` | 연료·속성 정규화 |
| `data/encar_codes/vehicle_maker.csv` | 제조사 |
| `data/encar_codes/vehicle_model.csv` | 모델 |
| `data/encar_codes/vehicle_model_detail.csv` | 세부모델 |
| `data/encar_codes/vehicle_grade.csv` | 등급 |
| `data/encar_codes/vehicle_grade_detail.csv` | 세부등급 |

**주의:** `apps/routes/admin.py`의 `/api/codes/makers|models|grades|gdetails` 는 **관리자 세션용**이다. PM이 쓰는 공개 `X-API-Key` codes API가 아니다. 목표 백로그는 `GET /api/v1/codes/*` + API Key.

### 3.3 Public read API (Hub → PM)

| 파일 | 역할 |
|------|------|
| `apps/routes/api.py` | Blueprint `url_prefix=/api/v1` · `VEHICLE_FIELDS` · `_vehicle_public` |
| `apps/services/api_keys.py` | `X-API-Key` / Bearer 검증 |
| `apps/services/openapi.py` | OpenAPI (vehicles만) |
| `apps/services/db_stats.py` | count/estimate · list order |

### 3.4 PM 쪽에서만 존재하는 것 (참고 — Hub에 이식 금지)

`/Users/USER/dev/pm/app/services/hub_client.py`, `listing_sync.py`, `base_price.py`, `trim.py`, `harmonic.py`, `app/modules/partner_api/`, `app/modules/ai/`, `app/modules/auth/totp.py` 등.

---

## 4. Hub Public API 계약 (PM이 소비하는 것)

구현: `apps/routes/api.py` · 명세: PM `요구사항.md` #56~#59.

### 4.1 공통

| 항목 | 값 |
|------|-----|
| Base | `/api/v1` (배포 예: `https://vehicle-data-hub-alpha.vercel.app/api/v1`) |
| 인증 | 모든 요청 `X-API-Key` 또는 `Authorization: Bearer` — 없음/비활성 → **401** |
| 가격 | `price_unit` 항상 `"만원"` · `car_price`는 만원 정수 |
| CORS | `Access-Control-Allow-Origin: *` (브라우저에 키 노출 금지) |
| per_page 상한 | 린: `API_PER_PAGE_MAX` 기본 **100** · `include=text`: `API_PER_PAGE_MAX_WITH_TEXT` (요구사항은 max **20**, config 기본은 MAX와 동일 — 변경 시 PM `hub_client`와 맞출 것) |

### 4.2 엔드포인트

#### `GET /api/v1/vehicles`

Query:

| 파라미터 | 설명 |
|----------|------|
| `page` | ≥1 |
| `per_page` | 1..상한 |
| `include` | `text` 이면 장문 필드 포함 |
| `maker_no`, `model_no`, `mdetail_no`, `grade_no`, `gdetail_no` | 코드 필터 |
| `maker`, `model` | 이름 필터 |
| `site_type`, `year` | |
| `price_min`, `price_max` | 만원 |
| `created_at_from`, `created_at_to` | `YYYY-MM-DD` → DB `scraped_at` 구간 (**증분 sync**) |
| `fuel` / `car_fuel` | 연료 |

응답 envelope:

```json
{
  "price_unit": "만원",
  "page": 1,
  "per_page": 20,
  "total": 12345,
  "fields": ["id", "site_type", "..."],
  "items": [ { "...": "..." } ]
}
```

#### `GET /api/v1/vehicles/search?q=`

- `q` 없으면 items `[]`
- 내부 limit **50** (`hub_client.HUB_SEARCH_MAX_PER_PAGE`)

#### `GET /api/v1/vehicles/<int:vehicle_id>`

- 경로 = 응답의 **`db_id`** (CSV `id` 아님)
- 404 → `{"error":"not_found"}`

### 4.3 item 필드 목록 (`_vehicle_public` / #58)

항상(또는 린 목록):

`id`, `db_id`, `car_import_yn`, `site_type`, `site_id`, `car_no`, `car_year`, `car_km`, `car_price`, `car_maker`, `car_model`, `car_submodel`, `car_grade`, `car_subgrade`, `maker_no`, `model_no`, `mdetail_no`, `grade_no`, `gdetail_no`, `car_fuel`, `car_mission`, `car_color`, `car_location`, `url_link`, `created_at`, `car_cc`, `car_type`, `car_seat`, `inspected_at`, `색상`, `미션`, `차종`, `인승`, `성능점검일`, `price_unit`

`include=text` 추가:

`detail_info`, `option_info`, `unique_option_info`, `diag_info`, `옵션정보`, `유용옵션`, `진단정보`

**매핑 주의**

| Hub 응답 | Hub DB | PM `Listing` |
|----------|--------|--------------|
| `id` | `source_id` (없으면 `str(pk)`) | `external_id` |
| `db_id` | `vehicles.id` | `db_id` |
| `created_at` | `scraped_at` | `scraped_at` / `saved_at` |
| `site_type`+`site_id` | UK | UK `uq_listing_site` |

필드·필터·상한을 바꾸면 **반드시** PM `hub_client.py` · `listing_sync.py` · `요구사항.md` #56~#62를 같은 변경 세트로 고지/수정한다.

---

## 5. 품질 필터 (1차 SSOT = Hub)

파일: `apps/services/filters.py`  
호출: `import_csv.py`, `import_crawl.py` → `should_reject_row(...)`

| 규칙 | 구현 | reject reason |
|------|------|---------------|
| `site_type`/`site_id` 없음 | | `missing_site_key` |
| 번호에 `하`/`허`/`호` | `is_rental_plate` · `RENTAL_CHARS` | `rental_plate` |
| 가격 ≤0 또는 ≥**9999** (만원) | `is_abnormal_price` | `abnormal_price` |
| 가격 None | 비정상으로 거부 | `abnormal_price` |

PM 방어 필터 (`pm/app/services/trim.py`):

- `is_rental_plate`: 동일 (하/허/호)
- `is_invalid_price`: **`price >= 9000`** ← Hub의 **9999**와 **불일치(드리프트)**. 규칙 변경 시 양쪽·`요구사항.md` #61을 **함께** 맞출 것. 목표 SSOT는 Hub `filters.py` + #61(≥9999).

---

## 6. 코드 마스터 (현재 vs 목표)

### 현재

| 위치 | 경로 | 시드 |
|------|------|------|
| Hub | `data/encar_codes/*.csv` | `apps/services/encar_seed.py` → `seed_encar_codes()` |
| PM | `data/encar_codes/*.csv` (동일 5파일) | `app/services/code_sync.py` → `seed_encar_codes()` · job `app/jobs/code_sync.py` |

CSV 컬럼 예 (`vehicle_maker.csv`): `maker_no,maker_name,sort_no,synced_at`

5단: `maker_no` → `model_no` → `mdetail_no` → `grade_no` → `gdetail_no`

### 목표 (백로그)

Hub에 API Key 보호 codes API:

```http
GET /api/v1/codes/makers
GET /api/v1/codes/models?maker_no=
GET /api/v1/codes/mdetails?model_no=
GET /api/v1/codes/grades?mdetail_no=
GET /api/v1/codes/gdetails?grade_no=
# 또는 GET /api/v1/codes/tree · 증분 synced_at
```

응답 예(makers):

```json
{ "items": [ { "maker_no": "10055", "maker_name": "현대", "sort_no": 1 } ] }
```

그 후 PM `code_sync`를 Hub pull로 전환하고 CSV 이중 시드를 축소한다.  
taxonomy 변경 시: **Hub CSV/시드 먼저** → (과도기) PM CSV 동기화 또는 codes API.

---

## 7. 환경변수 (Hub `.env.example`만 — 비밀값 금지)

| 변수 | 용도 |
|------|------|
| `SECRET_KEY` | Flask 세션 |
| `DATABASE_URL` | Hub 전용 DB (`postgresql+psycopg://...`) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 최초 admin (코드에 실비번 커밋 금지) |
| `CRAWL_API_URL` | 기본 `https://crawl.wecarmobility.co.kr` |
| `CRAWL_API_KEY` | 크롤 인증 (PM `.env`에 넣지 않음) |
| `API_PER_PAGE_MAX` | 목록 상한 (기본 100) |
| `API_PER_PAGE_MAX_WITH_TEXT` | text 포함 상한 |

PM이 쓰는 Hub 연동 변수는 **PM** `.env.example`의 `VEHICLE_DATA_HUB_*` / `HUB_SYNC_*` 이다. Hub 저장소에 PM 키를 넣지 않는다.

---

## 8. 금지 패턴 (Cursor soft-stop)

1. Hub에 `base_prices` / Trim / TWH / CatBoost / forecast / briefing 테이블·서비스 추가
2. Hub·PM `DATABASE_URL` 공유 write
3. PM용 `CRAWL_API_*` 클라이언트·문서·예제 추가 (크롤은 Hub만)
4. `apps/routes`·`apps/services`를 `app/modules`로 전면 이전 (ADR 001)
5. AI/MFA/audit 제품 테이블을 Hub에 “미리” 생성 (`pro.md`)
6. API Key·비밀번호를 응답·로그·README·커밋에 출력
7. `/api/v1/vehicles*` 계약을 PM 미고지 변경
8. 파일명 힌트: Hub에 `hub_client.py`, `listing_sync.py`, `base_price.py`, `partner_api/` 신설 금지

---

## 9. 결정 트리 — 이 기능은 Hub? PM?

| # | 기능 예 | 어디 | 이유 |
|---|---------|------|------|
| 1 | 크롤 스케줄·수동 수집·ImportJob | **Hub** | `import_crawl` / admin upload |
| 2 | CSV 매물 업로드·제외 규칙 | **Hub** (+ PM은 동일 스키마 관리자 업로드만) | #61 |
| 3 | `vehicles`에 옵션 필드 추가 + API 노출 | **Hub** 먼저, PM `listing_sync` 매핑 후속 | 계약 #58 |
| 4 | 엔카 제조사/등급 CSV 수정 | **Hub** SSOT → PM CSV/API 동기화 | taxonomy |
| 5 | `GET /api/v1/codes/*` 신설 | **Hub** | 공개 읽기 + API Key |
| 6 | Hub sync / listings 미러 / sync_logs | **PM** | `listing_sync` · `hub_sync` job |
| 7 | 기준가·15k bucket·TWH | **PM** | `base_price.py` · `base_prices` |
| 8 | Trim 10% 통계 | **PM** | `trim.py` (품질 제외와 다름) |
| 9 | 파트너 `GET/POST /api/v1/price/*` | **PM** | `modules/partner_api` |
| 10 | MFA · AI 연결 · RAG · audit | **PM** | Hub `pro.md` 금지 |
| 11 | 홈 검색 KPI·lookup UI | **PM** | 로컬 미러만 (#60) |
| 12 | 렌트/가격 제외 임계값 변경 | **Hub `filters.py` + #61 + PM `trim.is_*`** | 드리프트 방지 |

---

## 10. Cursor 작업 템플릿 (요약)

상세 복붙 프롬프트: `docs/cursor-hub-tasks.md`

### When adding a vehicle field

1. `apps/models.py` `Vehicle` + Alembic migration
2. `import_csv.py` / `import_crawl.py` 매핑
3. `apps/routes/api.py` `VEHICLE_FIELDS` + `_vehicle_public` (+ `_LIST_LOAD` if 목록)
4. OpenAPI·테스트 갱신
5. **PM에 고지:** `listing_sync._apply_listing_fields` · `요구사항` #58

### When changing code taxonomy

1. Hub `data/encar_codes/*.csv` 수정
2. `encar_seed.seed_encar_codes` 재실행 경로 확인
3. PM `data/encar_codes` 동일 반영 **또는** codes API 계획
4. 양쪽 count/샘플 비교

### When changing quality filter

1. Hub `filters.py`만 SSOT로 변경
2. `요구사항.md` #61 문구 동기화 (PM 저장소)
3. PM `trim.is_rental_plate` / `is_invalid_price` 동등화 (현재 9000 vs 9999 해소)
4. pytest 양쪽

### When changing base price / Trim / price API

→ **거절.** PM 저장소 `/Users/USER/dev/pm` 로 안내.

---

## 11. PR 체크리스트 (Hub)

- [ ] 변경이 매물 원천·코드 WRITE·vehicles API인가? (아니면 PM)
- [ ] 금지 테이블/시세 모듈을 추가하지 않았는가?
- [ ] `/api/v1/vehicles*` 필드·필터·per_page 변경 시 PM #56~#62 · `hub_client` · `listing_sync` 영향 고지
- [ ] 품질 필터 변경 시 PM `trim`·#61 동시 검토 (9999 vs 9000)
- [ ] 엔카 CSV 변경 시 PM `data/encar_codes` 동기화 계획
- [ ] `CRAWL_API_*`를 PM 문서/예제에 유도하지 않음
- [ ] 비밀값·`.env` 실값 커밋/로그 없음
- [ ] 레이아웃 `app/modules`로 이전하지 않음 (ADR 001)
- [ ] 관련 pytest 통과

---

## 12. 백로그 (경계 강화)

1. `GET /api/v1/codes/*` (API Key) + OpenAPI
2. PM `code_sync` Hub pull 전환 · CSV 이중 시드 축소
3. 품질 필터 임계값 Hub↔PM↔#61 단일화 (9999)
4. (선택) 필터 버전 메타를 API에 노출
