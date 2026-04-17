from __future__ import annotations

from datetime import datetime, timezone


def now_utc_aware() -> datetime:
    return datetime.now(timezone.utc)


def format_local(dt: object) -> str:
    if dt is None:
        return "-"
    if not isinstance(dt, datetime):
        return str(dt)
    value = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def format_local_date(dt: object) -> str:
    if dt is None:
        return "-"
    if not isinstance(dt, datetime):
        return str(dt)
    value = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return value.astimezone().strftime("%Y-%m-%d")
