"""CSV 유종 문자열 → 엔카 검색 표준명."""

from __future__ import annotations

import re

ENCAR_FUELS = (
    "가솔린",
    "디젤",
    "LPG",
    "하이브리드",
    "전기",
    "수소",
)

_NULLISH = {"", "null", "none", "없음", "-", "NULL"}

_ALIASES = {
    "가솔린": "가솔린",
    "휘발유": "가솔린",
    "가솔린유": "가솔린",
    "gasoline": "가솔린",
    "petrol": "가솔린",
    "디젤": "디젤",
    "경유": "디젤",
    "diesel": "디젤",
    "lpg": "LPG",
    "lpi": "LPG",
    "엘피지": "LPG",
    "하이브리드": "하이브리드",
    "hybrid": "하이브리드",
    "hev": "하이브리드",
    "phev": "하이브리드",
    "플러그인": "하이브리드",
    "플러그인하이브리드": "하이브리드",
    "가솔린하이브리드": "하이브리드",
    "디젤하이브리드": "하이브리드",
    "lpg하이브리드": "하이브리드",
    "가솔린+전기": "하이브리드",
    "디젤+전기": "하이브리드",
    "lpg+전기": "하이브리드",
    "가솔린전기": "하이브리드",
    "디젤전기": "하이브리드",
    "전기": "전기",
    "전기차": "전기",
    "ev": "전기",
    "electric": "전기",
    "cng": "CNG",
    "수소": "수소",
    "수소전기": "수소",
    "수소차": "수소",
    "hydrogen": "수소",
    "fcev": "수소",
}


def _key(value: str) -> str:
    return re.sub(r"[\s\-_/＋]", "", value).casefold()


def normalize_fuel(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in _NULLISH or text in _NULLISH:
        return None
    if text in ENCAR_FUELS:
        return text
    alias = _ALIASES.get(_key(text))
    if alias:
        return alias

    folded = text.casefold()
    if "수소" in text or "hydrogen" in folded or "fcev" in folded:
        return "수소"
    if (
        "하이브리드" in text
        or "hybrid" in folded
        or "phev" in folded
        or re.search(r"(?i)(?<![a-z])hev(?![a-z])", text)
    ):
        return "하이브리드"
    if "전기" in text and ("+" in text or "＋" in text):
        return "하이브리드"
    if (
        text in {"전기", "전기차"}
        or _key(text) in {"전기", "전기차", "ev", "electric"}
        or re.search(r"(?i)(?<![a-z0-9])ev(?![a-z0-9])", text)
    ):
        return "전기"
    if "cng" in folded or text == "CNG":
        return "CNG"
    if "디젤" in text or "경유" in text or "diesel" in folded:
        return "디젤"
    if "lpg" in folded or "lpi" in folded or "엘피지" in text:
        return "LPG"
    if "가솔린" in text or "휘발유" in text or "gasoline" in folded or "petrol" in folded:
        return "가솔린"
    return text


def infer_fuel(car_fuel: str | None, car_grade: str | None = None) -> str | None:
    """CSV 유종이 없거나 비표준이면 엔카 등급명에서 표준 유종을 채운다."""
    canon = normalize_fuel(car_fuel)
    if canon in ENCAR_FUELS:
        return canon
    from_grade = normalize_fuel(car_grade)
    if from_grade in ENCAR_FUELS:
        return from_grade
    return canon


def remap_vehicle_fuels() -> dict[str, int]:
    """기존 vehicles.car_fuel 를 엔카 표준명으로 일괄 치환."""
    from sqlalchemy import or_, update

    from apps.extensions import db
    from apps.models import Vehicle

    distinct = db.session.execute(db.select(Vehicle.car_fuel).distinct()).scalars().all()
    changed = 0
    scanned = 0
    for raw in distinct:
        scanned += 1
        canon = infer_fuel(raw)
        if not canon or canon == raw:
            continue
        result = db.session.execute(
            update(Vehicle).where(Vehicle.car_fuel == raw).values(car_fuel=canon)
        )
        changed += result.rowcount or 0

    leftovers = db.session.execute(
        db.select(Vehicle).where(
            or_(Vehicle.car_fuel.is_(None), Vehicle.car_fuel.notin_(list(ENCAR_FUELS)))
        )
    ).scalars().all()
    for vehicle in leftovers:
        inferred = infer_fuel(vehicle.car_fuel, vehicle.car_grade)
        if inferred and inferred != vehicle.car_fuel:
            vehicle.car_fuel = inferred
            changed += 1
    db.session.commit()
    return {"distinct": scanned, "updated": changed}
