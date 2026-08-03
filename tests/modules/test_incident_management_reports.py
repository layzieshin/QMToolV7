from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
    TimelineEntryType,
)
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    list_incident_timeline,
)


def _submission(*, title: str) -> IncidentSubmission:
    return IncidentSubmission(
        title=title,
        description="D",
        category="Prozess",
        reported_at=datetime.now(tz=UTC),
    )


def _assess_observation(api, incident_id: str) -> None:
    api.assess_incident(
        incident_id,
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


def _assess_critical_capa(api, incident_id: str) -> None:
    api.assess_incident(
        incident_id,
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


def _assess_repeated(api, incident_id: str) -> None:
    api.assess_incident(
        incident_id,
        IncidentAssessmentInput(
            classification=IncidentClassification.ERROR,
            is_critical=False,
            criticality_reason=None,
            is_repeated=True,
            capa_required=False,
            capa_reason=None,
            root_cause_required=False,
        ),
    )


class IncidentManagementReportsTest(unittest.TestCase):
    def test_case_and_register_reports(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission(title="Report"))
        report = api.generate_incident_report(case.incident_id)
        self.assertTrue(report.filename.endswith(".pdf"))
        register = api.generate_register_pdf()
        self.assertGreater(register.size_bytes, 0)

    def test_case_report_pdf_artifact_template_and_timeline(self) -> None:
        container, _ = build_incident_test_container(
            user=_FakeUser("qmb", "QMB"),
            residual_policy={
                "incident_management": {
                    "report_templates": {
                        "case": "case_v2",
                        "register": "default",
                        "management_review": "default",
                    }
                }
            },
        )
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission(title="Case PDF"))
        report = api.generate_incident_report(case.incident_id)

        self.assertEqual(report.mime_type, "application/pdf")
        self.assertGreater(report.size_bytes, 0)
        self.assertTrue(report.storage_key)
        self.assertTrue(report.report_id)
        self.assertEqual(report.report_template_id, "case_v2")
        self.assertTrue(report.filename.endswith("_report.pdf"))

        timeline = list_incident_timeline(container, case.incident_id)
        self.assertTrue(any(t.entry_type == TimelineEntryType.REPORT_GENERATED for t in timeline))

        second = api.generate_incident_report(case.incident_id)
        self.assertNotEqual(report.report_id, second.report_id)

    def test_register_pdf_not_stored_as_incident_artifact(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(_submission(title="Register only"))
        timeline_before = list_incident_timeline(container, case.incident_id)
        self.assertFalse(
            any(t.entry_type == TimelineEntryType.REPORT_GENERATED for t in timeline_before)
        )

        register = api.generate_register_pdf()
        self.assertEqual(register.filename, "incident_register.pdf")
        self.assertGreater(register.size_bytes, 0)
        self.assertTrue(register.storage_key)

        timeline_after = list_incident_timeline(container, case.incident_id)
        self.assertFalse(
            any(t.entry_type == TimelineEntryType.REPORT_GENERATED for t in timeline_after)
        )

    def test_capa_report_reflects_capa_required_incidents(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")

        baseline = api.generate_capa_report()
        self.assertGreater(baseline.size_bytes, 0)

        capa_case = api.submit_incident(_submission(title="CAPA line"))
        _assess_critical_capa(api, capa_case.incident_id)
        normal_case = api.submit_incident(_submission(title="No CAPA"))
        _assess_observation(api, normal_case.incident_id)

        capa_queue = api.list_capa_relevant_incidents()
        capa_ids = {c.incident_id for c in capa_queue}
        self.assertIn(capa_case.incident_id, capa_ids)
        self.assertNotIn(normal_case.incident_id, capa_ids)

        with_capa = api.generate_capa_report()
        self.assertGreater(with_capa.size_bytes, baseline.size_bytes)
        self.assertIsNone(with_capa.storage_key)

    def test_patterns_report_reflects_repeated_incidents(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")

        baseline = api.generate_patterns_report()
        self.assertGreater(baseline.size_bytes, 0)

        repeated_case = api.submit_incident(_submission(title="Repeated line"))
        _assess_repeated(api, repeated_case.incident_id)
        normal_case = api.submit_incident(_submission(title="Once"))
        _assess_observation(api, normal_case.incident_id)

        with_repeated = api.generate_patterns_report()
        self.assertGreater(with_repeated.size_bytes, baseline.size_bytes)
        self.assertIsNone(with_repeated.storage_key)


if __name__ == "__main__":
    unittest.main()
