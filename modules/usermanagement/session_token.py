from __future__ import annotations

import hashlib
import secrets


def generate_session_token(*, nbytes: int = 32) -> str:
    """Create a high-entropy opaque session token (never persist in plaintext)."""
    if nbytes < 32:
        raise ValueError("session token entropy must be at least 32 bytes")
    return secrets.token_urlsafe(nbytes)


def hash_session_token(raw_token: str) -> str:
    """Hash an opaque token for storage/lookup (SHA-256 hex digest)."""
    if not raw_token:
        raise ValueError("raw_token must not be empty")
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
