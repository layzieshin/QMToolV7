from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
    ModuleInternalRole,
)
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    run_capa_to_closure_review,
    switch_incident_user,
)


class IncidentManagementLeadershipTest(unittest.TestCase):
    def test_leadership_queue_filtered(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(
            IncidentSubmission(
                title="Lead",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=True,
                criticality_reason="Critical",
                is_repeated=False,
                capa_required=True,
                capa_reason="Critical",
                root_cause_required=True,
            ),
        )
        run_capa_to_closure_review(api, case)
        api.forward_to_leadership(case.incident_id, "lead1")
        switch_incident_user(container, _FakeUser("other", "User"))
        self.assertEqual(api.list_leadership_queue(), [])
        switch_incident_user(container, _FakeUser("lead1", "User"))
        queue = api.list_leadership_queue()
        self.assertEqual(len(queue), 1)


if __name__ == "__main__":
    unittest.main()
