from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from modules.incident_management.contracts import (
    ActionType,
    ArtifactType,
    CapaStatus,
    IncidentAssessmentInput,
    IncidentClassification,
    IncidentSubmission,
    ModuleInternalRole,
    SimilarIncidentQuery,
    TimelineEntryType,
)
from qm_platform.events.event_bus import EventBus
from qm_platform.events.event_envelope import EventEnvelope
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    list_incident_timeline,
    switch_incident_user,
)


def _submission(*, title: str = "Event") -> IncidentSubmission:
    return IncidentSubmission(
        title=title,
        description="D",
        category="Prozess",
        reported_at=datetime.now(tz=UTC),
    )


class _EventCollector:
    def __init__(self, bus: EventBus) -> None:
        self.envelopes: list[EventEnvelope] = []
        self._bus = bus

    def subscribe(self, *names: str) -> None:
        for name in names:
            self._bus.subscribe(name, self._capture)

    def _capture(self, envelope: EventEnvelope) -> None:
        self.envelopes.append(envelope)

    def names(self) -> list[str]:
        return [e.name for e in self.envelopes]

    def payloads(self, name: str) -> list[dict]:
        return [e.payload for e in self.envelopes if e.name == name]

    def count(self, name: str) -> int:
        return sum(1 for e in self.envelopes if e.name == name)


def _assert_envelope_contract(envelope: EventEnvelope, *, required_payload_keys: set[str]) -> None:
    self_module = envelope.module_id
    assert self_module == "incident_management"
    assert envelope.name.startswith("domain.incident_management.")
    assert envelope.actor_user_id is not None
    assert envelope.occurred_at_utc
    assert required_payload_keys.issubset(envelope.payload.keys())
    for value in envelope.payload.values():
        if isinstance(value, str) and len(value) > 500:
            raise AssertionError("payload contains unexpectedly large string value")


class IncidentManagementEventContractsTest(unittest.TestCase):
    EVENT_NAMES = (
        "domain.incident_management.incident.submitted.v1",
        "domain.incident_management.inquiry.opened.v1",
        "domain.incident_management.inquiry.answered.v1",
        "domain.incident_management.incident.assessed.v1",
        "domain.incident_management.incident.grouped.v1",
        "domain.incident_management.capa.required.v1",
        "domain.incident_management.capa.updated.v1",
        "domain.incident_management.action.created.v1",
        "domain.incident_management.action.completed.v1",
        "domain.incident_management.effectiveness.planned.v1",
        "domain.incident_management.effectiveness.reviewed.v1",
        "domain.incident_management.leadership.forwarded.v1",
        "domain.incident_management.leadership.acknowledged.v1",
        "domain.incident_management.management_review.created.v1",
        "domain.incident_management.management_review.in_discussion.v1",
        "domain.incident_management.management_review.acknowledged.v1",
        "domain.incident_management.report.generated.v1",
        "domain.incident_management.artifact.attached.v1",
        "domain.incident_management.incident.closed.v1",
        "domain.incident_management.incident.archived.v1",
        "domain.incident_management.incident.rca.created.v1",
        "domain.incident_management.role.assigned.v1",
    )

    def setUp(self) -> None:
        self.container, self.root = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        self.api = self.container.get_port("incident_management_api")
        self.bus: EventBus = self.container.get_port("event_bus")
        self.events = _EventCollector(self.bus)
        self.events.subscribe(*self.EVENT_NAMES)

    def test_submit_publishes_event_with_payload(self) -> None:
        case = self.api.submit_incident(_submission())
        envelope = next(e for e in self.events.envelopes if e.name.endswith("incident.submitted.v1"))
        _assert_envelope_contract(envelope, required_payload_keys={"incident_id", "status"})
        self.assertEqual(envelope.payload["incident_id"], case.incident_id)

    def test_assess_publishes_assessed_and_capa_required_once(self) -> None:
        case = self.api.submit_incident(_submission(title="Assess"))
        self.api.assess_incident(
            case.incident_id,
            IncidentAssessmentInput(
                classification=IncidentClassification.NEAR_MISS,
                is_critical=True,
                criticality_reason="Near miss",
                is_repeated=False,
                capa_required=True,
                capa_reason="Near miss",
                root_cause_required=True,
            ),
        )
        assessed = next(e for e in self.events.envelopes if e.name.endswith("incident.assessed.v1"))
        _assert_envelope_contract(
            assessed,
            required_payload_keys={"incident_id", "classification", "capa_required", "criticality_group"},
        )
        self.assertEqual(self.events.count("domain.incident_management.capa.required.v1"), 1)

    def test_capa_start_does_not_republish_capa_required(self) -> None:
        case = self.api.submit_incident(_submission(title="Capa"))
        self.api.assess_incident(
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
        self.assertEqual(self.events.count("domain.incident_management.capa.required.v1"), 1)
        self.api.create_root_cause_analysis(case.incident_id, root_causes="Gap")
        self.api.start_capa(case.incident_id)
        self.assertEqual(self.events.count("domain.incident_management.capa.required.v1"), 1)
        self.assertGreaterEqual(self.events.count("domain.incident_management.capa.updated.v1"), 1)

    def test_link_incident_publishes_grouped_not_group_created(self) -> None:
        group = self.api.create_incident_group("Cluster")
        self.assertNotIn("domain.incident_management.group.created.v1", self.events.names())
        case = self.api.submit_incident(_submission(title="Grouped"))
        self.api.link_incident_to_group(case.incident_id, group.group_id)
        grouped = next(e for e in self.events.envelopes if e.name.endswith("incident.grouped.v1"))
        _assert_envelope_contract(grouped, required_payload_keys={"incident_id", "group_id"})
        self.assertEqual(grouped.payload["group_id"], group.group_id)

    def test_artifact_attached_event_and_timeline(self) -> None:
        case = self.api.submit_incident(_submission(title="Artifact"))
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=self.root) as fh:
            fh.write("evidence")
            path = Path(fh.name)
        artifact = self.api.attach_artifact(case.incident_id, path, ArtifactType.ATTACHMENT)
        envelope = next(e for e in self.events.envelopes if e.name.endswith("artifact.attached.v1"))
        _assert_envelope_contract(
            envelope,
            required_payload_keys={
                "incident_id",
                "artifact_id",
                "artifact_type",
                "uploaded_by",
                "occurred_at",
            },
        )
        self.assertEqual(envelope.payload["artifact_id"], artifact.artifact_id)
        timeline = list_incident_timeline(self.container, case.incident_id)
        self.assertTrue(any(t.entry_type == TimelineEntryType.ARTIFACT_ATTACHED for t in timeline))

    def test_full_workflow_event_payloads(self) -> None:
        self.api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        switch_incident_user(self.container, _FakeUser("u1", "User"))
        case = self.api.submit_incident(_submission(title="Reporter"))
        switch_incident_user(self.container, _FakeUser("qmb", "QMB"))
        self.api.open_inquiry(case.incident_id, "Question?")
        opened = next(e for e in self.events.envelopes if e.name.endswith("inquiry.opened.v1"))
        _assert_envelope_contract(opened, required_payload_keys={"incident_id", "inquiry_id"})

        switch_incident_user(self.container, _FakeUser("u1", "User"))
        self.api.answer_inquiry(case.incident_id, "Answer")
        answered = next(e for e in self.events.envelopes if e.name.endswith("inquiry.answered.v1"))
        _assert_envelope_contract(answered, required_payload_keys={"incident_id", "inquiry_id"})

        switch_incident_user(self.container, _FakeUser("qmb", "QMB"))
        self.api.assess_incident(
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
        self.api.create_root_cause_analysis(case.incident_id, root_causes="Root")
        rca = next(e for e in self.events.envelopes if e.name.endswith("incident.rca.created.v1"))
        _assert_envelope_contract(rca, required_payload_keys={"incident_id", "rca_id"})

        self.api.start_capa(case.incident_id)
        self.api.update_capa(case.incident_id, status=CapaStatus.IN_PROGRESS)
        action = self.api.create_action(case.incident_id, ActionType.CORRECTIVE_ACTION, "Fix")
        created = next(e for e in self.events.envelopes if e.name.endswith("action.created.v1"))
        _assert_envelope_contract(created, required_payload_keys={"incident_id", "action_id"})
        self.api.complete_action(action.action_id)
        completed = next(e for e in self.events.envelopes if e.name.endswith("action.completed.v1"))
        _assert_envelope_contract(completed, required_payload_keys={"incident_id", "action_id"})

        self.api.plan_effectiveness_review(case.incident_id, "Criteria")
        planned = next(e for e in self.events.envelopes if e.name.endswith("effectiveness.planned.v1"))
        _assert_envelope_contract(planned, required_payload_keys={"incident_id", "review_id"})
        self.api.complete_effectiveness_review(case.incident_id, effective=True, result="OK")
        reviewed = next(e for e in self.events.envelopes if e.name.endswith("effectiveness.reviewed.v1"))
        _assert_envelope_contract(reviewed, required_payload_keys={"incident_id", "review_id", "effective"})

        self.api.forward_to_leadership(case.incident_id, "lead1")
        forwarded = next(e for e in self.events.envelopes if e.name.endswith("leadership.forwarded.v1"))
        _assert_envelope_contract(forwarded, required_payload_keys={"incident_id", "leadership_user_id"})
        switch_incident_user(self.container, _FakeUser("lead1", "User"))
        self.api.acknowledge_leadership_review(case.incident_id)
        acked = next(e for e in self.events.envelopes if e.name.endswith("leadership.acknowledged.v1"))
        _assert_envelope_contract(acked, required_payload_keys={"incident_id"})

        switch_incident_user(self.container, _FakeUser("qmb", "QMB"))
        self.api.close_incident(case.incident_id)
        closed = next(e for e in self.events.envelopes if e.name.endswith("incident.closed.v1"))
        _assert_envelope_contract(closed, required_payload_keys={"incident_id"})
        self.api.archive_incident(case.incident_id)
        archived = next(e for e in self.events.envelopes if e.name.endswith("incident.archived.v1"))
        _assert_envelope_contract(archived, required_payload_keys={"incident_id"})

    def test_management_review_events_have_minimal_payloads(self) -> None:
        reported = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        case = self.api.submit_incident(
            IncidentSubmission(
                title="MR",
                description="D",
                category="Prozess",
                reported_at=reported,
            )
        )
        self.api.assess_incident(
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
        self.api.close_incident(case.incident_id)
        batch = self.api.create_management_review(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
        created = next(e for e in self.events.envelopes if e.name.endswith("management_review.created.v1"))
        _assert_envelope_contract(created, required_payload_keys={"batch_id", "item_count"})
        self.api.mark_management_review_in_discussion(batch.batch_id)
        in_disc = next(
            e for e in self.events.envelopes if e.name.endswith("management_review.in_discussion.v1")
        )
        _assert_envelope_contract(in_disc, required_payload_keys={"batch_id"})
        self.api.acknowledge_management_review_items(batch.batch_id)
        acked = next(
            e for e in self.events.envelopes if e.name.endswith("management_review.acknowledged.v1")
        )
        _assert_envelope_contract(acked, required_payload_keys={"batch_id", "count"})

    def test_rca_role_and_close_events(self) -> None:
        self.api.assign_module_role("lead1", ModuleInternalRole.LEITUNG)
        self.assertIn("domain.incident_management.role.assigned.v1", self.events.names())
        case = self.api.submit_incident(_submission(title="Close"))
        self.api.assess_incident(
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
        closed = self.api.close_incident(case.incident_id)
        self.assertEqual(closed.status.value, "CLOSED")
        self.assertIn("domain.incident_management.incident.closed.v1", self.events.names())


class IncidentManagementReportEventContractsTest(unittest.TestCase):
    def test_case_report_publishes_report_generated(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        bus: EventBus = container.get_port("event_bus")
        collector = _EventCollector(bus)
        collector.subscribe("domain.incident_management.report.generated.v1")
        case = api.submit_incident(_submission(title="Report event"))
        api.generate_incident_report(case.incident_id)

        self.assertEqual(collector.count("domain.incident_management.report.generated.v1"), 1)
        envelope = collector.envelopes[0]
        _assert_envelope_contract(
            envelope,
            required_payload_keys={"incident_id", "report_type", "report_template_id"},
        )
        self.assertEqual(envelope.payload["incident_id"], case.incident_id)
        self.assertEqual(envelope.payload["report_type"], "case")
        self.assertNotIn("batch_id", envelope.payload)

    def test_management_review_report_publishes_report_generated(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        bus: EventBus = container.get_port("event_bus")
        collector = _EventCollector(bus)
        reported = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        case = api.submit_incident(
            IncidentSubmission(
                title="MR report event",
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
        batch = api.create_management_review(
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 30, 23, 59, tzinfo=UTC),
        )
        collector.subscribe("domain.incident_management.report.generated.v1")
        api.generate_management_review_report(batch.batch_id)

        self.assertEqual(collector.count("domain.incident_management.report.generated.v1"), 1)
        envelope = collector.envelopes[0]
        _assert_envelope_contract(
            envelope,
            required_payload_keys={"batch_id", "report_type", "report_template_id"},
        )
        self.assertEqual(envelope.payload["batch_id"], batch.batch_id)
        self.assertEqual(envelope.payload["report_type"], "management_review")
        self.assertNotIn("incident_id", envelope.payload)


class IncidentSimilarLabelsTest(unittest.TestCase):
    def test_similar_query_filters_labels(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        api.submit_incident(
            IncidentSubmission(
                title="A",
                description="D",
                category="Gerät",
                reported_at=datetime.now(tz=UTC),
                labels=("device",),
            )
        )
        api.submit_incident(
            IncidentSubmission(
                title="B",
                description="D",
                category="Gerät",
                reported_at=datetime.now(tz=UTC),
                labels=("process",),
            )
        )
        matches = api.list_similar_incidents(
            SimilarIncidentQuery(category="Gerät", labels=("device",), limit=10)
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].title, "A")


class IncidentMyIncidentsTest(unittest.TestCase):
    def test_list_my_incidents_filters_reporter(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        api.submit_incident(
            IncidentSubmission(
                title="Mine",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        switch_incident_user(container, _FakeUser("u2", "User"))
        api.submit_incident(
            IncidentSubmission(
                title="Other",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        switch_incident_user(container, _FakeUser("u1", "User"))
        mine = api.list_my_incidents()
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].title, "Mine")


if __name__ == "__main__":
    unittest.main()
