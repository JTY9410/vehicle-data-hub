from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from apps.extensions import db
from apps.models import (
    VehicleGrade,
    VehicleGradeDetail,
    VehicleMaker,
    VehicleModel,
    VehicleModelDetail,
)

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "encar_codes"
BATCH = 500


def _disable_statement_timeout() -> None:
    try:
        db.session.execute(text("SET statement_timeout = 0"))
        db.session.commit()
    except Exception:  # noqa: BLE001
        db.session.rollback()


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


def _flush_upsert(table, rows: list[dict], conflict_col: str, update_cols: list[str]) -> None:
    if not rows:
        return
    stmt = insert(table).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[conflict_col],
        set_={c: stmt.excluded[c] for c in update_cols},
    )
    db.session.execute(stmt)
    db.session.commit()


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

    # Supabase pooler 기본 statement_timeout 회피 (대량 upsert)
    _disable_statement_timeout()

    batch: list[dict] = []
    with (root / "vehicle_maker.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            maker_no = (row.get("maker_no") or "").strip()
            maker_name = (row.get("maker_name") or "").strip()
            if not maker_no or not maker_name:
                continue
            batch.append(
                {
                    "maker_no": maker_no,
                    "maker_name": maker_name,
                    "sort_no": _int_or_none(row.get("sort_no")),
                }
            )
            counts["makers"] += 1
            if len(batch) >= BATCH:
                _flush_upsert(
                    VehicleMaker.__table__,
                    batch,
                    "maker_no",
                    ["maker_name", "sort_no"],
                )
                batch = []
                _disable_statement_timeout()
    _flush_upsert(VehicleMaker.__table__, batch, "maker_no", ["maker_name", "sort_no"])
    batch = []

    with (root / "vehicle_model.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            model_no = (row.get("model_no") or "").strip()
            model_name = (row.get("model_name") or "").strip()
            if not model_no or not model_name:
                continue
            batch.append(
                {
                    "model_no": model_no,
                    "maker_no": (row.get("maker_no") or "").strip() or None,
                    "model_name": model_name,
                    "sort_no": _int_or_none(row.get("sort_no")),
                }
            )
            counts["models"] += 1
            if len(batch) >= BATCH:
                _flush_upsert(
                    VehicleModel.__table__,
                    batch,
                    "model_no",
                    ["maker_no", "model_name", "sort_no"],
                )
                batch = []
                _disable_statement_timeout()
    _flush_upsert(
        VehicleModel.__table__,
        batch,
        "model_no",
        ["maker_no", "model_name", "sort_no"],
    )
    batch = []

    with (root / "vehicle_model_detail.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            mdetail_no = (row.get("mdetail_no") or "").strip()
            mdetail_name = (row.get("mdetail_name") or "").strip()
            if not mdetail_no or not mdetail_name:
                continue
            batch.append(
                {
                    "mdetail_no": mdetail_no,
                    "model_no": (row.get("model_no") or "").strip() or None,
                    "mdetail_name": mdetail_name,
                    "sort_no": _int_or_none(row.get("sort_no")),
                    "st_year": _int_or_none(row.get("st_year")),
                    "ed_year": _int_or_none(row.get("ed_year")),
                }
            )
            counts["mdetails"] += 1
            if len(batch) >= BATCH:
                _flush_upsert(
                    VehicleModelDetail.__table__,
                    batch,
                    "mdetail_no",
                    ["model_no", "mdetail_name", "sort_no", "st_year", "ed_year"],
                )
                batch = []
                _disable_statement_timeout()
    _flush_upsert(
        VehicleModelDetail.__table__,
        batch,
        "mdetail_no",
        ["model_no", "mdetail_name", "sort_no", "st_year", "ed_year"],
    )
    batch = []

    with (root / "vehicle_grade.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            grade_no = (row.get("grade_no") or "").strip()
            grade_name = (row.get("grade_name") or "").strip()
            if not grade_no or not grade_name:
                continue
            batch.append(
                {
                    "grade_no": grade_no,
                    "mdetail_no": (row.get("mdetail_no") or "").strip() or None,
                    "grade_name": grade_name,
                    "sort_no": _int_or_none(row.get("sort_no")),
                }
            )
            counts["grades"] += 1
            if len(batch) >= BATCH:
                _flush_upsert(
                    VehicleGrade.__table__,
                    batch,
                    "grade_no",
                    ["mdetail_no", "grade_name", "sort_no"],
                )
                batch = []
                _disable_statement_timeout()
    _flush_upsert(
        VehicleGrade.__table__,
        batch,
        "grade_no",
        ["mdetail_no", "grade_name", "sort_no"],
    )
    batch = []

    with (root / "vehicle_grade_detail.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            gdetail_no = (row.get("gdetail_no") or "").strip()
            gdetail_name = (row.get("gdetail_name") or "").strip()
            if not gdetail_no or not gdetail_name:
                continue
            batch.append(
                {
                    "gdetail_no": gdetail_no,
                    "grade_no": (row.get("grade_no") or "").strip() or None,
                    "gdetail_name": gdetail_name,
                    "sort_no": _int_or_none(row.get("sort_no")),
                }
            )
            counts["gdetails"] += 1
            if len(batch) >= BATCH:
                _flush_upsert(
                    VehicleGradeDetail.__table__,
                    batch,
                    "gdetail_no",
                    ["grade_no", "gdetail_name", "sort_no"],
                )
                batch = []
                _disable_statement_timeout()
    _flush_upsert(
        VehicleGradeDetail.__table__,
        batch,
        "gdetail_no",
        ["grade_no", "gdetail_name", "sort_no"],
    )

    from apps.services.encar_codes import clear_code_index

    clear_code_index()
    return counts
