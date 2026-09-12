from __future__ import annotations

from datetime import timezone

from apps.extensions import db
from apps.models import ImportJob, utcnow
from apps.services.crawl_client import DEFAULT_LIMIT, iter_crawling_rows
from apps.services.import_csv import import_row_dicts
from apps.services.settings import CRAWL_COLLECT_NOW, crawl_credentials, get_setting, set_setting

PAGE_DELAY_SECONDS = 1.0
STALE_IDLE_SECONDS = 180
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


def request_manual_collect() -> ImportJob | None:
    running = find_running_job()
    if running:
        return running
    set_setting(CRAWL_COLLECT_NOW, "1")
    return None


def consume_queued_collect(**kwargs):
    if find_running_job():
        return None
    if not get_setting(CRAWL_COLLECT_NOW):
        return None
    set_setting(CRAWL_COLLECT_NOW, "")
    return import_from_crawl(source="web", filename="queued", **kwargs)


def import_from_crawl(
    *,
    source: str,
    filename: str = "api/crawling",
    replace: bool = True,
    fetch_rows=None,
) -> ImportJob:
    running = find_running_job()
    if running:
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

    return import_row_dicts(
        (item_to_row(item) for item in fetch_rows()),
        source,
        filename,
        replace=replace,
    )
