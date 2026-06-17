from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentStatus,
    IncidentSubmission,
)
from tests.modules.incident_management_test_support import _FakeUser, build_incident_test_container


class IncidentManagementAssessmentTest(unittest.TestCase):
    def _submit(self, api):
        return api.submit_incident(
            IncidentSubmission(
                title="Assess me",
                description="Details",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )

    def test_observation_documentation_only(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        assessed = api.assess_incident(
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
        self.assertEqual(assessed.status, IncidentStatus.DOCUMENTATION_ONLY)

    def test_critical_requires_capa(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        assessed = api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=True,
                criticality_reason="Patient safety",
                is_repeated=False,
                capa_required=True,
                capa_reason="Critical event",
                root_cause_required=True,
            ),
        )
        self.assertTrue(assessed.capa_required)
        self.assertTrue(assessed.leadership_required)
        self.assertEqual(assessed.status, IncidentStatus.ROOT_CAUSE_REQUIRED)

    def test_critical_derives_capa_without_manual_flag(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        assessed = api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=True,
                criticality_reason="Patient safety",
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=False,
            ),
        )
        self.assertTrue(assessed.capa_required)
        self.assertTrue(assessed.root_cause_required)
        self.assertEqual(assessed.status, IncidentStatus.ROOT_CAUSE_REQUIRED)

    def test_capa_derives_root_cause_even_when_input_false(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        assessed = api.assess_incident(
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
        self.assertTrue(assessed.capa_required)
        self.assertTrue(assessed.root_cause_required)
        self.assertEqual(assessed.status, IncidentStatus.ROOT_CAUSE_REQUIRED)

    def test_explicit_root_cause_without_capa(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        case = self._submit(api)
        assessed = api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.ERROR,
                is_critical=False,
                criticality_reason=None,
                is_repeated=False,
                capa_required=False,
                capa_reason=None,
                root_cause_required=True,
            ),
        )
        self.assertFalse(assessed.capa_required)
        self.assertTrue(assessed.root_cause_required)
        self.assertEqual(assessed.status, IncidentStatus.ROOT_CAUSE_REQUIRED)


if __name__ == "__main__":
    unittest.main()
