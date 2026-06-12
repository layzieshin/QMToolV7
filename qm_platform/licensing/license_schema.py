from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
LICENSE_TYPE_TRIAL = "trial"
LICENSE_TYPE_FULL = "full"
LICENSE_TYPES = frozenset({LICENSE_TYPE_TRIAL, LICENSE_TYPE_FULL})

REQUIRED_FIELDS = (
    "schema_version",
    "license_id",
    "license_type",
    "issued_to",
    "customer_id",
    "issued_at",
    "expires_at",
    "enabled_modules",
    "machine_id",
    "key_id",
    "signature",
)


def normalize_enabled_modules(modules: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    return sorted({str(m).strip() for m in modules if str(m).strip()})


def unknown_module_tags(enabled_modules: list[str], known_tags: set[str]) -> list[str]:
    return sorted(tag for tag in enabled_modules if tag not in known_tags)
