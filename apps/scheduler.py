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
from apps.services.settings import crawl_cooldown_remaining

POLL_SECONDS = 5
COOLDOWN_POLL_SECONDS = 60
ERROR_RETRY_SECONDS = 30


def _rollback() -> None:
    try:
        db.session.rollback()
    except Exception:  # noqa: BLE001
        pass


def tick(app) -> int:
    with app.app_context():
        try:
            left = crawl_cooldown_remaining()
            if left:
                print(f"crawl cooldown {left}s", flush=True)
                return min(COOLDOWN_POLL_SECONDS, left)
            job = consume_queued_collect()
            if job:
                print(
                    f"queued crawl {job.filename} status={job.status} saved={job.saved_rows} "
                    f"rejected={job.rejected_rows}",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001
            _rollback()
            print(f"scheduler error (retry in {ERROR_RETRY_SECONDS}s): {exc}", flush=True)
            return ERROR_RETRY_SECONDS
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
