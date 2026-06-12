from __future__ import annotations

import base64
import json
import re
from typing import Any

CODE_PREFIX = "QMT1"


def encode_license_code(payload: dict[str, Any]) -> str:
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    encoded = base64.urlsafe_b64encode(compact.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{CODE_PREFIX}.{encoded}"


def decode_license_code(code: str) -> dict[str, Any]:
    raw = code.strip()
    if not raw:
        raise ValueError("license code is empty")
    if not raw.startswith(f"{CODE_PREFIX}."):
        raise ValueError(f"license code must start with '{CODE_PREFIX}.'")
    encoded = raw[len(CODE_PREFIX) + 1 :]
    if not encoded or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        raise ValueError("license code payload is invalid")
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(encoded + padding)
    except Exception as exc:
        raise ValueError("license code base64 decode failed") from exc
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("license code JSON payload is invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("license code payload must be a JSON object")
    return payload
