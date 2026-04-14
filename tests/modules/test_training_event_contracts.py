from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, DocumentVersionState
from modules.training.secure_store import EncryptedTrainingBlobStore
from modules.training.service import TrainingService
from modules.training.sqlite_repository import SQLiteTrainingRepository


@dataclass
class _FakeUser:
    user_id: str
    username: str
    role: str


class _FakeDocsPool:
    def __init__(self, rows):
        self._rows = rows

    def list_by_status(self, status: DocumentStatus):
        return [r for r in self._rows if r.status == status]


class _FakeUsers:
    def list_users(self):
        return [_FakeUser("qmb", "qmb", "QMB"), _FakeUser("admin", "admin", "Admin"), _FakeUser("user", "user", "User")]


class _Bus:
    def __init__(self) -> None:
        self.events = []

    def publish(self, envelope) -> None:
        self.events.append(envelope)


class TrainingEventContractsTest(unittest.TestCase):
    def test_comment_event_contains_required_payload_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = _FakeDocsPool(
                [
                    DocumentVersionState(
                        document_id="DOC-1",
                        version=1,
                        status=DocumentStatus.APPROVED,
                        doc_type=DocumentType.VA,
                        control_class=ControlClass.CONTROLLED,
                        owner_user_id="admin",
                    )
                ]
            )
            bus = _Bus()
            service = TrainingService(
                repository=SQLiteTrainingRepository(root / "training.db", Path("modules/training/schema.sql")),
                documents_pool_api=docs,
                usermanagement_service=_FakeUsers(),
                secure_store=EncryptedTrainingBlobStore(root / "quiz", root / "quiz.key"),
                event_bus=bus,
            )
            comment = service.add_comment("user", "DOC-1", 1, "Hinweis")
            self.assertTrue(comment.comment_id)
            event = next(e for e in bus.events if e.name == "domain.training.comment.created.v1")
            required = {"comment_id", "document_id", "version", "owner_user_id", "qmb_user_ids"}
            self.assertTrue(required.issubset(set(event.payload.keys())))

    def test_quiz_completion_event_contains_required_payload_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = _FakeDocsPool(
                [
                    DocumentVersionState(
                        document_id="DOC-2",
                        version=1,
                        status=DocumentStatus.APPROVED,
                        doc_type=DocumentType.VA,
                        control_class=ControlClass.CONTROLLED,
                        owner_user_id="admin",
                    )
                ]
            )
            bus = _Bus()
            service = TrainingService(
                repository=SQLiteTrainingRepository(root / "training.db", Path("modules/training/schema.sql")),
                documents_pool_api=docs,
                usermanagement_service=_FakeUsers(),
                secure_store=EncryptedTrainingBlobStore(root / "quiz", root / "quiz.key"),
                event_bus=bus,
            )
            service.create_category("c", "C")
            service.assign_document_to_category("c", "DOC-2")
            service.assign_user_to_category("c", "user")
            service.sync_required_assignments()
            service.confirm_read(
                user_id="user",
                document_id="DOC-2",
                version=1,
                last_page_seen=2,
                total_pages=2,
                scrolled_to_end=True,
            )
            service.import_quiz_questions(
                "DOC-2",
                1,
                json.dumps(
                    {
                        "questions": [
                            {"id": "q1", "text": "1", "options": ["A", "B", "C"], "correct_index": 0},
                            {"id": "q2", "text": "2", "options": ["A", "B", "C"], "correct_index": 0},
                            {"id": "q3", "text": "3", "options": ["A", "B", "C"], "correct_index": 0},
                        ]
                    },
                    ensure_ascii=True,
                ).encode("utf-8"),
            )
            session, _questions = service.start_quiz("user", "DOC-2", 1)
            service.submit_quiz_answers(session.session_id, [0, 0, 0])
            event = next(e for e in bus.events if e.name == "domain.training.quiz.completed.v1")
            required = {"user_id", "document_id", "version", "score", "total", "passed"}
            self.assertTrue(required.issubset(set(event.payload.keys())))


if __name__ == "__main__":
    unittest.main()
