"""Docker 전용: 수기 예약 수집 + 매주 월요일 00:00 KST 전량 교체."""

from __future__ import annotations

import time
from datetime import datetime

from apps import create_app
from apps.services.import_crawl import consume_queued_collect, import_from_crawl
from apps.services.scheduler import next_sunday_midnight_kst

POLL_SECONDS = 5


def main() -> None:
    app = create_app()
    while True:
        nxt = next_sunday_midnight_kst()
        deadline = time.monotonic() + max(1, int((nxt - datetime.now(nxt.tzinfo)).total_seconds()))
        while time.monotonic() < deadline:
            with app.app_context():
                try:
                    job = consume_queued_collect()
                    if job:
                        print(
                            f"queued crawl status={job.status} saved={job.saved_rows} "
                            f"rejected={job.rejected_rows}",
                            flush=True,
                        )
                except Exception as exc:  # noqa: BLE001
                    print(f"queued crawl failed: {exc}", flush=True)
            remaining = deadline - time.monotonic()
            time.sleep(min(POLL_SECONDS, max(1, remaining)))
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
