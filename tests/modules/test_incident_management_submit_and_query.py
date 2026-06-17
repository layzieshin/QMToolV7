from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import IncidentListFilter, IncidentStatus, IncidentSubmission
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container


class IncidentManagementSubmitAndQueryTest(unittest.TestCase):
    def test_submit_get_list(self) -> None:
        container, _root = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(
            IncidentSubmission(
                title="Event A",
                description="Details",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        fetched = api.get_incident(case.incident_id)
        self.assertEqual(fetched.incident_id, case.incident_id)
        rows = api.list_incidents(IncidentListFilter(status=IncidentStatus.SUBMITTED))
        self.assertTrue(any(r.incident_id == case.incident_id for r in rows))


if __name__ == "__main__":
    unittest.main()
