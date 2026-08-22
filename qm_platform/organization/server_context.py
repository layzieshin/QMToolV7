"""Server-authoritative single-organization context (AP-029 D04 / PG00-B).

``organization_id`` is never taken from browser/client headers as authoritative input.
Callers may pass a client hint only so spoof attempts can be detected and rejected.
"""
from __future__ import annotations

import re

# Stable installation identifier seeded by platform migration 0003.
INSTALLATION_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000001"
_ORGANIZATION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class ClientOrganizationSpoofRejected(ValueError):
    """Raised when a client tries to supply a non-matching authoritative organization_id."""


def _normalize_client_hint(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def resolve_active_organization_id(*, client_organization_id: str | None = None) -> str:
    """Return the server-confirmed active organization for this installation.

    A non-empty client hint that differs from the server value is rejected fail-closed.
    Matching hints are ignored for authority (server value remains canonical).
    """
    hint = _normalize_client_hint(client_organization_id)
    if hint is not None and hint != INSTALLATION_ORGANIZATION_ID:
        raise ClientOrganizationSpoofRejected(
            "client-supplied organization_id is not authoritative"
        )
    if not _ORGANIZATION_ID_RE.fullmatch(INSTALLATION_ORGANIZATION_ID):
        raise RuntimeError("installation organization_id contract is invalid")
    return INSTALLATION_ORGANIZATION_ID
