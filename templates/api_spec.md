# Vehicle Data Hub API 명세서

- 버전: {{ spec.info.version }} (OpenAPI {{ spec.openapi }})
- Base URL: `{{ base_url }}`
- 형식: JSON (UTF-8) · 읽기 전용 `GET` · 가격 단위 **만원**
- 발급: Vehicle Data Hub 관리자 > **API 명세서·키 발급**

{{ spec.info.description }}

## 1. 인증

모든 요청에 아래 헤더 중 **하나**를 넣습니다.

```http
X-API-Key: <발급받은_API_키>
Authorization: Bearer <발급받은_API_키>
```

키가 없거나 폐기되면 `401` `{"error": "unauthorized"}`를 반환합니다. API 키는 서버 쪽에만 두고 브라우저 코드·로그·문서에 원문을 남기지 않습니다.

## 2. 공통 규칙

- CORS: `Access-Control-Allow-Origin: *`, 허용 메서드 `GET, OPTIONS`
- 가격 `car_price`는 만원 단위 정수, 응답마다 `price_unit: "만원"`
- 목록·검색 기본 응답에는 긴 텍스트 필드가 없습니다. 필요하면 `include=text` 또는 상세 API를 씁니다.
- 목록 `per_page` 기본 20, 최대 {{ config.API_PER_PAGE_MAX }} (`include=text`일 때 최대 {{ config.API_PER_PAGE_MAX_WITH_TEXT }})
- 렌트 번호(하/허/호), 가격 0 이하 또는 9999 이상 매물은 저장하지 않으므로 응답에도 없습니다.

## 3. 엔드포인트
{% for path, item in spec.paths.items() %}{% set op = item["get"] %}
### GET /api/v1{{ path }} — {{ op.summary }}

{{ op.description }}

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
{% for p in op.parameters %}| `{{ p.name }}` | {{ p["in"] }} | {{ p.schema.type }} | {{ "필수" if p.required else "선택" }} | {{ p.description }} |
{% endfor %}
| 응답 | 설명 |
|---|---|
{% for code, r in op.responses.items() %}| `{{ code }}` | {{ r.description }} |
{% endfor %}{% endfor %}
## 4. 차량 필드

| 필드 | 설명 | 비고 |
|---|---|---|
{% for name, desc, is_text in fields %}| `{{ name }}` | {{ desc }} | {{ "include=text 또는 상세" if is_text else "" }} |
{% endfor %}
## 5. 응답 예시

`GET /api/v1/vehicles?page=1&per_page=1`

```json
{
  "price_unit": "만원",
  "page": 1,
  "per_page": 1,
  "total": 12345,
  "fields": ["id", "car_import_yn", "site_type", "..."],
  "items": [
    {
      "id": "10",
      "db_id": 1,
      "car_import_yn": "N",
      "site_type": "encar",
      "site_id": "s-10",
      "car_no": "12가3456",
      "car_year": "2020",
      "car_km": 10000,
      "car_price": 1500,
      "car_maker": "현대",
      "car_model": "쏘나타",
      "car_fuel": "가솔린",
      "url_link": "https://example.com/10",
      "created_at": "2026-10-01T00:00:00+00:00",
      "price_unit": "만원"
    }
  ]
}
```

오류 응답:

```json
{"error": "unauthorized", "message": "X-API-Key 또는 Authorization: Bearer 가 필요합니다."}
{"error": "not_found"}
```

## 6. 연동 예제

```bash
curl -H "X-API-Key: YOUR_KEY" "{{ base_url }}/vehicles?page=1&per_page=20"
```

```python
import requests

r = requests.get(
    "{{ base_url }}/vehicles",
    headers={"X-API-Key": "YOUR_KEY"},
    params={"page": 1, "per_page": 20},
    timeout=30,
)
r.raise_for_status()
items = r.json()["items"]
```

```javascript
const res = await fetch("{{ base_url }}/vehicles?page=1&per_page=20", {
  headers: { "X-API-Key": process.env.VEHICLE_HUB_API_KEY },
});
const data = await res.json();
```

## 7. 증분 동기화

1. 최초: `page`를 1부터 늘려 가며 `items`가 빌 때까지 받습니다.
2. 이후: 마지막 동기화 날짜를 `created_at_from=YYYY-MM-DD`로 넘겨 새로 저장된 매물만 받습니다.
3. 유일 키는 `site_type` + `site_id`이며, 상세 조회는 `db_id`를 씁니다.
