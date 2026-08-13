from __future__ import annotations

import csv
from pathlib import Path

from apps.extensions import db
from apps.models import (
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "encar_codes"


def _int_or_none(raw: str | None) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def seed_encar_codes(seed_dir: Path | None = None) -> dict[str, int]:
    """엔카(car2) 차량코드 CSV를 DB에 upsert 적재."""
    root = seed_dir or SEED_DIR
    counts = {
        "makers": 0,
        "models": 0,
        "mdetails": 0,
        "grades": 0,
        "gdetails": 0,
    }

    with (root / "vehicle_maker.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            maker_no = (row.get("maker_no") or "").strip()
            maker_name = (row.get("maker_name") or "").strip()
            if not maker_no or not maker_name:
                continue
            obj = db.session.get(VehicleMaker, maker_no) or VehicleMaker(maker_no=maker_no)
            obj.maker_name = maker_name
            obj.sort_no = _int_or_none(row.get("sort_no"))
            db.session.merge(obj)
            counts["makers"] += 1

    with (root / "vehicle_model.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            model_no = (row.get("model_no") or "").strip()
            model_name = (row.get("model_name") or "").strip()
            if not model_no or not model_name:
                continue
            obj = db.session.get(VehicleModel, model_no) or VehicleModel(model_no=model_no)
            obj.maker_no = (row.get("maker_no") or "").strip() or None
            obj.model_name = model_name
            obj.sort_no = _int_or_none(row.get("sort_no"))
            db.session.merge(obj)
            counts["models"] += 1

    with (root / "vehicle_model_detail.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mdetail_no = (row.get("mdetail_no") or "").strip()
            mdetail_name = (row.get("mdetail_name") or "").strip()
            if not mdetail_no or not mdetail_name:
                continue
            obj = db.session.get(VehicleModelDetail, mdetail_no) or VehicleModelDetail(
                mdetail_no=mdetail_no
            )
            obj.model_no = (row.get("model_no") or "").strip() or None
            obj.mdetail_name = mdetail_name
            obj.sort_no = _int_or_none(row.get("sort_no"))
            obj.st_year = _int_or_none(row.get("st_year"))
            obj.ed_year = _int_or_none(row.get("ed_year"))
            db.session.merge(obj)
            counts["mdetails"] += 1

    with (root / "vehicle_grade.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            grade_no = (row.get("grade_no") or "").strip()
            grade_name = (row.get("grade_name") or "").strip()
            if not grade_no or not grade_name:
                continue
            obj = db.session.get(VehicleGrade, grade_no) or VehicleGrade(grade_no=grade_no)
            obj.mdetail_no = (row.get("mdetail_no") or "").strip() or None
            obj.grade_name = grade_name
            obj.sort_no = _int_or_none(row.get("sort_no"))
            db.session.merge(obj)
            counts["grades"] += 1

    with (root / "vehicle_grade_detail.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            gdetail_no = (row.get("gdetail_no") or "").strip()
            gdetail_name = (row.get("gdetail_name") or "").strip()
            if not gdetail_no or not gdetail_name:
                continue
            obj = db.session.get(VehicleGradeDetail, gdetail_no) or VehicleGradeDetail(
                gdetail_no=gdetail_no
            )
            obj.grade_no = (row.get("grade_no") or "").strip() or None
            obj.gdetail_name = gdetail_name
            obj.sort_no = _int_or_none(row.get("sort_no"))
            db.session.merge(obj)
            counts["gdetails"] += 1

    db.session.commit()
    from apps.services.encar_codes import clear_code_index

    clear_code_index()
    return counts
