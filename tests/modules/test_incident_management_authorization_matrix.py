from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    ActionType,
    AuthorizationError,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
    ModuleInternalRole,
    ValidationError,
)
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    run_capa_to_closure_review,
)


from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    switch_incident_user,
)


def _switch_user(container, user: _FakeUser) -> None:
    switch_incident_user(container, user)


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


class IncidentManagementAuthorizationMatrixTest(unittest.TestCase):
    def test_user_can_submit(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        self.assertEqual(case.reporter_user_id, "u1")

    def test_user_can_list_and_get_all_incidents(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission(title="Visible"))
        _switch_user(container, _FakeUser("u2", "User"))
        fetched = api.get_incident(case.incident_id)
        self.assertEqual(fetched.incident_id, case.incident_id)
        rows = api.list_incidents()
        self.assertTrue(any(r.incident_id == case.incident_id for r in rows))

    def test_user_cannot_assess(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        with self.assertRaises(AuthorizationError):
            api.assess_incident(case.incident_id, _observation_assessment())

    def test_user_cannot_close(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _observation_assessment())
        _switch_user(container, _FakeUser("u1", "User"))
        with self.assertRaises(AuthorizationError):
            api.close_incident(case.incident_id)

    def test_user_cannot_start_or_update_capa(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
        _switch_user(container, _FakeUser("u1", "User"))
        with self.assertRaises(AuthorizationError):
            api.start_capa(case.incident_id)
        with self.assertRaises(AuthorizationError):
            api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)

    def test_user_cannot_create_root_cause(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        _switch_user(container, _FakeUser("u1", "User"))
        with self.assertRaises(AuthorizationError):
            api.create_root_cause_analysis(case.incident_id, root_causes="Gap")

    def test_user_cannot_create_management_review(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        now = datetime.now(tz=UTC)
        with self.assertRaises(AuthorizationError):
            api.create_management_review(now, now)

    def test_user_cannot_forward_leadership(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        run_capa_to_closure_review(api, case)
        _switch_user(container, _FakeUser("u1", "User"))
        with self.assertRaises(AuthorizationError):
            api.forward_to_leadership(case.incident_id, "lead1")

    def test_user_cannot_open_inquiry(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        with self.assertRaises(AuthorizationError):
            api.open_inquiry(case.incident_id, "Question?")

    def test_user_cannot_list_qmb_queues(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(AuthorizationError):
            api.list_qmb_review_queue()
        with self.assertRaises(AuthorizationError):
            api.list_open_inquiries()

    def test_qmb_can_assess(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        assessed = api.assess_incident(case.incident_id, _observation_assessment())
        self.assertIsNotNone(assessed.classification)

    def test_qmb_can_open_inquiry(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        inquiry = api.open_inquiry(case.incident_id, "Need detail?")
        self.assertEqual(inquiry.incident_id, case.incident_id)

    def test_qmb_can_run_steering_workflow(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
        api.start_capa(case.incident_id)
        api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
        act = api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Fix")
        api.complete_action(act.action_id)
        api.plan_effectiveness_review(case.incident_id, "No repeat")
        api.complete_effectiveness_review(case.incident_id, effective=True, result="OK")
        api.forward_to_leadership(case.incident_id, "lead1")
        _switch_user(container, _FakeUser("lead1", "User"))
        api.acknowledge_leadership_review(case.incident_id)
        _switch_user(container, _FakeUser("qmb", "QMB"))
        closed = api.close_incident(case.incident_id)
        self.assertIsNotNone(closed.closed_at)

    def test_admin_and_qmb_can_assign_leitung(self) -> None:
        for actor_id, role in (("admin", "Admin"), ("qmb", "QMB")):
            with self.subTest(actor=role):
                container, _ = build_incident_test_container(user=_FakeUser(actor_id, role))
                api = container.get_port("incident_management_api")
                assignment = api.assign_module_role("lead-user", ModuleInternalRole.LEITUNG)
                self.assertEqual(assignment.role_name, ModuleInternalRole.LEITUNG)

    def test_user_cannot_assign_leitung(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(AuthorizationError):
            api.assign_module_role("lead-user", ModuleInternalRole.LEITUNG)

    def test_user_cannot_list_module_roles(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        with self.assertRaises(AuthorizationError):
            api.list_module_roles()

    def test_leitung_can_ack_only_when_forwarded(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        run_capa_to_closure_review(api, case)
        api.forward_to_leadership(case.incident_id, "lead1")
        _switch_user(container, _FakeUser("lead1", "User"))
        ack = api.acknowledge_leadership_review(case.incident_id, comment="Noted")
        self.assertIsNotNone(ack.acknowledged_at)

    def test_non_leitung_cannot_ack(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        run_capa_to_closure_review(api, case)
        api.forward_to_leadership(case.incident_id, "lead1")
        _switch_user(container, _FakeUser("u2", "User"))
        with self.assertRaises(AuthorizationError):
            api.acknowledge_leadership_review(case.incident_id)

    def test_leitung_without_forward_cannot_ack(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        case = api.submit_incident(_submission())
        api.assess_incident(case.incident_id, _critical_assessment())
        _switch_user(container, _FakeUser("lead1", "User"))
        with self.assertRaises(ValidationError):
            api.acknowledge_leadership_review(case.incident_id)

    def test_reporter_can_answer_inquiry(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        _switch_user(container, _FakeUser("qmb", "QMB"))
        api.open_inquiry(case.incident_id, "More detail?")
        _switch_user(container, _FakeUser("u1", "User"))
        answered = api.answer_inquiry(case.incident_id, "Here is the answer")
        self.assertEqual(answered.answer, "Here is the answer")

    def test_foreign_user_cannot_answer_inquiry(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        _switch_user(container, _FakeUser("qmb", "QMB"))
        api.open_inquiry(case.incident_id, "More detail?")
        _switch_user(container, _FakeUser("u2", "User"))
        with self.assertRaises(AuthorizationError):
            api.answer_inquiry(case.incident_id, "Not my incident")

    def test_answered_inquiry_cannot_be_answered_again(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission())
        _switch_user(container, _FakeUser("qmb", "QMB"))
        api.open_inquiry(case.incident_id, "More detail?")
        _switch_user(container, _FakeUser("u1", "User"))
        api.answer_inquiry(case.incident_id, "First answer")
        with self.assertRaises(ValidationError):
            api.answer_inquiry(case.incident_id, "Second answer")


if __name__ == "__main__":
    unittest.main()
