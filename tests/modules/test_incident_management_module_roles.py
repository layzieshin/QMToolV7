from __future__ import annotations

import unittest

from modules.incident_management.contracts import ModuleInternalRole
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container


class IncidentManagementModuleRolesTest(unittest.TestCase):
    def test_assign_and_list_leitung(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("admin", "Admin"))
        api = container.get_port("incident_management_api")
        assignment = api.assign_module_role("lead-user", ModuleInternalRole.LEITUNG)
        rows = api.list_module_roles(ModuleInternalRole.LEITUNG)
        self.assertTrue(any(r.user_id == "lead-user" for r in rows))
        self.assertEqual(assignment.role_name, ModuleInternalRole.LEITUNG)


if __name__ == "__main__":
    unittest.main()
