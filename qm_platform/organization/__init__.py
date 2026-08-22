"""Platform organization context (AP-029 PG00-B)."""

from .server_context import (
    INSTALLATION_ORGANIZATION_ID,
    ClientOrganizationSpoofRejected,
    resolve_active_organization_id,
)

__all__ = [
    "INSTALLATION_ORGANIZATION_ID",
    "ClientOrganizationSpoofRejected",
    "resolve_active_organization_id",
]
