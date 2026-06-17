from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    ActionType,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
    ValidationError,
)
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container


class IncidentManagementCapaRulesTest(unittest.TestCase):
    def _assessed_capa_case(self, api):
        case = api.submit_incident(
            IncidentSubmission(
                title="CAPA case",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        return api.assess_incident(
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

    def test_closure_blocked_without_rca(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._assessed_capa_case(api)
        api.start_capa(case.incident_id)
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_capa_required_sent_once_on_assess_not_on_start(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        bus = container.get_port("event_bus")
        received: list[str] = []

        def _handler(env) -> None:
            if env.name == "domain.incident_management.capa.required.v1":
                received.append(env.name)

        bus.subscribe("domain.incident_management.capa.required.v1", _handler)
        case = self._assessed_capa_case(api)
        self.assertEqual(len(received), 1)
        api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
        api.start_capa(case.incident_id)
        self.assertEqual(len(received), 1)


class IncidentManagementActionsTest(unittest.TestCase):
    def test_create_and_complete_action(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(
            IncidentSubmission(
                title="Action case",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=False,
                criticality_reason=None,
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
            ),
        )
        action = api.create_action(case.incident_id, ActionType.IMMEDIATE_ACTION, "Stop process")
        completed = api.complete_action(action.action_id)
        self.assertEqual(completed.status.value, "COMPLETED")


if __name__ == "__main__":
    unittest.main()
