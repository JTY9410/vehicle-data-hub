# Cursor 복붙 프롬프트 — Vehicle Data Hub

사용법: 아래 블록을 Cursor 채팅에 그대로 붙인다. 작업 전 `docs/architecture-boundaries.md`가 이미 alwaysApply 규칙에 연결돼 있다.

---

## H1. 매물 필드 추가 (vehicles + API)

```text
Vehicle Data Hub에서 매물 필드를 추가한다. Hub↔PM 경계(docs/architecture-boundaries.md)를 지킨다.

목표 필드: <이름> / 타입: <str|int|datetime> / 의미: <…>

필수 단계:
1. apps/models.py Vehicle에 컬럼 추가 + Alembic migration (migrations/versions/)
2. apps/services/import_csv.py · import_crawl.py 매핑 (있으면 CSV 키도)
3. apps/routes/api.py:
   - VEHICLE_FIELDS에 키 추가
   - _vehicle_public에 응답 추가
   - 목록에 필요하면 _LIST_LOAD에 포함 (장문이면 include=text만)
4. apps/services/openapi.py 및 tests/ 갱신
5. 완료 보고에 PM 후속 작업 명시:
   - /Users/USER/dev/pm/app/services/listing_sync.py _apply_listing_fields
   - pm/요구사항.md #58 필드 표
금지: base_prices, Trim, MFA, AI, /api/v1/price. 비밀값 출력 금지.
완료 전: 관련 pytest.
```

---

## H2. 엔카 코드 taxonomy 변경

```text
Hub 엔카 코드 마스터를 수정한다. SSOT는 이 저장소다.

변경: <maker/model/mdetail/grade/gdetail 중 무엇> / 내용: <…>

단계:
1. data/encar_codes/ 해당 CSV 수정 (vehicle_maker.csv 등 5파일 체계 유지)
2. apps/services/encar_seed.py seed_encar_codes 경로로 적재 가능한지 확인
3. apps/services/encar_codes.py 인덱스/캐시 clear 필요 시 호출
4. admin codes API(세션) vs 공개 /api/v1/codes/* 구분 — 공개 API Key codes는 아직 없으면 만들지 말고 백로그로만 제안하거나, 명시적으로 구현 요청된 경우 API Key+OpenAPI로 추가
5. PM(/Users/USER/dev/pm/data/encar_codes) 동일 CSV 동기화 필요함을 PR 설명에 적기
금지: PM base_price 로직 변경. DB URL 공유. 비밀값 커밋.
```

---

## H3. 품질 필터 변경 (렌트/가격)

```text
1차 품질 필터 SSOT는 apps/services/filters.py 이다.

변경안: <예: 상한을 9999 유지 / 렌트 문자 추가 등>

단계:
1. filters.py의 RENTAL_CHARS / is_abnormal_price / should_reject_row 수정
2. import_csv.py · import_crawl.py가 should_reject_row를 쓰는지 확인 (이미 사용 중)
3. tests/test_filters.py (없으면 추가)로 rental_plate · abnormal_price · missing_site_key 커버
4. 보고에 반드시 포함: PM app/services/trim.py 의 is_rental_plate / is_invalid_price
   현재 드리프트: Hub ≥9999, PM ≥9000, 요구사항 #61 ≥9999 → 정렬 필요
5. PM 저장소 요구사항.md #61 문구 동기화는 PM 쪽 작업으로 명시
금지: 필터를 PM에만 바꾸라고 Hub에서 우회 구현하지 말 것.
```

---

## H4. vehicles API 계약 변경 (쿼리/상한/필드)

```text
apps/routes/api.py 공개 API를 변경한다. 계약 SSOT는 PM 요구사항.md #56~#59.

변경: <쿼리 파라미터 / per_page 상한 / 응답 필드>

단계:
1. api.py list_vehicles / search_vehicles / vehicle_detail / _vehicle_public
2. config.py API_PER_PAGE_MAX · API_PER_PAGE_MAX_WITH_TEXT와 요구사항(린 100, text 20) 정합성 확인
3. openapi.py · tests/test_admin_api.py 등 API 테스트
4. 호환성: created_at_from/to → scraped_at, id vs db_id 혼동 금지, price_unit=만원 유지
5. Breaking change면 PM hub_client.py · listing_sync.py 수정 체크리스트를 결과 mid에 나열
인증: X-API-Key 필수 · 401 메시지 유지. 키를 로그에 남기지 않음.
```

---

## H5. 크롤/CSV 적재 개선

```text
매물 적재는 Hub only. apps/services/crawl_client.py · import_crawl.py · import_csv.py · ImportJob.

목표: <…>

단계:
1. 필터는 filters.should_reject_row 경유 유지
2. upsert 키 site_type+site_id (Vehicle UniqueConstraint uq_vehicle_site)
3. admin 업로드 UI는 apps/routes/admin.py /upload
4. CRAWL_API_URL/KEY는 config/.env — PM .env.example에 추가하지 말 것
5. 스케줄러 변경 시 apps/services/scheduler.py
금지: PM이 크롤 API를 직접 치게 하는 엔드포인트·문서.
```

---

## H6. 공개 codes API 추가 (백로그 구현)

```text
GET /api/v1/codes/* 를 X-API-Key로 공개한다. (admin /api/codes/* 세션 API와 별개)

제안 엔드포인트:
- GET /api/v1/codes/makers
- GET /api/v1/codes/models?maker_no=
- GET /api/v1/codes/mdetails?model_no=
- GET /api/v1/codes/grades?mdetail_no=
- GET /api/v1/codes/gdetails?grade_no=

요구:
1. apps/routes/api.py 또는 codes 전용 blueprint를 /api/v1 아래에, require_api_key 동일
2. 모델 VehicleMaker…VehicleGradeDetail 읽기만
3. openapi.py 반영
4. 페이지네이션 또는 tree — 문서화
5. PM code_sync를 Hub pull로 바꾸는 후속은 PM 저장소 작업으로 명시
금지: 시세·기준가. 쓰기 공개 API 금지(READ only).
```

---

## H7. 거절해야 할 요청 (복붙 답변)

```text
이 요청은 WeCar PM(/Users/USER/dev/pm) 범위입니다.
Vehicle Data Hub는 매물·엔카 코드 원천과 /api/v1/vehicles* 만 담당합니다.
기준가/Trim/TWH/파트너 /api/v1/price/MFA/AI는 Hub에 구현하지 않습니다.
docs/architecture-boundaries.md 결정 트리를 보세요.
```

적용 예: 기준가 테이블, Trim 서비스, 파트너 시세, MFA, Hub·PM DB 통합.
