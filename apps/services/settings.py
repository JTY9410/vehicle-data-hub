from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import current_app

from apps.extensions import db
from apps.models import AppSetting, utcnow

CRAWL_API_KEY = "crawl_api_key"
CRAWL_API_URL = "crawl_api_url"
CRAWL_COLLECT_NOW = "crawl_collect_now"
CRAWL_RESUME_ID = "crawl_resume_id"
CRAWL_COOLDOWN_UNTIL = "crawl_cooldown_until"
DEFAULT_CRAWL_URL = "https://crawl.wecarmobility.co.kr"
DEFAULT_COOLDOWN_SECONDS = 30 * 60


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


def set_crawl_cooldown(seconds: int = DEFAULT_COOLDOWN_SECONDS) -> None:
    until = utcnow() + timedelta(seconds=max(1, int(seconds)))
    set_setting(CRAWL_COOLDOWN_UNTIL, until.isoformat())


def crawl_cooldown_remaining() -> int:
    raw = get_setting(CRAWL_COOLDOWN_UNTIL)
    if not raw:
        return 0
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return 0
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    left = (until - utcnow()).total_seconds()
    return max(0, int(left))


def masked_crawl_key() -> str | None:
    key = crawl_credentials()[1]
    if not key:
        return None
    if len(key) <= 4:
        return "****"
    return f"••••{key[-4:]}"
