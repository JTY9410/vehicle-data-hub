from flask import request

from apps.routes.api import VEHICLE_FIELDS, _TEXT_FIELDS


def vehicle_openapi_spec() -> dict:
    props = {name: {"type": "string", "nullable": True} for name in VEHICLE_FIELDS}
    props["car_km"] = {"type": "integer", "nullable": True}
    props["car_price"] = {"type": "integer", "nullable": True, "description": "만원"}
    props["db_id"] = {"type": "integer"}
    props["price_unit"] = {"type": "string", "example": "만원"}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Vehicle Data Hub API",
            "version": "1.0.0",
            "description": "관리자에서 발급한 API 키로 차량 매물을 조회합니다.",
        },
        "servers": [{"url": f"{request.host_url.rstrip('/')}/api/v1"}],
        "paths": {
            "/vehicles": {
                "get": {
                    "summary": "차량 목록",
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "include", "in": "query", "schema": {"type": "string", "enum": ["text"]}},
                    ],
                    "responses": {"200": {"description": "목록"}},
                }
            },
            "/vehicles/search": {
                "get": {
                    "summary": "차량 검색",
                    "parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "검색 결과"}},
                }
            },
            "/vehicles/{vehicle_id}": {
                "get": {
                    "summary": "차량 상세",
                    "parameters": [
                        {"name": "vehicle_id", "in": "path", "required": True, "schema": {"type": "integer"}}
                    ],
                    "responses": {"200": {"description": "상세"}},
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
                }
            },
        },
        "security": [{"ApiKey": []}, {"Bearer": []}],
    }
