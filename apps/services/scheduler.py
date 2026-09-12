from __future__ import annotations

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def next_sunday_midnight_kst(now: datetime | None = None) -> datetime:
    """일요일 저녁 12시 = 월요일 00:00 KST."""
    current = (now or datetime.now(SEOUL)).astimezone(SEOUL)
    days_ahead = (7 - current.weekday()) % 7
    target = datetime.combine(
        current.date() + timedelta(days=days_ahead),
        time(0, 0),
        tzinfo=SEOUL,
    )
    if target <= current:
        target += timedelta(days=7)
    return target
