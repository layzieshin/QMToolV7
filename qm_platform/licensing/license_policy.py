from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .license_schema import LICENSE_TYPE_FULL, LICENSE_TYPE_TRIAL, LICENSE_TYPES


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class LicensePolicy:
    local_machine_id: str

    def validate_license_type(self, payload: dict[str, Any]) -> None:
        license_type = str(payload.get("license_type", "")).strip().lower()
        if license_type not in LICENSE_TYPES:
            raise ValueError(f"invalid license_type: {license_type!r}")

    def validate_expiry_rules(self, payload: dict[str, Any]) -> None:
        license_type = str(payload.get("license_type", "")).strip().lower()
        expires_at = payload.get("expires_at")
        if license_type == LICENSE_TYPE_TRIAL:
            if expires_at is None or str(expires_at).strip() == "":
                raise ValueError("trial license requires expires_at")
            return
        if license_type == LICENSE_TYPE_FULL:
            if expires_at is not None and str(expires_at).strip() not in ("", "null"):
                raise ValueError("full license must have expires_at null")

    def is_expired(self, payload: dict[str, Any], now_utc: datetime | None = None) -> bool:
        license_type = str(payload.get("license_type", "")).strip().lower()
        if license_type == LICENSE_TYPE_FULL:
            return False
        expires_at = payload.get("expires_at")
        if expires_at is None or str(expires_at).strip() == "":
            return True
        now = now_utc or datetime.now(timezone.utc)
        return now > _parse_utc(str(expires_at))

    def machine_id_matches(self, payload: dict[str, Any]) -> bool:
        expected = str(payload.get("machine_id", "")).strip()
        return bool(expected) and expected == self.local_machine_id

    def is_module_allowed(self, payload: dict[str, Any], module_tag: str) -> bool:
        enabled = payload.get("enabled_modules", [])
        return module_tag in enabled
