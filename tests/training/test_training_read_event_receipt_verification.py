from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from modules.training.wiring import register_training_ports
from qm_platform.events.event_bus import EventBus
from qm_platform.events.event_envelope import EventEnvelope
from qm_platform.runtime.container import RuntimeContainer


class _SettingsService:
    def get_module_settings(self, _module_id: str) -> dict[str, object]:
        return {}


class _DocsPool:
    def list_by_status(self, _status):
        return []

    def get_header(self, _document_id: str):
        return None


class _Users:
    def list_users(self):
        return []


class _ReadApiMissing:
    def get_read_receipt(self, _user_id: str, _document_id: str, _version: int):
        return None


class _Receipt:
    def __init__(self, user_id: str, document_id: str, version: int):
        self.user_id = user_id
        self.document_id = document_id
        self.version = version


class _ReadApiPresent:
    def get_read_receipt(self, user_id: str, document_id: str, version: int):
        return _Receipt(user_id, document_id, version)


class TrainingReadEventReceiptVerificationTest(unittest.TestCase):
    def _prepare_container(self, app_home: Path, read_api) -> RuntimeContainer:
        c = RuntimeContainer()
        c.register_port("settings_service", _SettingsService())
        c.register_port("app_home", app_home)
        c.register_port("event_bus", EventBus())
        c.register_port("documents_pool_api", _DocsPool())
        c.register_port("documents_read_api", read_api)
        c.register_port("usermanagement_service", _Users())
        return c

    def _count_progress_rows(self, db_path: Path) -> int:
        if not db_path.exists():
            return 0
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM training_progress").fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def test_event_without_receipt_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_home = Path(tmp)
            c = self._prepare_container(app_home, _ReadApiMissing())
            register_training_ports(c)
            event_bus = c.get_port("event_bus")
            event_bus.publish(
                EventEnvelope.create(
                    name="domain.documents.read.confirmed.v1",
                    module_id="documents",
                    payload={"user_id": "u1", "document_id": "DOC-1", "version": 1},
                )
            )
            self.assertEqual(self._count_progress_rows(app_home / "storage" / "training" / "training.db"), 0)

    def test_event_with_receipt_updates_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_home = Path(tmp)
            c = self._prepare_container(app_home, _ReadApiPresent())
            register_training_ports(c)
            event_bus = c.get_port("event_bus")
            event_bus.publish(
                EventEnvelope.create(
                    name="domain.documents.read.confirmed.v1",
                    module_id="documents",
                    payload={"user_id": "u1", "document_id": "DOC-1", "version": 1},
                )
            )
            self.assertEqual(self._count_progress_rows(app_home / "storage" / "training" / "training.db"), 1)


if __name__ == "__main__":
    unittest.main()

