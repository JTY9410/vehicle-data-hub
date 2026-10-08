"""Docker 전용: 수기 예약 수집 + 매일 00:00 KST 추가 데이터 수집."""

from __future__ import annotations

import time
from datetime import datetime

from apps import create_app
from apps.extensions import db
from apps.services.import_crawl import (
    consume_queued_collect,
    recover_interrupted_jobs,
    request_manual_collect,
)
from apps.services.scheduler import SEOUL, next_midnight_kst
from apps.services.settings import CRAWL_COOLDOWN_UNTIL, crawl_cooldown_remaining, get_setting

POLL_SECONDS = 5
COOLDOWN_POLL_SECONDS = 60
ERROR_RETRY_SECONDS = 30

_announced_cooldown: str | None = None


def _rollback() -> None:
    try:
        db.session.rollback()
    except Exception:  # noqa: BLE001
        pass


def _cooldown_until() -> tuple[str | None, str]:
    raw = get_setting(CRAWL_COOLDOWN_UNTIL)
    if not raw:
        return None, "-"
    return raw, datetime.fromisoformat(raw).astimezone(SEOUL).strftime("%H:%M:%S KST")


def _db_error(exc: Exception) -> int:
    _rollback()
    print(f"scheduler error (retry in {ERROR_RETRY_SECONDS}s): {exc}", flush=True)
    return ERROR_RETRY_SECONDS


def tick(app) -> int:
    global _announced_cooldown
    with app.app_context():
        try:
            left = crawl_cooldown_remaining()
            if left:
                raw, until = _cooldown_until()
                if raw != _announced_cooldown:
                    print(f"crawl cooldown until {until}", flush=True)
                    _announced_cooldown = raw
                return min(COOLDOWN_POLL_SECONDS, left)
        except Exception as exc:  # noqa: BLE001
            return _db_error(exc)
        try:
            job = consume_queued_collect()
        except Exception as exc:  # noqa: BLE001
            _rollback()
            try:
                left = crawl_cooldown_remaining()
                raw, until = _cooldown_until()
            except Exception:  # noqa: BLE001
                left = 0
            if not left:
                return _db_error(exc)
            print(f"queued crawl failed: {exc}; next retry {until}", flush=True)
            _announced_cooldown = raw
            return POLL_SECONDS
        if job:
            print(
                f"queued crawl {job.filename} status={job.status} saved={job.saved_rows} "
                f"rejected={job.rejected_rows}",
                flush=True,
            )
    return POLL_SECONDS


def queue_daily_collect(app) -> bool:
    with app.app_context():
        try:
            job = request_manual_collect(source="cron", filename="daily")
            print(f"daily collect queued job={job.id} status={job.status}", flush=True)
            return True
        except Exception as exc:  # noqa: BLE001
            _rollback()
            print(f"daily collect queue failed (retry in {ERROR_RETRY_SECONDS}s): {exc}", flush=True)
            return False


def main() -> None:
    app = create_app()
    while True:
        with app.app_context():
            try:
                n = recover_interrupted_jobs()
                break
            except Exception as exc:  # noqa: BLE001
                _rollback()
                print(f"scheduler start failed (retry in {ERROR_RETRY_SECONDS}s): {exc}", flush=True)
        time.sleep(ERROR_RETRY_SECONDS)
    if n:
        print(f"reset running jobs={n}; retry without cooldown", flush=True)
    print("scheduler ready", flush=True)
    nxt = next_midnight_kst()
    while True:
        if datetime.now(SEOUL) >= nxt:
            if queue_daily_collect(app):
                nxt = next_midnight_kst()
            else:
                time.sleep(ERROR_RETRY_SECONDS)
                continue
        wait = tick(app)
        until_next = (nxt - datetime.now(SEOUL)).total_seconds()
        time.sleep(max(1, min(wait, until_next)))


if __name__ == "__main__":
    main()
