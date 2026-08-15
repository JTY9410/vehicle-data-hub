from __future__ import annotations

import csv
from datetime import date, datetime, time, timezone
from pathlib import Path

from sqlalchemy import text, tuple_

from apps.extensions import db
from apps.models import ImportJob, Vehicle, utcnow
from apps.services.encar_codes import apply_codes_to_vehicle
from apps.services.filters import parse_km, parse_price_manwon, should_reject_row

CHUNK_SIZE = 1000

# CSV 저장일자 컬럼 후보 (우선순위)
_CSV_SAVED_AT_KEYS = ("created_at", "saved_at", "저장일자", "scraped_at")


def parse_csv_saved_at(raw: str | None) -> datetime | None:
    """CSV 저장일자(created_at 등) → timezone-aware UTC datetime."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.upper() == "NULL":
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = None
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d %H:%M:%S",
            "%Y.%m.%d",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_scraped_at(raw: str | None) -> datetime | None:
    return parse_csv_saved_at(raw)


def csv_row_saved_at(row: dict) -> datetime | None:
    for key in _CSV_SAVED_AT_KEYS:
        if key in row and row.get(key) not in (None, ""):
            parsed = parse_csv_saved_at(row.get(key))
            if parsed is not None:
                return parsed
    return None


def parse_date_bound(raw: str | None, *, end_of_day: bool = False) -> datetime | None:
    """YYYY-MM-DD 또는 datetime 문자열 → UTC 경계."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            d = date.fromisoformat(s)
        except ValueError:
            return None
        t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
        return datetime.combine(d, t, tzinfo=timezone.utc)
    return parse_csv_saved_at(s)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.upper() == "NULL":
        return None
    return s


def _apply_row(vehicle: Vehicle, row: dict, scraped_at: datetime | None, price: int) -> None:
    vehicle.source_id = _clean(row.get("id"))
    vehicle.car_no = _clean(row.get("car_no"))
    vehicle.car_year = _clean(row.get("car_year"))
    vehicle.car_km = parse_km(row.get("car_km"))
    vehicle.car_price = price
    vehicle.car_maker = _clean(row.get("car_maker"))
    vehicle.car_model = _clean(row.get("car_model"))
    vehicle.car_submodel = _clean(row.get("car_submodel"))
    vehicle.car_grade = _clean(row.get("car_grade"))
    vehicle.car_subgrade = _clean(row.get("car_subgrade"))
    vehicle.car_fuel = _clean(row.get("car_fuel"))
    vehicle.car_mission = _clean(row.get("car_mission"))
    vehicle.car_color = _clean(row.get("car_color"))
    vehicle.car_location = _clean(row.get("car_location"))
    vehicle.car_import_yn = _clean(row.get("car_import_yn"))
    vehicle.car_cc = _clean(row.get("car_cc"))
    vehicle.car_type = _clean(row.get("car_type"))
    vehicle.car_seat = _clean(row.get("car_seat"))
    vehicle.detail_info = _clean(row.get("detail_info"))
    vehicle.option_info = _clean(row.get("option_info"))
    vehicle.diag_info = _clean(row.get("diag_info"))
    vehicle.url_link = _clean(row.get("url_link"))
    vehicle.scraped_at = scraped_at
    vehicle.updated_at = utcnow()
    apply_codes_to_vehicle(vehicle)


def _flush_chunk(job: ImportJob, pending: list[dict]) -> None:
    if not pending:
        return
    keys = [(p["site_type"], p["site_id"]) for p in pending]
    existing_rows = db.session.execute(
        db.select(Vehicle).where(tuple_(Vehicle.site_type, Vehicle.site_id).in_(keys))
    ).scalars().all()
    existing_map = {(v.site_type, v.site_id): v for v in existing_rows}

    for item in pending:
        key = (item["site_type"], item["site_id"])
        existing = existing_map.get(key)
        if existing is None:
            vehicle = Vehicle(site_type=item["site_type"], site_id=item["site_id"])
            _apply_row(vehicle, item["row"], item["scraped_at"], item["price"])
            db.session.add(vehicle)
            existing_map[key] = vehicle
            job.saved_rows += 1
            continue

        existing_ts = existing.scraped_at
        incoming_ts = item["scraped_at"]
        newer = existing_ts is None or (
            incoming_ts is not None and incoming_ts > existing_ts
        )
        needs_backfill = existing.source_id is None and _clean(item["row"].get("id"))
        if newer or needs_backfill:
            _apply_row(existing, item["row"], item["scraped_at"], item["price"])
            job.saved_rows += 1
        else:
            job.skipped_rows += 1

    db.session.commit()


def import_csv_file(path: str | Path, source: str, filename: str | None = None) -> ImportJob:
    path = Path(path)
    job = ImportJob(
        source=source,
        filename=filename or path.name,
        status="running",
        started_at=utcnow(),
    )
    db.session.add(job)
    db.session.commit()

    try:
        # Supabase 기본 statement_timeout 회피 (SQLite 테스트에서는 무시)
        try:
            db.session.execute(text("SET statement_timeout = 0"))
            db.session.commit()
        except Exception:  # noqa: BLE001
            db.session.rollback()
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            pending: list[dict] = []
            for row in reader:
                job.total_rows += 1
                job.processed_rows += 1
                site_type = (row.get("site_type") or "").strip()
                site_id = str(row.get("site_id") or "").strip()
                car_no = row.get("car_no")
                reject, _reason = should_reject_row(
                    car_no, row.get("car_price"), site_type, site_id
                )
                if reject:
                    job.rejected_rows += 1
                    if job.processed_rows % CHUNK_SIZE == 0:
                        db.session.commit()
                    continue

                price = parse_price_manwon(row.get("car_price"))
                assert price is not None
                pending.append(
                    {
                        "site_type": site_type,
                        "site_id": site_id,
                        "row": row,
                        "scraped_at": csv_row_saved_at(row),
                        "price": price,
                    }
                )
                if len(pending) >= CHUNK_SIZE:
                    _flush_chunk(job, pending)
                    pending = []

            _flush_chunk(job, pending)

        job.status = "completed"
        job.finished_at = utcnow()
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        job = db.session.get(ImportJob, job.id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = utcnow()
            db.session.commit()
        raise

    return job
