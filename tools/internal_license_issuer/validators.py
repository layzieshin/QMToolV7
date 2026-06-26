"""Validation helpers for internal license issuing."""
from __future__ import annotations

import re
from datetime import datetime, timezone

_MACHINE_ID_RE = re.compile(r"^qmt-[0-9a-f]{16}$")


def normalize_machine_id(value: str) -> str:
    return str(value).strip().lower()


def is_valid_machine_id(value: str) -> bool:
    return bool(_MACHINE_ID_RE.fullmatch(normalize_machine_id(value)))


def parse_utc_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def trial_expires_at_days(days: int) -> str:
    from datetime import timedelta

    end = datetime.now(timezone.utc) + timedelta(days=max(1, days))
    end = end.replace(hour=23, minute=59, second=59, microsecond=0)
    return end.isoformat()


def suggest_next_customer_id(last: str | None) -> str:
    if not last or not str(last).strip():
        return "CUST-001"
    match = re.fullmatch(r"CUST-(\d+)", str(last).strip().upper())
    if not match:
        return "CUST-001"
    return f"CUST-{int(match.group(1)) + 1:03d}"
