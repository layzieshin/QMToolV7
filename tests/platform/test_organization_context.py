"""Static checks for AP-029 PG00-B organization context."""
from __future__ import annotations

import pytest

from qm_platform.organization.server_context import (
    INSTALLATION_ORGANIZATION_ID,
    ClientOrganizationSpoofRejected,
    resolve_active_organization_id,
)


def test_resolve_active_organization_id_returns_installation_default() -> None:
    assert resolve_active_organization_id() == INSTALLATION_ORGANIZATION_ID


def test_resolve_active_organization_id_rejects_client_spoof() -> None:
    with pytest.raises(ClientOrganizationSpoofRejected):
        resolve_active_organization_id(
            client_organization_id="00000000-0000-4000-8000-000000009999"
        )


def test_matching_client_hint_does_not_change_server_authority() -> None:
    assert resolve_active_organization_id(
        client_organization_id=INSTALLATION_ORGANIZATION_ID
    ) == INSTALLATION_ORGANIZATION_ID
