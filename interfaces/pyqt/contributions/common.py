from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

from modules.documents.contracts import SystemRole
from modules.usermanagement.role_policies import is_effective_qmb


def normalize_role(role: str | None) -> str:
    if role is None:
        return ""
    raw = role.strip().upper()
    if raw == "ADMIN":
        return "ADMIN"
    if raw == "QMB":
        return "QMB"
    if raw == "USER":
        return "USER"
    return raw


def role_to_system_role(role: str) -> SystemRole:
    normalized = normalize_role(role)
    mapping = {
        "ADMIN": SystemRole.ADMIN,
        "QMB": SystemRole.QMB,
        "USER": SystemRole.USER,
    }
    if normalized not in mapping:
        raise RuntimeError(f"unsupported role '{role}'")
    return mapping[normalized]


def user_to_system_role(user: object) -> SystemRole:
    normalized = normalize_role(getattr(user, "role", None))
    if normalized == "ADMIN":
        return SystemRole.ADMIN
    if is_effective_qmb(user):
        return SystemRole.QMB
    return SystemRole.USER


def to_plain(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_plain(v) for v in value]
    if isinstance(value, tuple):
        return [to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_plain(v) for k, v in value.items()}
    if hasattr(value, "value"):
        try:
            return value.value  # enum-like
        except Exception:
            return str(value)
    return value


def as_json_text(value: object) -> str:
    return json.dumps(to_plain(value), indent=2, ensure_ascii=True, default=str)


def parse_csv_set(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}
