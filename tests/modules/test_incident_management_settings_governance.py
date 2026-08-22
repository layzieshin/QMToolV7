from __future__ import annotations

import unittest
from datetime import datetime, timezone

from modules.incident_management.contracts import AuthorizationError
from modules.usermanagement.contracts import issue_user_context
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.settings.errors import ResidualPolicyReadonlyError
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    switch_incident_user,
)


def _actor():
    return issue_user_context(
        user_id="qmb-1",
        session_id="s1",
        request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username="qmb",
        global_roles=["QMB"],
        is_qmb=True,
        authenticated_at=datetime.now(timezone.utc),
    )


class IncidentManagementSettingsGovernanceTest(unittest.TestCase):
    def _switch(self, container, user: _FakeUser) -> None:
        switch_incident_user(container, user)

    def test_bucket_c_write_blocked_without_actor_kwarg(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(TypeError):
            api.set_module_settings({"effectiveness_delay": 45})

    def test_bucket_c_write_blocked_even_with_acknowledge_and_actor(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(ResidualPolicyReadonlyError):
            api.set_module_settings(
                {"effectiveness_delay": 45},
                actor=_actor(),
                acknowledge_governance_change=True,
            )

    def test_bucket_c_capa_rules_blocked(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("admin", "Admin"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(ResidualPolicyReadonlyError):
            api.set_module_settings(
                {"capa_required_rules": {"critical": False, "repeated": False}},
                actor=_actor(),
                acknowledge_governance_change=True,
            )

    def test_bucket_c_categories_blocked(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(ResidualPolicyReadonlyError):
            api.set_module_settings(
                {"categories": ["Prozess", "Gerät", "Sonstiges"]},
                actor=_actor(),
            )

    def test_user_cannot_set_module_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(AuthorizationError):
            api.set_module_settings({"categories": ["Prozess"]}, actor=_actor())


if __name__ == "__main__":
    unittest.main()
