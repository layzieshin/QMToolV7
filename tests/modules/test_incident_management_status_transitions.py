from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    ActionType,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentStatus,
    IncidentSubmission,
    ManagementReviewItemStatus,
    ModuleInternalRole,
    ValidationError,
)
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    run_capa_to_closure_review,
    switch_incident_user,
)


def _submission(*, title: str = "T") -> IncidentSubmission:
    return IncidentSubmission(
        title=title,
        description="D",
        category="Prozess",
        reported_at=datetime.now(tz=UTC),
    )


def _observation_assessment() -> IncidentAssessmentInput:
    return IncidentAssessmentInput(
        classification=IncidentClassification.OBSERVATION,
        is_critical=False,
        criticality_reason=None,
        is_repeated=False,
        capa_required=False,
        capa_reason=None,
        root_cause_required=False,
    )


def _critical_assessment() -> IncidentAssessmentInput:
    return IncidentAssessmentInput(
        classification=IncidentClassification.ERROR,
        is_critical=True,
        criticality_reason="Critical",
        is_repeated=False,
        capa_required=True,
        capa_reason="Critical",
        root_cause_required=True,
    )


class IncidentStatusTransitionsTest(unittest.TestCase):
    def test_submitted_cannot_close_directly(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_inquiry_open_cannot_close_directly(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        switch_incident_user(container, _FakeUser("u1", "User"))
        case = api.submit_incident(_submission())
        switch_incident_user(container, _FakeUser("qmb", "QMB"))
        api.open_inquiry(case.incident_id, "Detail?")
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_capa_required_cannot_close_directly(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_actions_in_progress_cannot_close_directly(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
        api.start_capa(case.incident_id)
        api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
        api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Fix")
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_documentation_path_reaches_closed_via_closure_review(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _observation_assessment())
        closed = api.close_incident(case.incident_id)
        self.assertEqual(closed.status, IncidentStatus.CLOSED)

    def test_closed_can_archive(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _observation_assessment())
        api.close_incident(case.incident_id)
        archived = api.archive_incident(case.incident_id)
        self.assertEqual(archived.status, IncidentStatus.ARCHIVED)


class IncidentStatusWorkflowIntegrationTest(unittest.TestCase):
    def test_capa_path_reaches_closed_with_leadership_ack(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        run_capa_to_closure_review(api, case)
        api.forward_to_leadership(case.incident_id, "lead1")
        switch_incident_user(container, _FakeUser("lead1", "User"))
        api.acknowledge_leadership_review(case.incident_id)
        switch_incident_user(container, _FakeUser("qmb", "QMB"))
        closed = api.close_incident(case.incident_id)
        self.assertEqual(closed.status, IncidentStatus.CLOSED)

    def test_capa_path_blocked_without_leadership_ack(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        run_capa_to_closure_review(api, case)
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_ineffective_review_returns_to_follow_up_and_blocks_close(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
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
        api.complete_effectiveness_review(case.incident_id, effective=False, result="Failed")
        updated = api.get_incident(case.incident_id)
        self.assertEqual(updated.status, IncidentStatus.FOLLOW_UP)
        with self.assertRaises(ValidationError):
            api.close_incident(case.incident_id)

    def test_management_review_does_not_block_closure(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        reported = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        case = api.submit_incident(
            IncidentSubmission(
                title="MR",
                description="D",
                category="Prozess",
                reported_at=reported,
            )
        )
        api.assess_incident(case.incident_id, _observation_assessment())
        closed = api.close_incident(case.incident_id)
        self.assertEqual(closed.status, IncidentStatus.CLOSED)
        batch = api.create_management_review(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
        api.mark_management_review_in_discussion(batch.batch_id)
        items = api.acknowledge_management_review_items(batch.batch_id)
        self.assertTrue(all(i.status == ManagementReviewItemStatus.ACKNOWLEDGED for i in items))


if __name__ == "__main__":
    unittest.main()
