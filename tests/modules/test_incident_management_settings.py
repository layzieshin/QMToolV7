from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from modules.incident_management.contracts import (
    ActionType,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
    ModuleInternalRole,
    ValidationError,
)
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container, switch_incident_user


class IncidentManagementSettingsTest(unittest.TestCase):
    def test_get_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("admin", "Admin"))
        api = container.get_port("incident_management_api")
        settings = api.get_module_settings()
        self.assertIn("categories", settings)
        self.assertIn("effectiveness_delay", settings)
        self.assertNotIn("leadership_role_assignments", settings)

    def test_standard_deadlines_default_action_due_at(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.set_module_settings(
            {
                "standard_deadlines": {
                    "assessment_days": 5,
                    "action_days": 30,
                    "immediate_action_days": 3,
                    "corrective_action_days": 14,
                    "preventive_action_days": 21,
                    "qmb_review_days": 5,
                }
            },
            acknowledge_governance_change=True,
        )
        case = api.submit_incident(
            IncidentSubmission(
                title="Deadline",
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
        before = datetime.now(tz=UTC)
        action = api.create_action(case.incident_id, ActionType.IMMEDIATE_ACTION, "Stop")
        self.assertIsNotNone(action.due_at)
        assert action.due_at is not None
        delta = action.due_at - before
        self.assertGreaterEqual(delta, timedelta(days=2, hours=23))
        self.assertLessEqual(delta, timedelta(days=3, hours=1))

    def test_explicit_action_due_at_overrides_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(
            IncidentSubmission(
                title="Explicit due",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
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
        explicit = datetime(2030, 1, 1, tzinfo=UTC)
        action = api.create_action(
            case.incident_id,
            ActionType.CORRECTIVE_ACTION,
            "Fix",
            due_at=explicit,
        )
        self.assertEqual(action.due_at, explicit)

    def test_effectiveness_delay_from_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.set_module_settings({"effectiveness_delay": 10}, acknowledge_governance_change=True)
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
        act = api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Fix")
        api.complete_action(act.action_id)
        before = datetime.now(tz=UTC)
        review = api.plan_effectiveness_review(case.incident_id, "Criteria")
        delta = review.planned_at - before
        self.assertGreaterEqual(delta, timedelta(days=9, hours=23))
        self.assertLessEqual(delta, timedelta(days=10, hours=1))

    def test_report_templates_affect_report_result(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.set_module_settings(
            {"report_templates": {"case": "case_v2", "register": "default", "management_review": "default"}},
            acknowledge_governance_change=True,
        )
        case = api.submit_incident(
            IncidentSubmission(
                title="Report",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        report = api.generate_incident_report(case.incident_id)
        self.assertEqual(report.report_template_id, "case_v2")

    def test_categories_validation_from_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        switch_incident_user(container, _FakeUser("admin", "Admin"))
        api.set_module_settings({"categories": ["Prozess", "Gerät"]})
        switch_incident_user(container, _FakeUser("u1", "User"))
        with self.assertRaises(ValidationError):
            api.submit_incident(
                IncidentSubmission(
                    title="Bad category",
                    description="D",
                    category="Unbekannt",
                    reported_at=datetime.now(tz=UTC),
                )
            )

    def test_leadership_assignment_uses_module_roles_not_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        assignment = api.assign_module_role("lead-user", ModuleInternalRole.LEITUNG)
        rows = api.list_module_roles(ModuleInternalRole.LEITUNG)
        self.assertEqual(assignment.role_name, ModuleInternalRole.LEITUNG)
        self.assertTrue(any(r.user_id == "lead-user" for r in rows))


from modules.incident_management.contracts import CapaStatus  # noqa: E402


if __name__ == "__main__":
    unittest.main()
