from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import tuple_

from apps.extensions import db
from apps.models import ImportJob, Vehicle, utcnow
from apps.services.filters import parse_km, parse_price_manwon, should_reject_row

CHUNK_SIZE = 1000


def _parse_scraped_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _apply_row(vehicle: Vehicle, row: dict, scraped_at: datetime | None, price: int) -> None:
    vehicle.car_no = row.get("car_no") or None
    vehicle.car_year = row.get("car_year") or None
    vehicle.car_km = parse_km(row.get("car_km"))
    vehicle.car_price = price
    vehicle.car_maker = row.get("car_maker") or None
    vehicle.car_model = row.get("car_model") or None
    vehicle.car_submodel = row.get("car_submodel") or None
    vehicle.car_grade = row.get("car_grade") or None
    vehicle.car_subgrade = row.get("car_subgrade") or None
    vehicle.car_fuel = row.get("car_fuel") or None
    vehicle.car_mission = row.get("car_mission") or None
    vehicle.car_color = row.get("car_color") or None
    vehicle.car_location = row.get("car_location") or None
    vehicle.car_import_yn = row.get("car_import_yn") or None
    vehicle.car_cc = row.get("car_cc") or None
    vehicle.car_type = row.get("car_type") or None
    vehicle.car_seat = row.get("car_seat") or None
    vehicle.detail_info = row.get("detail_info") or None
    vehicle.option_info = row.get("option_info") or None
    vehicle.diag_info = row.get("diag_info") or None
    vehicle.url_link = row.get("url_link") or None
    vehicle.scraped_at = scraped_at
    vehicle.updated_at = utcnow()


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
        if existing_ts is not None and (incoming_ts is None or incoming_ts <= existing_ts):
            job.skipped_rows += 1
        else:
            _apply_row(existing, item["row"], item["scraped_at"], item["price"])
            job.saved_rows += 1

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
                        "scraped_at": _parse_scraped_at(row.get("created_at")),
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
