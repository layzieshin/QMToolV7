from __future__ import annotations

import unittest
from datetime import UTC, datetime

from modules.incident_management.contracts import (
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentStatus,
    IncidentSubmission,
    ManagementReviewItemStatus,
    TimelineEntryType,
)
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    list_incident_timeline,
)


class IncidentManagementManagementReviewTest(unittest.TestCase):
    def _close_observation(self, api, *, title: str, reported: datetime) -> str:
        case = api.submit_incident(
            IncidentSubmission(
                title=title,
                description="D",
                category="Prozess",
                reported_at=reported,
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
        api.close_incident(case.incident_id)
        return case.incident_id

    def test_batch_does_not_block_closure(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        reported = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        case_id = self._close_observation(api, title="MR", reported=reported)
        closed = api.get_incident(case_id)
        self.assertEqual(closed.status, IncidentStatus.CLOSED)
        batch = api.create_management_review(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
        api.mark_management_review_in_discussion(batch.batch_id)
        items = api.acknowledge_management_review_items(batch.batch_id)
        self.assertTrue(all(i.status == ManagementReviewItemStatus.ACKNOWLEDGED for i in items))

    def test_management_review_timeline_on_all_incidents(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        reported = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
        id_a = self._close_observation(api, title="A", reported=reported)
        id_b = self._close_observation(api, title="B", reported=reported)

        batch = api.create_management_review(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
        for incident_id in (id_a, id_b):
            timeline = list_incident_timeline(container, incident_id)
            self.assertTrue(
                any(t.entry_type == TimelineEntryType.MANAGEMENT_REVIEW_CREATED for t in timeline),
                incident_id,
            )

        api.mark_management_review_in_discussion(batch.batch_id)
        for incident_id in (id_a, id_b):
            timeline = list_incident_timeline(container, incident_id)
            self.assertTrue(
                any(t.entry_type == TimelineEntryType.MANAGEMENT_REVIEW_IN_DISCUSSION for t in timeline),
                incident_id,
            )

        api.acknowledge_management_review_items(batch.batch_id)
        for incident_id in (id_a, id_b):
            timeline = list_incident_timeline(container, incident_id)
            self.assertTrue(
                any(t.entry_type == TimelineEntryType.MANAGEMENT_REVIEW_ACKNOWLEDGED for t in timeline),
                incident_id,
            )


    def test_management_review_report_batch_level_without_incident_artifact(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        reported = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
        case_id = self._close_observation(api, title="MR report gate", reported=reported)
        status_before = api.get_incident(case_id).status

        batch = api.create_management_review(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
        timeline_after_close = list_incident_timeline(container, case_id)
        report_timeline_count = sum(
            1 for t in timeline_after_close if t.entry_type == TimelineEntryType.REPORT_GENERATED
        )
        self.assertEqual(report_timeline_count, 1)

        report = api.generate_management_review_report(batch.batch_id)
        self.assertGreater(report.size_bytes, 0)
        self.assertTrue(report.storage_key)
        self.assertIn("management_review", report.filename)

        self.assertEqual(api.get_incident(case_id).status, status_before)
        timeline_after_report = list_incident_timeline(container, case_id)
        self.assertEqual(
            sum(1 for t in timeline_after_report if t.entry_type == TimelineEntryType.REPORT_GENERATED),
            report_timeline_count,
        )

        items = api.acknowledge_management_review_items(batch.batch_id)
        self.assertTrue(all(i.status == ManagementReviewItemStatus.ACKNOWLEDGED for i in items))


if __name__ == "__main__":
    unittest.main()
