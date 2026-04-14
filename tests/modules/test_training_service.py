from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from modules.documents.contracts import DocumentStatus, DocumentType, ControlClass, DocumentVersionState
from modules.training.secure_store import EncryptedTrainingBlobStore
from modules.training.service import TrainingService
from modules.training.sqlite_repository import SQLiteTrainingRepository


@dataclass
class _FakeUser:
    user_id: str
    username: str
    role: str


class _FakeDocsPool:
    def __init__(self, rows: list[DocumentVersionState]) -> None:
        self._rows = rows

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        return [r for r in self._rows if r.status == status]


class _FakeUserService:
    def list_users(self) -> list[_FakeUser]:
        return [
            _FakeUser(user_id="admin", username="admin", role="Admin"),
            _FakeUser(user_id="qmb", username="qmb", role="QMB"),
            _FakeUser(user_id="user", username="user", role="User"),
        ]


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[str] = []

    def publish(self, event) -> None:
        self.events.append(event.name)


class TrainingServiceTest(unittest.TestCase):
    def test_assignment_quiz_comment_flow(self) -> None:
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
            bus = _FakeBus()
            repository = SQLiteTrainingRepository(root / "training.db", Path("modules/training/schema.sql"))
            secure_store = EncryptedTrainingBlobStore(root / "quiz", root / "quiz.key")
            service = TrainingService(
                repository=repository,
                documents_pool_api=docs,
                usermanagement_service=_FakeUserService(),
                secure_store=secure_store,
                event_bus=bus,
            )
            service.create_category("cat-1", "Pflicht")
            service.assign_document_to_category("cat-1", "DOC-1")
            service.assign_user_to_category("cat-1", "user")
            self.assertGreaterEqual(service.sync_required_assignments(), 1)
            required = service.list_required_for_user("user")
            self.assertEqual(len(required), 1)
            self.assertEqual(required[0].status.value, "ASSIGNED")
            updated = service.confirm_read(
                user_id="user",
                document_id="DOC-1",
                version=1,
                last_page_seen=5,
                total_pages=5,
                scrolled_to_end=True,
            )
            self.assertEqual(updated.status.value, "READ_CONFIRMED")
            service.import_quiz_questions(
                "DOC-1",
                1,
                json.dumps(
                    {
                        "questions": [
                            {"id": "q1", "text": "a", "options": ["1", "2", "3"], "correct_index": 0},
                            {"id": "q2", "text": "b", "options": ["1", "2", "3"], "correct_index": 1},
                            {"id": "q3", "text": "c", "options": ["1", "2", "3"], "correct_index": 2},
                            {"id": "q4", "text": "d", "options": ["1", "2", "3"], "correct_index": 0},
                        ]
                    },
                    ensure_ascii=True,
                ).encode("utf-8"),
            )
            session, questions = service.start_quiz("user", "DOC-1", 1)
            answers = [q.correct_index for q in questions]
            result = service.submit_quiz_answers(session.session_id, answers)
            self.assertTrue(result.passed)
            comment = service.add_comment("user", "DOC-1", 1, "Bitte Abschnitt 3 anpassen")
            self.assertTrue(comment.comment_id)
            self.assertIn("domain.training.comment.created.v1", bus.events)


if __name__ == "__main__":
    unittest.main()
