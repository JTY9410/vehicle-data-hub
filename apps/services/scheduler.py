from __future__ import annotations

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def next_midnight_kst(now: datetime | None = None) -> datetime:
    """매일 저녁 12시 = 다음 날 00:00 KST."""
    current = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    return datetime.combine(current.date() + timedelta(days=1), time(0, 0), tzinfo=SEOUL)
