"""Client runtime profile for J04-M0 (backend vs legacy)."""
from __future__ import annotations

CLIENT_RUNTIME_PROFILE_PORT = "client_runtime_profile"

PROFILE_BACKEND = "backend"
PROFILE_LEGACY = "legacy"


def normalize_client_runtime_profile(value: object | None) -> str:
    raw = str(value or PROFILE_BACKEND).strip().lower()
    if raw == PROFILE_LEGACY:
        return PROFILE_LEGACY
    return PROFILE_BACKEND


def is_backend_client_profile(container) -> bool:
    if not container.has_port(CLIENT_RUNTIME_PROFILE_PORT):
        return True
    return normalize_client_runtime_profile(container.get_port(CLIENT_RUNTIME_PROFILE_PORT)) == PROFILE_BACKEND
