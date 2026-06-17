from __future__ import annotations

import unittest

from modules.incident_management.contracts import AuthorizationError
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container, switch_incident_user


class IncidentManagementSettingsGovernanceTest(unittest.TestCase):
    def _switch(self, container, user: _FakeUser) -> None:
        switch_incident_user(container, user)

    def test_governance_critical_without_acknowledge_blocked(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(ValueError):
            api.set_module_settings({"effectiveness_delay": 45})

    def test_governance_critical_with_acknowledge_allowed_for_qmb(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        updated = api.set_module_settings(
            {"effectiveness_delay": 45},
            acknowledge_governance_change=True,
        )
        self.assertEqual(updated["effectiveness_delay"], 45)

    def test_governance_critical_with_acknowledge_allowed_for_admin(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("admin", "Admin"))
        api = container.get_port("incident_management_api")
        updated = api.set_module_settings(
            {"capa_required_rules": {"critical": False, "repeated": False}},
            acknowledge_governance_change=True,
        )
        self.assertFalse(updated["capa_required_rules"]["critical"])

    def test_operational_setting_without_acknowledge_allowed(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        updated = api.set_module_settings({"categories": ["Prozess", "Gerät", "Sonstiges"]})
        self.assertEqual(updated["categories"], ["Prozess", "Gerät", "Sonstiges"])

    def test_user_cannot_set_module_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(AuthorizationError):
            api.set_module_settings({"categories": ["Prozess"]})


if __name__ == "__main__":
    unittest.main()
