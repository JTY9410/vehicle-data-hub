"""CSV 변속기·색상·차종 → 엔카 검색 표준명."""

from __future__ import annotations

import re

from sqlalchemy import update

ENCAR_MISSIONS = ("오토", "수동", "CVT", "세미오토")
ENCAR_TYPES = (
    "경차",
    "소형차",
    "준중형차",
    "중형차",
    "대형차",
    "스포츠카",
    "SUV",
    "RV",
    "승합",
    "화물",
)

_NULLISH = {"", "null", "none", "없음", "-", "NULL", "미선택"}

_MISSION_ALIASES = {
    "오토": "오토",
    "자동": "오토",
    "automatic": "오토",
    "at": "오토",
    "a/t": "오토",
    "auto": "오토",
    "dct": "오토",
    "dsg": "오토",
    "수동": "수동",
    "manual": "수동",
    "mt": "수동",
    "m/t": "수동",
    "cvt": "CVT",
    "무단변속기": "CVT",
    "무단": "CVT",
    "세미오토": "세미오토",
    "semi": "세미오토",
    "sat": "세미오토",
}

_COLOR_ALIASES = {
    "파란색": "청색",
    "파랑": "청색",
    "파랑색": "청색",
    "blue": "청색",
    "검정": "검정색",
    "검정색": "검정색",
    "검은색": "검정색",
    "black": "검정색",
    "빨강": "빨간색",
    "빨강색": "빨간색",
    "빨간색": "빨간색",
    "red": "빨간색",
    "흰색": "흰색",
    "하얀색": "흰색",
    "화이트": "흰색",
    "white": "흰색",
    "은색": "은색",
    "실버": "은색",
    "silver": "은색",
    "회색": "회색",
    "그레이": "회색",
    "gray": "회색",
    "grey": "회색",
}

_TYPE_ALIASES = {
    "경차": "경차",
    "소형차": "소형차",
    "소형": "소형차",
    "준중형차": "준중형차",
    "준중형": "준중형차",
    "중형차": "중형차",
    "중형": "중형차",
    "대형차": "대형차",
    "대형": "대형차",
    "스포츠카": "스포츠카",
    "스포츠": "스포츠카",
    "suv": "SUV",
    "rv": "RV",
    "rv/suv": "SUV",
    "suv/rv": "SUV",
    "승합": "승합",
    "승합차": "승합",
    "경승합차": "승합",
    "화물": "화물",
    "화물차": "화물",
}


def _clean(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() in _NULLISH or text in _NULLISH:
        return None
    return text


def _key(value: str) -> str:
    return re.sub(r"[\s]", "", value).casefold()


def _alias(raw: str | None, table: dict[str, str], allowed: tuple[str, ...] | None = None) -> str | None:
    text = _clean(raw)
    if not text:
        return None
    if allowed and text in allowed:
        return text
    mapped = table.get(_key(text))
    if mapped:
        return mapped
    return text


def normalize_mission(raw: str | None) -> str | None:
    return _alias(raw, _MISSION_ALIASES, ENCAR_MISSIONS)


def normalize_color(raw: str | None) -> str | None:
    return _alias(raw, _COLOR_ALIASES)


def normalize_type(raw: str | None) -> str | None:
    return _alias(raw, _TYPE_ALIASES, ENCAR_TYPES)


def remap_vehicle_attrs() -> dict[str, int]:
    from apps.extensions import db
    from apps.models import Vehicle

    changed = 0
    pairs = (
        (Vehicle.car_mission, normalize_mission),
        (Vehicle.car_color, normalize_color),
        (Vehicle.car_type, normalize_type),
    )
    for column, fn in pairs:
        distinct = db.session.execute(db.select(column).distinct()).scalars().all()
        for raw in distinct:
            canon = fn(raw)
            if not canon or canon == raw:
                continue
            result = db.session.execute(
                update(Vehicle).where(column == raw).values(**{column.key: canon})
            )
            changed += result.rowcount or 0
    db.session.commit()
    return {"updated": changed}
