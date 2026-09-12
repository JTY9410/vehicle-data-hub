from __future__ import annotations

from flask import current_app

from apps.models import ImportJob
from apps.services.crawl_client import DEFAULT_LIMIT, iter_crawling_rows
from apps.services.import_csv import import_row_dicts


def item_to_row(item: dict) -> dict:
    row = dict(item)
    if row.get("id") is not None:
        row["id"] = str(row["id"])
    if row.get("site_id") is not None:
        row["site_id"] = str(row["site_id"])
    if row.get("car_seat") is not None:
        row["car_seat"] = str(row["car_seat"])
    uniq = str(row.get("unique_option_info") or "").strip()
    if uniq:
        opt = str(row.get("option_info") or "").strip()
        row["option_info"] = f"{opt}\n{uniq}".strip() if opt else uniq
    return row


def import_from_crawl(
    *,
    source: str,
    filename: str = "api/crawling",
    replace: bool = True,
    fetch_rows=None,
) -> ImportJob:
    if fetch_rows is None:
        api_key = (current_app.config.get("CRAWL_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("CRAWL_API_KEY가 설정되지 않았습니다.")
        base_url = (
            current_app.config.get("CRAWL_API_URL") or "https://crawl.wecarmobility.co.kr"
        )

        def fetch_rows():
            yield from iter_crawling_rows(
                base_url=base_url,
                api_key=api_key,
                limit=DEFAULT_LIMIT,
            )

    return import_row_dicts(
        (item_to_row(item) for item in fetch_rows()),
        source,
        filename,
        replace=replace,
    )
