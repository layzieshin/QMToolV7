from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    ActionType,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
)
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container, switch_incident_user


class IncidentManagementQueryQueuesTest(unittest.TestCase):
    def _submit(self, api, *, title: str = "Case"):
        return api.submit_incident(
            IncidentSubmission(
                title=title,
                description="Details",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )

    def test_qmb_review_queue_before_and_after_assess(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        queue = api.list_qmb_review_queue()
        self.assertEqual([c.incident_id for c in queue], [case.incident_id])
        api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.OBSERVATION,
                is_critical=False,
                criticality_reason=None,
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
            ),
        )
        self.assertEqual(api.list_qmb_review_queue(), [])

    def test_open_inquiries_queue(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        switch_incident_user(container, _FakeUser("u1", "User"))
        case = self._submit(api)
        switch_incident_user(container, _FakeUser("qmb", "QMB"))
        inquiry = api.open_inquiry(case.incident_id, "Need more detail?")
        open_rows = api.list_open_inquiries()
        self.assertEqual(len(open_rows), 1)
        self.assertEqual(open_rows[0].inquiry_id, inquiry.inquiry_id)
        switch_incident_user(container, _FakeUser("u1", "User"))
        api.answer_inquiry(case.incident_id, "Here is the answer")
        switch_incident_user(container, _FakeUser("qmb", "QMB"))
        self.assertEqual(api.list_open_inquiries(), [])

    def test_open_actions_queue(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
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
        open_rows = api.list_open_actions()
        self.assertEqual(len(open_rows), 1)
        self.assertEqual(open_rows[0].action_id, action.action_id)
        api.complete_action(action.action_id)
        self.assertEqual(api.list_open_actions(), [])

    def test_pending_effectiveness_reviews_queue(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=True,
                criticality_reason="Critical",
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
            ),
        )
        api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
        api.start_capa(case.incident_id)
        api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
        act = api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Retrain")
        api.complete_action(act.action_id)
        review = api.plan_effectiveness_review(case.incident_id, "No repeat errors")
        pending = api.list_pending_effectiveness_reviews()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].review_id, review.review_id)
        api.complete_effectiveness_review(case.incident_id, effective=True, result="OK")
        self.assertEqual(api.list_pending_effectiveness_reviews(), [])

    def test_similar_incident_candidates_via_api(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        reported = datetime.now(tz=UTC)
        api.submit_incident(
            IncidentSubmission(
                title="A",
                description="D",
                category="Gerät",
                reported_at=reported,
                labels=("shared",),
            )
        )
        target = api.submit_incident(
            IncidentSubmission(
                title="Target",
                description="D",
                category="Gerät",
                reported_at=reported,
                labels=("shared",),
            )
        )
        candidates = api.list_similar_incident_candidates(target.incident_id)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "A")

    def test_capa_relevant_incidents_queue(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api, title="Capa case")
        api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=True,
                criticality_reason="Critical",
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
            ),
        )
        capa_cases = api.list_capa_relevant_incidents()
        self.assertEqual(len(capa_cases), 1)
        self.assertTrue(capa_cases[0].capa_required)


if __name__ == "__main__":
    unittest.main()
