from __future__ import annotations

from flask import current_app

from apps.extensions import db
from apps.models import AppSetting, utcnow

CRAWL_API_KEY = "crawl_api_key"
CRAWL_API_URL = "crawl_api_url"
CRAWL_COLLECT_NOW = "crawl_collect_now"
DEFAULT_CRAWL_URL = "https://crawl.wecarmobility.co.kr"


def get_setting(key: str) -> str | None:
    row = db.session.get(AppSetting, key)
    if row is None or row.value is None:
        return None
    value = row.value.strip()
    return value or None


def set_setting(key: str, value: str | None) -> None:
    row = db.session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
        row.updated_at = utcnow()
    db.session.commit()


def crawl_credentials() -> tuple[str, str]:
    url = get_setting(CRAWL_API_URL) or current_app.config.get("CRAWL_API_URL") or DEFAULT_CRAWL_URL
    key = get_setting(CRAWL_API_KEY) or current_app.config.get("CRAWL_API_KEY") or ""
    return str(url).strip().rstrip("/"), str(key).strip()


def crawl_key_configured() -> bool:
    return bool(crawl_credentials()[1])


def masked_crawl_key() -> str | None:
    key = crawl_credentials()[1]
    if not key:
        return None
    if len(key) <= 4:
        return "****"
    return f"••••{key[-4:]}"
