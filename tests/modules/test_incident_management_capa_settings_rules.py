from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import IncidentAssessmentInput, IncidentClassification, IncidentSubmission
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container, switch_incident_user


class IncidentCapaRulesFromSettingsTest(unittest.TestCase):
    def _assess_patient_safety(self, api, *, patient_safety: bool):
        case = api.submit_incident(
            IncidentSubmission(
                title="CAPA rule",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        return api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.RISK,
                is_critical=False,
                criticality_reason=None,
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
                patient_safety_relevant=patient_safety,
            ),
        )

    def test_patient_safety_rule_via_assess(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.set_module_settings(
            {
                "capa_required_rules": {
                    "critical": False,
                    "repeated": False,
                    "patient_safety": True,
                    "system_risk": False,
                    "formal_deviation": False,
                    "result_correctness": False,
                    "escalation": False,
                }
            },
            acknowledge_governance_change=True,
        )
        assessed = self._assess_patient_safety(api, patient_safety=True)
        self.assertTrue(assessed.capa_required)

    def test_patient_safety_disabled_via_assess(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.set_module_settings(
            {
                "capa_required_rules": {
                    "critical": False,
                    "repeated": False,
                    "patient_safety": False,
                    "system_risk": False,
                    "formal_deviation": False,
                    "result_correctness": False,
                    "escalation": False,
                }
            },
            acknowledge_governance_change=True,
        )
        assessed = self._assess_patient_safety(api, patient_safety=True)
        self.assertFalse(assessed.capa_required)

    def test_critical_rule_disabled_via_api_settings(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("admin", "Admin"))
        api = container.get_port("incident_management_api")
        api.set_module_settings(
            {
                "capa_required_rules": {
                    "critical": False,
                    "repeated": False,
                    "patient_safety": False,
                    "system_risk": False,
                    "formal_deviation": False,
                    "result_correctness": False,
                    "escalation": False,
                }
            },
            acknowledge_governance_change=True,
        )
        switch_incident_user(container, _FakeUser("qmb", "QMB"))
        case = api.submit_incident(
            IncidentSubmission(
                title="Critical no capa",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        assessed = api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=True,
                criticality_reason="Would be critical",
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
            ),
        )
        self.assertFalse(assessed.capa_required)


if __name__ == "__main__":
    unittest.main()
