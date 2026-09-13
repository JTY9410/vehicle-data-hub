"""Docker 전용: 수기 예약 수집 + 매주 월요일 00:00 KST 전량 교체."""

from __future__ import annotations

import time
from datetime import datetime

from apps import create_app
from apps.services.import_crawl import consume_queued_collect, import_from_crawl
from apps.services.scheduler import next_sunday_midnight_kst
from apps.services.settings import crawl_cooldown_remaining

POLL_SECONDS = 5
COOLDOWN_POLL_SECONDS = 60


def main() -> None:
    app = create_app()
    with app.app_context():
        from apps.services.import_crawl import fail_running_jobs

        n = fail_running_jobs()
        if n:
            from apps.services.settings import CRAWL_COLLECT_NOW, set_crawl_cooldown, set_setting

            set_crawl_cooldown()
            set_setting(CRAWL_COLLECT_NOW, "now")
            print(f"reset running jobs={n}; cooldown then retry", flush=True)
    while True:
        nxt = next_sunday_midnight_kst()
        deadline = time.monotonic() + max(1, int((nxt - datetime.now(nxt.tzinfo)).total_seconds()))
        while time.monotonic() < deadline:
            wait = POLL_SECONDS
            with app.app_context():
                left = crawl_cooldown_remaining()
                if left:
                    print(f"crawl cooldown {left}s", flush=True)
                    wait = min(COOLDOWN_POLL_SECONDS, left)
                else:
                    try:
                        job = consume_queued_collect()
                        if job:
                            print(
                                f"queued crawl status={job.status} saved={job.saved_rows} "
                                f"rejected={job.rejected_rows}",
                                flush=True,
                            )
                    except Exception as exc:  # noqa: BLE001
                        try:
                            from apps.extensions import db

                            db.session.rollback()
                        except Exception:  # noqa: BLE001
                            pass
                        print(f"queued crawl failed: {exc}", flush=True)
            remaining = deadline - time.monotonic()
            time.sleep(min(wait, max(1, remaining)))
        with app.app_context():
            try:
                job = import_from_crawl(source="cron", filename="weekly")
                print(
                    f"weekly crawl status={job.status} saved={job.saved_rows} "
                    f"rejected={job.rejected_rows}",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"weekly crawl failed: {exc}", flush=True)


if __name__ == "__main__":
    main()
