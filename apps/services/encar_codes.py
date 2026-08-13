"""CSV 명칭 → 엔카 차량코드(maker/model/mdetail/grade/gdetail) 매핑."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from apps.extensions import db
from apps.models import (
    Vehicle,
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)

_NULLISH = {"", "null", "none", "없음", "-", "NULL"}
_JACCARD_MIN = 0.72

MAKER_ALIASES = {
    "쌍용": "KG모빌리티(쌍용)",
    "KG모빌리티": "KG모빌리티(쌍용)",
    "삼성": "르노(삼성)",
    "르노삼성": "르노(삼성)",
    "르노코리아": "르노(삼성)",
    "르노코리아(삼성)": "르노(삼성)",
    "GM대우": "쉐보레(대우)",
    "대우": "쉐보레(대우)",
    "한국GM": "쉐보레",
    "쉐보레(GM대우)": "쉐보레(대우)",
    "현대자동차": "현대",
    "기아자동차": "기아",
    "기아차": "기아",
    "도요타": "토요타",
    "토요타자동차": "토요타",
    "시트로엥/DS": "시트로엥",
    "시트로엔": "시트로엥",
    "시트로엔/DS": "시트로엥",
    "DS": "시트로엥",
}


def _clean(value: str | None) -> str:
    text = (value or "").strip()
    return "" if text.lower() in _NULLISH or text in _NULLISH else text


def normalize_label(value: str | None) -> str:
    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"（[^）]*）", " ", text)
    text = re.sub(r"(?i)\b(FWD|AWD|4WD|2WD|4x4|4×4|WD)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(value: str | None) -> set[str]:
    text = normalize_label(value).casefold()
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9.]+|[가-힣]+", text))


def _match_from_list(items: list[tuple[str, str]], query: str) -> str | None:
    """items: (pk, name) list."""
    raw = _clean(query)
    if not raw or not items:
        return None
    norm = normalize_label(raw)
    for pk, name in items:
        if normalize_label(name) == norm or _clean(name) == raw:
            return pk
    qt = _tokens(raw)
    best_pk, best_score = None, 0.0
    for pk, name in items:
        rt = _tokens(name)
        score = len(qt & rt) / len(qt | rt) if qt and rt else 0.0
        if score > best_score:
            best_score, best_pk = score, pk
    if best_pk and best_score >= _JACCARD_MIN:
        return best_pk
    return None


@dataclass
class EncarCodeIndex:
    makers: list[tuple[str, str]] = field(default_factory=list)
    models_by_maker: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    mdetails_by_model: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    grades_by_mdetail: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    gdetails_by_grade: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "EncarCodeIndex":
        idx = cls()
        makers = db.session.execute(db.select(VehicleMaker)).scalars().all()
        idx.makers = [(m.maker_no, m.maker_name) for m in makers]

        models = db.session.execute(db.select(VehicleModel)).scalars().all()
        for m in models:
            if not m.maker_no:
                continue
            idx.models_by_maker.setdefault(m.maker_no, []).append((m.model_no, m.model_name))

        mdetails = db.session.execute(db.select(VehicleModelDetail)).scalars().all()
        for m in mdetails:
            if not m.model_no:
                continue
            idx.mdetails_by_model.setdefault(m.model_no, []).append(
                (m.mdetail_no, m.mdetail_name)
            )

        grades = db.session.execute(db.select(VehicleGrade)).scalars().all()
        for g in grades:
            if not g.mdetail_no:
                continue
            idx.grades_by_mdetail.setdefault(g.mdetail_no, []).append(
                (g.grade_no, g.grade_name)
            )

        gdetails = db.session.execute(db.select(VehicleGradeDetail)).scalars().all()
        for g in gdetails:
            if not g.grade_no:
                continue
            idx.gdetails_by_grade.setdefault(g.grade_no, []).append(
                (g.gdetail_no, g.gdetail_name)
            )
        return idx

    def resolve(
        self,
        *,
        car_maker: str | None,
        car_model: str | None,
        car_submodel: str | None,
        car_grade: str | None,
        car_subgrade: str | None,
    ) -> dict[str, str | None]:
        out = {
            "maker_no": None,
            "model_no": None,
            "mdetail_no": None,
            "grade_no": None,
            "gdetail_no": None,
        }
        maker_name = MAKER_ALIASES.get(_clean(car_maker), _clean(car_maker))
        maker_no = _match_from_list(self.makers, maker_name)
        if not maker_no:
            return out
        out["maker_no"] = maker_no

        models = self.models_by_maker.get(maker_no, [])
        model_no = _match_from_list(models, car_model or "")
        if not model_no:
            return out
        out["model_no"] = model_no

        mdetails = self.mdetails_by_model.get(model_no, [])
        mdetail_no = None
        if _clean(car_submodel):
            mdetail_no = _match_from_list(mdetails, car_submodel)
        if not mdetail_no and len(mdetails) == 1:
            mdetail_no = mdetails[0][0]
        out["mdetail_no"] = mdetail_no

        grades: list[tuple[str, str]] = []
        if mdetail_no:
            grades = self.grades_by_mdetail.get(mdetail_no, [])
        else:
            for md_no, _ in mdetails:
                grades.extend(self.grades_by_mdetail.get(md_no, []))
        grade_no = None
        if _clean(car_grade):
            grade_no = _match_from_list(grades, car_grade)
        out["grade_no"] = grade_no

        if grade_no and _clean(car_subgrade):
            gdetails = self.gdetails_by_grade.get(grade_no, [])
            out["gdetail_no"] = _match_from_list(gdetails, car_subgrade)
        return out


_INDEX: EncarCodeIndex | None = None


def get_code_index(*, force_reload: bool = False) -> EncarCodeIndex:
    global _INDEX
    if _INDEX is None or force_reload:
        _INDEX = EncarCodeIndex.load()
    return _INDEX


def clear_code_index() -> None:
    global _INDEX
    _INDEX = None


def resolve_csv_to_codes(
    *,
    car_maker: str | None,
    car_model: str | None,
    car_submodel: str | None,
    car_grade: str | None,
    car_subgrade: str | None,
    index: EncarCodeIndex | None = None,
) -> dict[str, str | None]:
    idx = index or get_code_index()
    return idx.resolve(
        car_maker=car_maker,
        car_model=car_model,
        car_submodel=car_submodel,
        car_grade=car_grade,
        car_subgrade=car_subgrade,
    )


def apply_codes_to_vehicle(
    vehicle: Vehicle, index: EncarCodeIndex | None = None
) -> dict[str, str | None]:
    codes = resolve_csv_to_codes(
        car_maker=vehicle.car_maker,
        car_model=vehicle.car_model,
        car_submodel=vehicle.car_submodel,
        car_grade=vehicle.car_grade,
        car_subgrade=vehicle.car_subgrade,
        index=index,
    )
    vehicle.maker_no = codes["maker_no"]
    vehicle.model_no = codes["model_no"]
    vehicle.mdetail_no = codes["mdetail_no"]
    vehicle.grade_no = codes["grade_no"]
    vehicle.gdetail_no = codes["gdetail_no"]
    return codes


def remap_all_vehicles(chunk_size: int = 500) -> dict[str, int]:
    clear_code_index()
    index = get_code_index(force_reload=True)
    total = mapped = 0
    last_id = 0
    while True:
        rows = db.session.execute(
            db.select(Vehicle)
            .where(Vehicle.id > last_id)
            .order_by(Vehicle.id)
            .limit(chunk_size)
        ).scalars().all()
        if not rows:
            break
        for v in rows:
            total += 1
            codes = apply_codes_to_vehicle(v, index=index)
            if codes["maker_no"]:
                mapped += 1
            last_id = v.id
        db.session.commit()
    return {"total": total, "mapped_maker": mapped}
