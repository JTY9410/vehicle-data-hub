# Vehicle Data Hub API 명세서

- 버전: 1.0.0 (OpenAPI 3.0.3)
- Base URL: `https://vehicle-data-hub-alpha.vercel.app/api/v1`
- 형식: JSON (UTF-8) · 읽기 전용 `GET` · 가격 단위 **만원**
- 발급: Vehicle Data Hub 관리자 > **API 명세서·키 발급**

관리자 > API 명세서·키 발급에서 받은 API 키로 차량 매물을 조회합니다. 읽기 전용(GET)이며 가격 단위는 만원입니다.

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
- 목록 `per_page` 기본 20, 최대 100 (`include=text`일 때 최대 100)
- 렌트 번호(하/허/호), 가격 0 이하 또는 9999 이상 매물은 저장하지 않으므로 응답에도 없습니다.

## 3. 엔드포인트

### GET /api/v1/vehicles — 차량 목록

필터·페이지로 차량을 조회합니다. 증분 동기화는 created_at_from을 씁니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `page` | query | integer | 선택 | 페이지 번호 (1부터) |
| `per_page` | query | integer | 선택 | 페이지 크기 (기본 20, 최대 100) |
| `include` | query | string | 선택 | text면 긴 텍스트 필드 포함 |
| `maker_no` | query | string | 선택 | 엔카 제조사 코드 |
| `model_no` | query | string | 선택 | 엔카 모델 코드 |
| `mdetail_no` | query | string | 선택 | 엔카 세부모델 코드 |
| `grade_no` | query | string | 선택 | 엔카 등급 코드 |
| `gdetail_no` | query | string | 선택 | 엔카 세부등급 코드 |
| `maker` | query | string | 선택 | 제조사명 (정확히 일치) |
| `model` | query | string | 선택 | 모델명 (정확히 일치) |
| `site_type` | query | string | 선택 | 사이트 구분 |
| `year` | query | string | 선택 | 연식 (부분 일치) |
| `price_min` | query | integer | 선택 | 최소 가격 (만원) |
| `price_max` | query | integer | 선택 | 최대 가격 (만원) |
| `created_at_from` | query | string | 선택 | Hub 저장일 시작 YYYY-MM-DD (증분 동기화) |
| `created_at_to` | query | string | 선택 | Hub 저장일 끝 YYYY-MM-DD |
| `fuel` | query | string | 선택 | 연료 (car_fuel 도 허용, 휘발유 등 별칭 정규화) |

| 응답 | 설명 |
|---|---|
| `200` | 목록 |
| `401` | API 키 없음 또는 폐기됨 |

### GET /api/v1/vehicles/search — 차량 검색

차량번호·제조사·모델·연료 부분 일치, 최대 50건.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `q` | query | string | 선택 | 검색어 (없으면 빈 목록) |
| `include` | query | string | 선택 | text면 긴 텍스트 필드 포함 |

| 응답 | 설명 |
|---|---|
| `200` | 검색 결과 |
| `401` | API 키 없음 또는 폐기됨 |

### GET /api/v1/vehicles/{vehicle_id} — 차량 상세

목록 응답의 db_id로 조회합니다. 긴 텍스트 필드를 항상 포함합니다.

| 파라미터 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `vehicle_id` | path | integer | 필수 | 목록 응답의 db_id |

| 응답 | 설명 |
|---|---|
| `200` | 상세 |
| `401` | API 키 없음 또는 폐기됨 |
| `404` | 없는 db_id |

## 4. 차량 필드

| 필드 | 설명 | 비고 |
|---|---|---|
| `id` | 원본 크롤 id (없으면 db_id 문자열) |  |
| `db_id` | Hub DB PK. 상세 경로 /vehicles/{db_id}에 사용 |  |
| `car_import_yn` | 수입차 여부 (Y/N) |  |
| `site_type` | 사이트 구분 (encar, kb, kcar) |  |
| `site_id` | 사이트 매물 ID. site_type과 함께 유일 키 |  |
| `car_no` | 차량번호 |  |
| `car_year` | 연식 |  |
| `car_km` | 주행거리 (km, 정수) |  |
| `car_price` | 가격 (만원, 정수) |  |
| `car_maker` | 제조사 |  |
| `car_model` | 모델 |  |
| `car_submodel` | 세부모델 |  |
| `car_grade` | 등급 |  |
| `car_subgrade` | 세부등급 |  |
| `maker_no` | 엔카 제조사 코드 |  |
| `model_no` | 엔카 모델 코드 |  |
| `mdetail_no` | 엔카 세부모델 코드 |  |
| `grade_no` | 엔카 등급 코드 |  |
| `gdetail_no` | 엔카 세부등급 코드 |  |
| `car_fuel` | 연료 (가솔린, 디젤, LPG, 하이브리드, 전기, 수소) |  |
| `car_mission` | 변속기 |  |
| `car_color` | 색상 |  |
| `car_location` | 지역 |  |
| `detail_info` | 상세정보 | include=text 또는 상세 |
| `option_info` | 옵션정보 | include=text 또는 상세 |
| `unique_option_info` | 유용옵션 | include=text 또는 상세 |
| `inspected_at` | 성능점검일 (YYYY-MM-DD) |  |
| `diag_info` | 진단정보 | include=text 또는 상세 |
| `url_link` | 원문 매물 링크 |  |
| `created_at` | Hub 저장일시 (ISO-8601) |  |
| `car_cc` | 배기량 |  |
| `car_type` | 차종 |  |
| `car_seat` | 승차인원 |  |
| `색상` | car_color 한글 별칭 |  |
| `미션` | car_mission 한글 별칭 |  |
| `차종` | car_type 한글 별칭 |  |
| `인승` | car_seat 한글 별칭 |  |
| `성능점검일` | inspected_at 한글 별칭 |  |
| `옵션정보` | option_info 한글 별칭 | include=text 또는 상세 |
| `유용옵션` | unique_option_info 한글 별칭 | include=text 또는 상세 |
| `진단정보` | diag_info 한글 별칭 | include=text 또는 상세 |
| `price_unit` | 가격 단위. 항상 만원 |  |

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
curl -H "X-API-Key: YOUR_KEY" "https://vehicle-data-hub-alpha.vercel.app/api/v1/vehicles?page=1&per_page=20"
```

```python
import requests

r = requests.get(
    "https://vehicle-data-hub-alpha.vercel.app/api/v1/vehicles",
    headers={"X-API-Key": "YOUR_KEY"},
    params={"page": 1, "per_page": 20},
    timeout=30,
)
r.raise_for_status()
items = r.json()["items"]
```

```javascript
const res = await fetch("https://vehicle-data-hub-alpha.vercel.app/api/v1/vehicles?page=1&per_page=20", {
  headers: { "X-API-Key": process.env.VEHICLE_HUB_API_KEY },
});
const data = await res.json();
```

## 7. 증분 동기화

1. 최초: `page`를 1부터 늘려 가며 `items`가 빌 때까지 받습니다.
2. 이후: 마지막 동기화 날짜를 `created_at_from=YYYY-MM-DD`로 넘겨 새로 저장된 매물만 받습니다.
3. 유일 키는 `site_type` + `site_id`이며, 상세 조회는 `db_id`를 씁니다.