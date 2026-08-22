"""Redact secret material from platform audit payloads (AP-029 D07)."""
from __future__ import annotations

import re
from typing import Any

_REDACTED = "<redacted>"

_FORBIDDEN_KEY_PARTS = frozenset(
    {
        "password",
        "passwd",
        "pass",
        "token",
        "secret",
        "private_key",
        "privatekey",
        "api_key",
        "apikey",
        "session_token",
        "raw_token",
        "bearer",
        "sslpassword",
        "passfile",
        "authorization",
        "credential",
    }
)

_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_PG_DSN_RE = re.compile(r"postgresql://[^\s'\"]+", re.IGNORECASE)
_PASSWORD_KV_RE = re.compile(
    r"(password\s*[:=]\s*)([^\s,;\"']+)",
    re.IGNORECASE,
)
_INLINE_SECRET_ALIASES = (
    "authorization",
    "session_token",
    "sessiontoken",
    "raw_token",
    "private_key",
    "privatekey",
    "sslpassword",
    "passfile",
    "password",
    "credential",
    "api_key",
    "apikey",
    "secret",
    "token",
    "passwd",
    "bearer",
)
_INLINE_SECRET_KV_RE = re.compile(
    rf"(?i)(\b(?:{'|'.join(re.escape(alias) for alias in _INLINE_SECRET_ALIASES)})\s*[:=]\s*)(\S+)",
)


def _normalize_key(key: str) -> str:
    text = str(key).strip()
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return text.lower().replace("-", "_")


def _key_is_forbidden(key: str) -> bool:
    normalized = _normalize_key(key)
    if not normalized:
        return False
    parts = normalized.split("_")
    return any(part in _FORBIDDEN_KEY_PARTS for part in parts) or normalized in _FORBIDDEN_KEY_PARTS


def _redact_string(value: str) -> str:
    text = str(value)
    text = _BEARER_RE.sub(f"Bearer {_REDACTED}", text)
    text = _PG_DSN_RE.sub(f"postgresql://{_REDACTED}", text)
    text = _PASSWORD_KV_RE.sub(rf"\1{_REDACTED}", text)
    text = _INLINE_SECRET_KV_RE.sub(rf"\1{_REDACTED}", text)
    return text


def redact_audit_details(value: Any) -> Any:
    """Return a copy of ``value`` with forbidden keys and inline secrets redacted."""
    if value is None:
        return None
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, list):
        return [redact_audit_details(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _key_is_forbidden(str(key)):
                redacted[str(key)] = _REDACTED
            else:
                redacted[str(key)] = redact_audit_details(item)
        return redacted
    return value
