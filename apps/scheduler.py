"""Docker 전용: 매주 일요일 저녁 12시(월요일 00:00 KST)에 크롤 전량 교체."""

from __future__ import annotations

import time
from datetime import datetime

from apps import create_app
from apps.services.import_crawl import import_from_crawl
from apps.services.scheduler import next_sunday_midnight_kst


def main() -> None:
    app = create_app()
    while True:
        nxt = next_sunday_midnight_kst()
        delay = max(1, int((nxt - datetime.now(nxt.tzinfo)).total_seconds()))
        time.sleep(delay)
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
