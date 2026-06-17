from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from modules.incident_management.contracts import ArtifactType, IncidentSubmission, TimelineEntryType
from qm_platform.events.event_bus import EventBus
from tests.modules.incident_management_test_support import (
    _FakeUser,
    build_incident_test_container,
    list_incident_timeline,
)


class IncidentManagementArtifactsTest(unittest.TestCase):
    def test_attach_artifact(self) -> None:
        container, root = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        case = api.submit_incident(
            IncidentSubmission(
                title="Artifact",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=root) as fh:
            fh.write("evidence")
            path = Path(fh.name)
        artifact = api.attach_artifact(case.incident_id, path, ArtifactType.ATTACHMENT)
        self.assertEqual(artifact.incident_id, case.incident_id)

    def test_attach_artifact_publishes_event(self) -> None:
        container, root = build_incident_test_container(user=_FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        bus: EventBus = container.get_port("event_bus")
        received: list[str] = []
        bus.subscribe(
            "domain.incident_management.artifact.attached.v1",
            lambda env: received.append(env.name),
        )
        case = api.submit_incident(
            IncidentSubmission(
                title="Artifact event",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=root) as fh:
            fh.write("evidence")
            path = Path(fh.name)
        api.attach_artifact(case.incident_id, path, ArtifactType.ATTACHMENT)
        self.assertEqual(received, ["domain.incident_management.artifact.attached.v1"])
        timeline = list_incident_timeline(container, case.incident_id)
        self.assertTrue(any(t.entry_type == TimelineEntryType.ARTIFACT_ATTACHED for t in timeline))

    def test_case_report_uses_report_generated_not_artifact_attached_event(self) -> None:
        container, _ = build_incident_test_container(user=_FakeUser("qmb", "QMB"))
        api = container.get_port("incident_management_api")
        bus: EventBus = container.get_port("event_bus")
        attached: list[str] = []
        generated: list[str] = []
        bus.subscribe(
            "domain.incident_management.artifact.attached.v1",
            lambda env: attached.append(env.name),
        )
        bus.subscribe(
            "domain.incident_management.report.generated.v1",
            lambda env: generated.append(env.name),
        )
        case = api.submit_incident(
            IncidentSubmission(
                title="Case report artifact",
                description="D",
                category="Prozess",
                reported_at=datetime.now(tz=UTC),
            )
        )
        api.generate_incident_report(case.incident_id)
        self.assertEqual(attached, [])
        self.assertEqual(generated, ["domain.incident_management.report.generated.v1"])
        timeline = list_incident_timeline(container, case.incident_id)
        self.assertTrue(any(t.entry_type == TimelineEntryType.REPORT_GENERATED for t in timeline))
        self.assertFalse(any(t.entry_type == TimelineEntryType.ARTIFACT_ATTACHED for t in timeline))


if __name__ == "__main__":
    unittest.main()
