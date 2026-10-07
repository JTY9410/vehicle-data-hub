from flask import current_app, render_template, request

from apps.routes.api import VEHICLE_FIELDS, _TEXT_FIELDS

# 명세서(화면 · OpenAPI · Markdown) 공통 원천. /api/v1 계약을 바꾸면 여기와 PM #56~#62를 같이 고친다.
FIELD_DESCRIPTIONS = {
    "id": "원본 크롤 id (없으면 db_id 문자열)",
    "db_id": "Hub DB PK. 상세 경로 /vehicles/{db_id}에 사용",
    "car_import_yn": "수입차 여부 (Y/N)",
    "site_type": "사이트 구분 (encar, kb, kcar)",
    "site_id": "사이트 매물 ID. site_type과 함께 유일 키",
    "car_no": "차량번호",
    "car_year": "연식",
    "car_km": "주행거리 (km, 정수)",
    "car_price": "가격 (만원, 정수)",
    "car_maker": "제조사",
    "car_model": "모델",
    "car_submodel": "세부모델",
    "car_grade": "등급",
    "car_subgrade": "세부등급",
    "maker_no": "엔카 제조사 코드",
    "model_no": "엔카 모델 코드",
    "mdetail_no": "엔카 세부모델 코드",
    "grade_no": "엔카 등급 코드",
    "gdetail_no": "엔카 세부등급 코드",
    "car_fuel": "연료 (가솔린, 디젤, LPG, 하이브리드, 전기, 수소)",
    "car_mission": "변속기",
    "car_color": "색상",
    "car_location": "지역",
    "detail_info": "상세정보",
    "option_info": "옵션정보",
    "unique_option_info": "유용옵션",
    "inspected_at": "성능점검일 (YYYY-MM-DD)",
    "diag_info": "진단정보",
    "url_link": "원문 매물 링크",
    "created_at": "Hub 저장일시 (ISO-8601)",
    "car_cc": "배기량",
    "car_type": "차종",
    "car_seat": "승차인원",
    "색상": "car_color 한글 별칭",
    "미션": "car_mission 한글 별칭",
    "차종": "car_type 한글 별칭",
    "인승": "car_seat 한글 별칭",
    "성능점검일": "inspected_at 한글 별칭",
    "옵션정보": "option_info 한글 별칭",
    "유용옵션": "unique_option_info 한글 별칭",
    "진단정보": "diag_info 한글 별칭",
    "price_unit": "가격 단위. 항상 만원",
}
RESPONSE_FIELDS = ("id", "db_id", *VEHICLE_FIELDS[1:], "price_unit")
_INTEGER_FIELDS = {"db_id", "car_km", "car_price"}


def _param(name, description, *, kind="string", location="query", required=False, **schema):
    return {
        "name": name,
        "in": location,
        "required": required,
        "description": description,
        "schema": {"type": kind, **schema},
    }


def _list_params() -> list[dict]:
    cap = current_app.config["API_PER_PAGE_MAX"]
    return [
        _param("page", "페이지 번호 (1부터)", kind="integer", minimum=1, default=1),
        _param(
            "per_page",
            f"페이지 크기 (기본 20, 최대 {cap})",
            kind="integer",
            minimum=1,
            maximum=cap,
            default=20,
        ),
        _param("include", "text면 긴 텍스트 필드 포함", enum=["text"]),
        _param("maker_no", "엔카 제조사 코드"),
        _param("model_no", "엔카 모델 코드"),
        _param("mdetail_no", "엔카 세부모델 코드"),
        _param("grade_no", "엔카 등급 코드"),
        _param("gdetail_no", "엔카 세부등급 코드"),
        _param("maker", "제조사명 (정확히 일치)"),
        _param("model", "모델명 (정확히 일치)"),
        _param("site_type", "사이트 구분", enum=["encar", "kb", "kcar"]),
        _param("year", "연식 (부분 일치)"),
        _param("price_min", "최소 가격 (만원)", kind="integer"),
        _param("price_max", "최대 가격 (만원)", kind="integer"),
        _param("created_at_from", "Hub 저장일 시작 YYYY-MM-DD (증분 동기화)", format="date"),
        _param("created_at_to", "Hub 저장일 끝 YYYY-MM-DD", format="date"),
        _param("fuel", "연료 (car_fuel 도 허용, 휘발유 등 별칭 정규화)"),
    ]


def _ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def _json(description: str, schema: dict) -> dict:
    return {"description": description, "content": {"application/json": {"schema": schema}}}


def api_base_url() -> str:
    return f"{request.host_url.rstrip('/')}/api/v1"


def vehicle_openapi_spec() -> dict:
    props = {}
    for name in RESPONSE_FIELDS:
        kind = "integer" if name in _INTEGER_FIELDS else "string"
        props[name] = {"type": kind, "nullable": name != "db_id", "description": FIELD_DESCRIPTIONS[name]}
    props["price_unit"]["example"] = "만원"
    unauthorized = _json("API 키 없음 또는 폐기됨", _ref("Error"))
    include = _param("include", "text면 긴 텍스트 필드 포함", enum=["text"])
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Vehicle Data Hub API",
            "version": "1.0.0",
            "description": (
                "관리자 > API 명세서·키 발급에서 받은 API 키로 차량 매물을 조회합니다. "
                "읽기 전용(GET)이며 가격 단위는 만원입니다."
            ),
        },
        "servers": [{"url": api_base_url()}],
        "paths": {
            "/vehicles": {
                "get": {
                    "summary": "차량 목록",
                    "description": "필터·페이지로 차량을 조회합니다. 증분 동기화는 created_at_from을 씁니다.",
                    "parameters": _list_params(),
                    "responses": {"200": _json("목록", _ref("VehicleList")), "401": unauthorized},
                }
            },
            "/vehicles/search": {
                "get": {
                    "summary": "차량 검색",
                    "description": "차량번호·제조사·모델·연료 부분 일치, 최대 50건.",
                    "parameters": [_param("q", "검색어 (없으면 빈 목록)"), include],
                    "responses": {"200": _json("검색 결과", _ref("VehicleSearch")), "401": unauthorized},
                }
            },
            "/vehicles/{vehicle_id}": {
                "get": {
                    "summary": "차량 상세",
                    "description": "목록 응답의 db_id로 조회합니다. 긴 텍스트 필드를 항상 포함합니다.",
                    "parameters": [
                        _param("vehicle_id", "목록 응답의 db_id", kind="integer", location="path", required=True)
                    ],
                    "responses": {
                        "200": _json("상세", _ref("Vehicle")),
                        "401": unauthorized,
                        "404": _json("없는 db_id", _ref("Error")),
                    },
                }
            },
        },
        "components": {
            "securitySchemes": {
                "ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                "Bearer": {"type": "http", "scheme": "bearer"},
            },
            "schemas": {
                "Vehicle": {
                    "type": "object",
                    "properties": props,
                    "description": "긴 텍스트 " + ", ".join(_TEXT_FIELDS) + " 는 include=text 또는 상세에서만 포함",
                },
                "VehicleList": {
                    "type": "object",
                    "properties": {
                        "price_unit": {"type": "string", "example": "만원"},
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "total": {"type": "integer", "description": "필터 없으면 추정치"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "items": {"type": "array", "items": _ref("Vehicle")},
                    },
                },
                "VehicleSearch": {
                    "type": "object",
                    "properties": {
                        "price_unit": {"type": "string", "example": "만원"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "items": {"type": "array", "items": _ref("Vehicle")},
                    },
                },
                "Error": {
                    "type": "object",
                    "properties": {"error": {"type": "string"}, "message": {"type": "string"}},
                },
            },
        },
        "security": [{"ApiKey": []}, {"Bearer": []}],
    }


def spec_context() -> dict:
    return {
        "spec": vehicle_openapi_spec(),
        "base_url": api_base_url(),
        "fields": [(name, FIELD_DESCRIPTIONS[name], name in _TEXT_FIELDS) for name in RESPONSE_FIELDS],
    }


def api_spec_markdown() -> str:
    return render_template("api_spec.md", **spec_context())
