"""Redact secret material from platform audit payloads (AP-029 D07)."""
from __future__ import annotations

import re
from collections.abc import Iterator
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
        "pwd",
    }
)

_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_BASIC_RE = re.compile(r"Basic\s+\S+", re.IGNORECASE)
_PG_DSN_RE = re.compile(r"postgresql://[^\s'\"]+", re.IGNORECASE)
_INLINE_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-")


def _normalize_key(key: str) -> str:
    text = str(key).strip()
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _key_is_forbidden(key: str) -> bool:
    normalized = _normalize_key(key)
    if not normalized:
        return False
    return any(
        normalized == alias
        or normalized.startswith(f"{alias}_")
        or normalized.endswith(f"_{alias}")
        or f"_{alias}_" in normalized
        for alias in _FORBIDDEN_KEY_PARTS
    )


def _inline_value_replacement(text: str, start: int) -> tuple[int, str]:
    """Scan one scalar value from ``start`` and return its end and redaction."""
    if start >= len(text):
        return start, _REDACTED
    quote = text[start] if text[start] in {"\"", "'"} else None
    if quote is not None:
        cursor = start + 1
        escaped = False
        while cursor < len(text):
            char = text[cursor]
            if char in {"\r", "\n"}:
                break
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return cursor + 1, f"{quote}{_REDACTED}{quote}"
            cursor += 1
        return cursor, f"{quote}{_REDACTED}"

    cursor = start
    while cursor < len(text) and text[cursor] not in " \t\r\n,;\"'":
        cursor += 1
    return cursor, _REDACTED


def _iter_inline_key_prefixes(text: str) -> Iterator[tuple[int, str, int]]:
    """Yield assignment key spans in one forward pass over ``text``."""
    cursor = 0
    length = len(text)
    while cursor < length:
        char = text[cursor]
        if not char.isascii() or not char.isalnum():
            cursor += 1
            continue
        if cursor > 0:
            previous = text[cursor - 1]
            if previous.isascii() and (previous.isalnum() or previous == "_"):
                cursor += 1
                continue

        key_start = cursor
        cursor += 1
        while cursor < length and text[cursor] in _INLINE_KEY_CHARS:
            cursor += 1
        key_end = cursor
        probe = cursor
        if probe < length and text[probe] in {"\"", "'"}:
            probe += 1
        while probe < length and text[probe].isspace():
            probe += 1
        if probe < length and text[probe] in {":", "="}:
            probe += 1
            while probe < length and text[probe].isspace():
                probe += 1
            yield key_start, text[key_start:key_end], probe
            cursor = probe
        else:
            cursor = max(probe, key_end)


def _redact_inline_key_values(text: str) -> str:
    """Redact forbidden assignments without scanning neutral values."""
    replacements: list[tuple[int, int, str]] = []
    consumed_until = -1
    for key_start, key, value_start in _iter_inline_key_prefixes(text):
        if key_start < consumed_until:
            continue
        if not _key_is_forbidden(key):
            continue
        end, replacement = _inline_value_replacement(text, value_start)
        replacements.append((value_start, end, replacement))
        consumed_until = end
    if not replacements:
        return text
    parts: list[str] = []
    copied_until = 0
    for start, end, replacement in replacements:
        parts.append(text[copied_until:start])
        parts.append(replacement)
        copied_until = end
    parts.append(text[copied_until:])
    return "".join(parts)


def _redact_string(value: str) -> str:
    text = str(value)
    text = _BEARER_RE.sub(f"Bearer {_REDACTED}", text)
    text = _BASIC_RE.sub(f"Basic {_REDACTED}", text)
    text = _PG_DSN_RE.sub(f"postgresql://{_REDACTED}", text)
    return _redact_inline_key_values(text)


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
