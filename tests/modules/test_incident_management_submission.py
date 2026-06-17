from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import IncidentSubmission
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container


class IncidentManagementSubmissionTest(unittest.TestCase):
    def test_id_generation_format(self) -> None:
        container, _root = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        reported = datetime(2026, 6, 16, 10, 0, tzinfo=UTC)
        case = api.submit_incident(
            IncidentSubmission(
                title="Test",
                description="Desc",
                category="Prozess",
                reported_at=reported,
            )
        )
        self.assertEqual(case.incident_id, "20260616_0001")
        case2 = api.submit_incident(
            IncidentSubmission(
                title="Test2",
                description="Desc2",
                category="Prozess",
                reported_at=reported,
            )
        )
        self.assertEqual(case2.incident_id, "20260616_0002")


if __name__ == "__main__":
    unittest.main()
