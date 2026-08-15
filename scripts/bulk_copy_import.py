"""로컬에서 CSV를 걸러 한 연결로 COPY. Flask/ORM/풀러 점유를 피한다."""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.services.encar_codes import EncarCodeIndex  # noqa: E402
from apps.services.filters import parse_km, parse_price_manwon, should_reject_row  # noqa: E402
from apps.services.import_csv import _clean, csv_row_saved_at  # noqa: E402
from config import (  # noqa: E402
    _ensure_pooler_username,
    _normalize_database_url,
    _prefer_supabase_pooler,
)

SEED_DIR = ROOT / "data" / "encar_codes"
COLS = (
    "source_id",
    "site_type",
    "site_id",
    "car_no",
    "car_year",
    "car_km",
    "car_price",
    "car_maker",
    "car_model",
    "car_submodel",
    "car_grade",
    "car_subgrade",
    "car_fuel",
    "car_mission",
    "car_color",
    "car_location",
    "car_import_yn",
    "car_cc",
    "car_type",
    "car_seat",
    "detail_info",
    "option_info",
    "diag_info",
    "url_link",
    "scraped_at",
    "maker_no",
    "model_no",
    "mdetail_no",
    "grade_no",
    "gdetail_no",
    "created_at",
    "updated_at",
)


def _db_url(*, transaction_pooler: bool = True) -> str:
    load_dotenv(ROOT / ".env")
    raw = os.environ["DATABASE_URL"]
    url = _ensure_pooler_username(_prefer_supabase_pooler(_normalize_database_url(raw)))
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    if transaction_pooler:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(url)
        url = urlunsplit(
            (parts.scheme, parts.netloc.replace(":5432", ":6543"), parts.path, parts.query, parts.fragment)
        )
    return url


def _load_index() -> EncarCodeIndex:
    idx = EncarCodeIndex()
    with (SEED_DIR / "vehicle_maker.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            no, name = (row.get("maker_no") or "").strip(), (row.get("maker_name") or "").strip()
            if no and name:
                idx.makers.append((no, name))
    with (SEED_DIR / "vehicle_model.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            no, name = (row.get("model_no") or "").strip(), (row.get("model_name") or "").strip()
            maker = (row.get("maker_no") or "").strip()
            if no and name and maker:
                idx.models_by_maker.setdefault(maker, []).append((no, name))
    with (SEED_DIR / "vehicle_model_detail.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            no, name = (row.get("mdetail_no") or "").strip(), (row.get("mdetail_name") or "").strip()
            model = (row.get("model_no") or "").strip()
            if no and name and model:
                idx.mdetails_by_model.setdefault(model, []).append((no, name))
    with (SEED_DIR / "vehicle_grade.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            no, name = (row.get("grade_no") or "").strip(), (row.get("grade_name") or "").strip()
            md = (row.get("mdetail_no") or "").strip()
            if no and name and md:
                idx.grades_by_mdetail.setdefault(md, []).append((no, name))
    with (SEED_DIR / "vehicle_grade_detail.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            no, name = (row.get("gdetail_no") or "").strip(), (row.get("gdetail_name") or "").strip()
            grade = (row.get("grade_no") or "").strip()
            if no and name and grade:
                idx.gdetails_by_grade.setdefault(grade, []).append((no, name))
    return idx


def _row_tuple(row: dict, price: int, idx: EncarCodeIndex, now: datetime) -> tuple:
    codes = idx.resolve(
        car_maker=_clean(row.get("car_maker")),
        car_model=_clean(row.get("car_model")),
        car_submodel=_clean(row.get("car_submodel")),
        car_grade=_clean(row.get("car_grade")),
        car_subgrade=_clean(row.get("car_subgrade")),
    )
    return (
        _clean(row.get("id")),
        (row.get("site_type") or "").strip(),
        str(row.get("site_id") or "").strip(),
        _clean(row.get("car_no")),
        _clean(row.get("car_year")),
        parse_km(row.get("car_km")),
        price,
        _clean(row.get("car_maker")),
        _clean(row.get("car_model")),
        _clean(row.get("car_submodel")),
        _clean(row.get("car_grade")),
        _clean(row.get("car_subgrade")),
        _clean(row.get("car_fuel")),
        _clean(row.get("car_mission")),
        _clean(row.get("car_color")),
        _clean(row.get("car_location")),
        _clean(row.get("car_import_yn")),
        _clean(row.get("car_cc")),
        _clean(row.get("car_type")),
        _clean(row.get("car_seat")),
        _clean(row.get("detail_info")),
        _clean(row.get("option_info")),
        _clean(row.get("diag_info")),
        _clean(row.get("url_link")),
        csv_row_saved_at(row),
        codes["maker_no"],
        codes["model_no"],
        codes["mdetail_no"],
        codes["grade_no"],
        codes["gdetail_no"],
        now,
        now,
    )


def collect_rows(path: Path, idx: EncarCodeIndex) -> dict[tuple[str, str], tuple]:
    now = datetime.now(timezone.utc)
    out: dict[tuple[str, str], tuple] = {}
    rejected = 0
    n = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            n += 1
            if n % 100000 == 0:
                print(f"  parse {path.name}: {n} rows, keep={len(out)} reject={rejected}", flush=True)
            site_type = (row.get("site_type") or "").strip()
            site_id = str(row.get("site_id") or "").strip()
            reject, _ = should_reject_row(row.get("car_no"), row.get("car_price"), site_type, site_id)
            if reject:
                rejected += 1
                continue
            price = parse_price_manwon(row.get("car_price"))
            assert price is not None
            key = (site_type, site_id)
            incoming = csv_row_saved_at(row)
            prev = out.get(key)
            if prev is not None:
                prev_ts = prev[24]
                if prev_ts is not None and (incoming is None or incoming <= prev_ts):
                    continue
            out[key] = _row_tuple(row, price, idx, now)
    print(f"  parse done {path.name}: read={n} keep={len(out)} reject={rejected}", flush=True)
    return out


_INSERT_SQL = (
    f"INSERT INTO vehicles ({', '.join(COLS)}) VALUES ({', '.join(['%s'] * len(COLS))}) "
    f"ON CONFLICT (site_type, site_id) DO UPDATE SET "
    + ", ".join(f"{c}=EXCLUDED.{c}" for c in COLS if c not in ("site_type", "site_id", "created_at"))
    + " WHERE vehicles.scraped_at IS NULL OR EXCLUDED.scraped_at IS NULL "
    "OR EXCLUDED.scraped_at > vehicles.scraped_at"
)
BATCH = 200


def upsert_batches(conn: psycopg.Connection, rows: list[tuple]) -> None:
    total = len(rows)
    for i in range(0, total, BATCH):
        chunk = rows[i : i + BATCH]
        with conn.cursor() as cur:
            cur.executemany(_INSERT_SQL, chunk)
        conn.commit()
        done = min(i + BATCH, total)
        if done % 2000 == 0 or done == total:
            print(f"  upsert {done}/{total}", flush=True)


def main() -> int:
    files = [Path(p) for p in sys.argv[1:]] or [
        ROOT / "uploads" / "20260730_.csv",
        ROOT / "uploads" / "20260813__7.csv",
    ]
    print("load encar index from local csv", flush=True)
    idx = _load_index()
    print(f"makers={len(idx.makers)}", flush=True)

    batches = [collect_rows(p, idx) for p in files]
    total = sum(len(b) for b in batches)
    print(f"ready to write ~{total} unique keys", flush=True)

    print("connect transaction pooler", flush=True)
    with psycopg.connect(
        _db_url(transaction_pooler=True),
        sslmode="require",
        connect_timeout=15,
        prepare_threshold=None,
        autocommit=False,
        options="-c statement_timeout=0",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM vehicle_maker")
            makers = cur.fetchone()[0]
            print(f"db makers={makers}", flush=True)
            if makers == 0:
                print("encar codes missing; abort", flush=True)
                return 1

        for i, batch in enumerate(batches):
            rows = list(batch.values())
            print(f"UPSERT file {i + 1}: {len(rows)} rows", flush=True)
            upsert_batches(conn, rows)
            print(f"file {i + 1} committed", flush=True)

        with conn.cursor() as cur:
            cur.execute("SELECT reltuples::bigint FROM pg_class WHERE relname='vehicles'")
            print(f"done vehicles_est={cur.fetchone()[0]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
