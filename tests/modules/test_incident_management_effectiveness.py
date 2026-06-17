from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    ActionType,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentStatus,
    IncidentSubmission,
    ModuleInternalRole,
)
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container, switch_incident_user


def _full_capa_path(api, *, leadership_user_id: str):
    case = api.submit_incident(
        IncidentSubmission(
            title="Close me",
            description="D",
            category="Prozess",
            reported_at=datetime.now(tz=UTC),
        )
    )
    case = api.assess_incident(
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
    api.create_root_cause_analysis(case.incident_id, root_causes="Training gap")
    api.start_capa(case.incident_id)
    api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
    action = api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Retrain staff")
    api.complete_action(action.action_id)
    api.plan_effectiveness_review(case.incident_id, "No repeat errors")
    api.complete_effectiveness_review(case.incident_id, effective=True, result="OK")
    api.forward_to_leadership(case.incident_id, leadership_user_id)
    return case


from modules.incident_management.contracts import CapaStatus  # noqa: E402


class IncidentManagementEffectivenessTest(unittest.TestCase):
    def test_ineffective_returns_to_follow_up(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(
            IncidentSubmission(
                title="Eff",
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
                capa_required=True,
                capa_reason="Manual",
                root_cause_required=True,
            ),
        )
        api.create_root_cause_analysis(case.incident_id, root_causes="Root")
        api.start_capa(case.incident_id)
        api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
        action = api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Fix")
        api.complete_action(action.action_id)
        api.plan_effectiveness_review(case.incident_id, "Criteria")
        review = api.complete_effectiveness_review(case.incident_id, effective=False, result="Failed")
        self.assertFalse(review.effective)
        updated = api.get_incident(case.incident_id)
        self.assertEqual(updated.status, IncidentStatus.FOLLOW_UP)


class IncidentManagementClosureRulesTest(unittest.TestCase):
    def test_capa_closure_with_leadership(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = _full_capa_path(api, leadership_user_id="lead1")
        switch_incident_user(container, _FakeUser("lead1", "User"))
        api.acknowledge_leadership_review(case.incident_id)
        switch_incident_user(container, _FakeUser("qmb", "QMB"))
        closed = api.close_incident(case.incident_id)
        self.assertEqual(closed.status, IncidentStatus.CLOSED)


if __name__ == "__main__":
    unittest.main()
