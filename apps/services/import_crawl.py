from __future__ import annotations

from datetime import timezone

from apps.extensions import db
from apps.models import ImportJob, utcnow
from apps.services.crawl_client import DEFAULT_LIMIT, iter_crawling_rows
from apps.services.import_csv import import_row_dicts
from apps.services.settings import CRAWL_COLLECT_NOW, crawl_credentials, get_setting, set_setting

PAGE_DELAY_SECONDS = 1.0
STALE_IDLE_SECONDS = 45 * 60
STALE_MAX_SECONDS = 3 * 3600


def item_to_row(item: dict) -> dict:
    row = dict(item)
    if row.get("id") is not None:
        row["id"] = str(row["id"])
    if row.get("site_id") is not None:
        row["site_id"] = str(row["site_id"])
    if row.get("car_seat") is not None:
        row["car_seat"] = str(row["car_seat"])
    return row


def fail_stale_running_jobs() -> int:
    now = utcnow()
    rows = db.session.execute(
        db.select(ImportJob).where(ImportJob.status == "running")
    ).scalars().all()
    expired = 0
    for job in rows:
        started = job.started_at or now
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        age = (now - started).total_seconds()
        idle = (job.processed_rows or 0) == 0
        if (idle and age > STALE_IDLE_SECONDS) or age > STALE_MAX_SECONDS:
            job.status = "failed"
            job.error_message = "수집이 중단되어 만료했습니다."
            job.finished_at = now
            expired += 1
    if expired:
        db.session.commit()
    return expired


def find_running_job() -> ImportJob | None:
    fail_stale_running_jobs()
    return db.session.execute(
        db.select(ImportJob).where(ImportJob.status == "running").order_by(ImportJob.id.desc())
    ).scalars().first()


def find_pending_job() -> ImportJob | None:
    return db.session.execute(
        db.select(ImportJob).where(ImportJob.status == "pending").order_by(ImportJob.id.desc())
    ).scalars().first()


def request_manual_collect() -> ImportJob:
    current = find_running_job() or find_pending_job()
    if current:
        return current
    job = ImportJob(source="web", filename="manual", status="pending")
    db.session.add(job)
    db.session.commit()
    set_setting(CRAWL_COLLECT_NOW, str(job.id))
    return job


def consume_queued_collect(**kwargs):
    if find_running_job():
        return None
    raw = get_setting(CRAWL_COLLECT_NOW)
    job = find_pending_job()
    if job is None and raw and raw.isdigit():
        candidate = db.session.get(ImportJob, int(raw))
        if candidate is not None and candidate.status == "pending":
            job = candidate
    if job is None and raw in {"1", "now"}:
        set_setting(CRAWL_COLLECT_NOW, "")
        return import_from_crawl(source="web", filename="queued", **kwargs)
    if job is None:
        return None
    set_setting(CRAWL_COLLECT_NOW, "")
    return import_from_crawl(source="web", filename="queued", job=job, **kwargs)


def import_from_crawl(
    *,
    source: str,
    filename: str = "api/crawling",
    replace: bool = True,
    fetch_rows=None,
    job: ImportJob | None = None,
) -> ImportJob:
    running = find_running_job()
    if running and (job is None or running.id != job.id):
        raise RuntimeError(f"이미 수집 중 (작업 #{running.id})")
    if fetch_rows is None:
        base_url, api_key = crawl_credentials()
        if not api_key:
            raise RuntimeError("CRAWL_API_KEY가 설정되지 않았습니다.")

        def fetch_rows():
            yield from iter_crawling_rows(
                base_url=base_url,
                api_key=api_key,
                limit=DEFAULT_LIMIT,
                page_delay=PAGE_DELAY_SECONDS,
            )

    if job is None:
        job = ImportJob(
            source=source,
            filename=filename,
            status="running",
            started_at=utcnow(),
            error_message="크롤 API에서 받는 중입니다.",
        )
        db.session.add(job)
    else:
        job.status = "running"
        job.source = source
        job.filename = filename
        job.started_at = utcnow()
        job.error_message = "크롤 API에서 받는 중입니다."
    db.session.commit()

    try:
        rows = [item_to_row(item) for item in fetch_rows()]
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = utcnow()
        db.session.commit()
        raise

    job.error_message = None
    db.session.commit()
    return import_row_dicts(rows, source, filename, replace=replace, job=job)
