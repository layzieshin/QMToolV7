from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.registry.contracts import RegisterState, ReleaseEvidenceMode
from modules.registry.module import create_registry_module_contract
from modules.registry.service import RegistryService
from modules.registry.sqlite_repository import SQLiteRegistryRepository
from qm_platform.events.event_bus import EventBus
from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


class RegistryModuleTest(unittest.TestCase):
    def test_registry_ports_are_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            container = RuntimeContainer()
            container.register_port("logger", LoggerService(root / "logs.jsonl"))
            container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
            container.register_port("event_bus", EventBus())
            container.register_port(
                "settings_service",
                SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json")),
            )

            lifecycle = LifecycleManager(container)
            lifecycle.register(create_registry_module_contract())
            lifecycle.start()

            self.assertTrue(container.has_port("registry_service"))
            self.assertTrue(container.has_port("registry_api"))
            self.assertTrue(container.has_port("registry_projection_api"))
            self.assertIsInstance(container.get_port("registry_service"), RegistryService)
            self.assertFalse(hasattr(container.get_port("registry_api"), "apply_documents_state"))

    def test_projection_api_rejects_non_documents_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bus = EventBus()
            events = []
            bus.subscribe("domain.registry.projection.rejected.v1", lambda e: events.append(e))
            container = RuntimeContainer()
            log_file = root / "logs.jsonl"
            container.register_port("logger", LoggerService(log_file))
            container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
            container.register_port("event_bus", bus)
            container.register_port(
                "settings_service",
                SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json")),
            )

            lifecycle = LifecycleManager(container)
            lifecycle.register(create_registry_module_contract())
            lifecycle.start()

            projection = container.get_port("registry_projection_api")
            with self.assertRaises(PermissionError):
                projection.apply_documents_projection(
                    source_module_id="tasks",
                    document_id="DOC-1",
                    version=1,
                    status="PLANNED",
                )
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].payload["source_module_id"], "tasks")
            self.assertTrue(log_file.exists())
            self.assertIn("projection update rejected", log_file.read_text(encoding="utf-8"))

    def test_apply_documents_state_deterministic_replay_supports_reconciliation(self) -> None:
        """Same inputs + fixed event envelope yield identical registry rows (rebuild/replay primitive)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = Path(__file__).resolve().parents[2] / "modules" / "registry" / "schema.sql"
            repo = SQLiteRegistryRepository(root / "registry.db", schema_path)
            service = RegistryService(repo)
            evt = EventEnvelope(
                event_id="recovery-replay-1",
                name="domain.documents.state.replay.v1",
                occurred_at_utc="2024-06-01T10:00:00+00:00",
                correlation_id="corr-recovery-1",
                causation_id=None,
                actor_user_id="system",
                module_id="documents",
                payload={"document_id": "DOC-R1", "version": 2},
            )
            first = service.apply_documents_state(
                document_id="DOC-R1",
                version=2,
                status="APPROVED",
                release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
                event=evt,
            )
            second = service.apply_documents_state(
                document_id="DOC-R1",
                version=2,
                status="APPROVED",
                release_evidence_mode=ReleaseEvidenceMode.WORKFLOW,
                event=evt,
            )
            self.assertEqual(first, second)
            self.assertEqual(first.register_state, RegisterState.VALID)
            self.assertTrue(first.is_findable)
            self.assertEqual(first.active_version, 2)
            self.assertIsNotNone(first.last_update_at.tzinfo)

    def test_registry_rebuild_on_empty_db_matches_replayed_projection(self) -> None:
        """Simulate empty registry after incident: replaying the same projection reproduces the row."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema_path = Path(__file__).resolve().parents[2] / "modules" / "registry" / "schema.sql"
            evt = EventEnvelope(
                event_id="recovery-replay-2",
                name="domain.documents.state.replay.v1",
                occurred_at_utc="2024-06-01T11:00:00+00:00",
                correlation_id="corr-recovery-2",
                causation_id=None,
                actor_user_id="system",
                module_id="documents",
                payload={"document_id": "DOC-R2", "version": 1},
            )
            db_before = root / "registry_before.db"
            svc_before = RegistryService(SQLiteRegistryRepository(db_before, schema_path))
            svc_before.apply_documents_state(
                document_id="DOC-R2",
                version=1,
                status="IN_REVIEW",
                event=evt,
            )
            expected = svc_before.get_entry("DOC-R2")
            self.assertIsNotNone(expected)

            db_after = root / "registry_after_fresh.db"
            svc_after = RegistryService(SQLiteRegistryRepository(db_after, schema_path))
            svc_after.apply_documents_state(
                document_id="DOC-R2",
                version=1,
                status="IN_REVIEW",
                event=evt,
            )
            got = svc_after.get_entry("DOC-R2")
            self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
