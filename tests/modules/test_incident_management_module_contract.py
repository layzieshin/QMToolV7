from __future__ import annotations

import unittest

from modules.incident_management.module import create_incident_management_module_contract
from tests.modules.incident_management_test_support import build_incident_test_container


class IncidentManagementModuleContractTest(unittest.TestCase):
    def test_ports_registered(self) -> None:
        container, _root = build_incident_test_container(
            user=__import__("tests.modules.incident_management_test_support", fromlist=["_FakeUser"])._FakeUser("admin", "Admin")
        )
        self.assertTrue(container.has_port("incident_management_api"))
        self.assertFalse(container.has_port("incident_management_service"))

    def test_contract_provides_api_port_only(self) -> None:
        contract = create_incident_management_module_contract()
        self.assertEqual(contract.provided_ports, ["incident_management_api"])

    def test_contract_license_tag(self) -> None:
        contract = create_incident_management_module_contract()
        self.assertEqual(contract.license_tag, "incident_management")
        self.assertNotIn("incident_management_service", contract.provided_ports)


if __name__ == "__main__":
    unittest.main()
