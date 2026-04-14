from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class LicensePolicy:
    def is_expired(self, payload: dict[str, Any], now_utc: datetime | None = None) -> bool:
        expires_at = str(payload.get("expires_at", "")).strip()
        if not expires_at:
            return True
        now = now_utc or datetime.now(timezone.utc)
        return now > _parse_utc(expires_at)

    def is_module_allowed(self, payload: dict[str, Any], module_tag: str) -> bool:
        enabled = payload.get("enabled_modules", [])
        return module_tag in enabled

