from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import IncidentSubmission
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container


class IncidentManagementGroupingTest(unittest.TestCase):
    def test_group_create_and_link(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        group = api.create_incident_group("Repeat cluster", "Same device")
        case = api.submit_incident(
            IncidentSubmission(
                title="Grouped",
                description="D",
                category="Gerät",
                reported_at=datetime.now(tz=UTC),
                device="Analyzer-1",
            )
        )
        linked = api.link_incident_to_group(case.incident_id, group.group_id)
        self.assertEqual(linked.group_id, group.group_id)


if __name__ == "__main__":
    unittest.main()
