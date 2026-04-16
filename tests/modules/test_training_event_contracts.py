"""Event contract tests for the new training module."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from modules.documents.contracts import ControlClass, DocumentHeader, DocumentStatus, DocumentType, DocumentVersionState
from modules.training.secure_store import EncryptedTrainingBlobStore
from modules.training.contracts import TrainingProgress
from modules.training.training_tag_repository import TrainingTagRepository
from modules.training.training_override_repository import TrainingOverrideRepository
from modules.training.training_snapshot_repository import TrainingSnapshotRepository
from modules.training.training_quiz_repository import TrainingQuizRepository
from modules.training.training_comment_repository import TrainingCommentRepository
from modules.training.released_document_catalog_reader import ReleasedDocumentCatalogReader
from modules.training.manual_assignment_service import ManualAssignmentService
from modules.training.quiz_import_service import QuizImportService
from modules.training.quiz_binding_service import QuizBindingService
from modules.training.quiz_execution_service import QuizExecutionService
from modules.training.training_comment_service import TrainingCommentService
from modules.training.training_snapshot_projector import TrainingSnapshotProjector


@dataclass
class _FakeUser:
    user_id: str
    username: str
    role: str
    department: str | None = None
    scope: str | None = None
    organization_unit: str | None = None
    is_active: bool = True


class _FakeDocsPool:
    def __init__(self, rows):
        self._rows = rows

    def list_by_status(self, status: DocumentStatus):
        return [r for r in self._rows if r.status == status]

    def get_header(self, document_id: str):
        return DocumentHeader(
            document_id=document_id, doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED, workflow_profile_id="long_release",
        )


class _FakeUsers:
    def list_users(self):
        return [_FakeUser("qmb", "qmb", "QMB"), _FakeUser("admin", "admin", "Admin"), _FakeUser("user", "user", "User")]


class _Bus:
    def __init__(self) -> None:
        self.events = []

    def publish(self, envelope) -> None:
        self.events.append(envelope)

    def subscribe(self, name, handler) -> None:
        pass


SAMPLE_QUIZ = json.dumps({
    "document_id": "DOC-2", "document_version": 1,
    "questions": [
        {"question_id": "Q1", "text": "1", "answers": [
            {"answer_id": "a1", "text": "A"}, {"answer_id": "a2", "text": "B"},
            {"answer_id": "a3", "text": "C"}, {"answer_id": "a4", "text": "D"}],
         "correct_answer_id": "a1"},
        {"question_id": "Q2", "text": "2", "answers": [
            {"answer_id": "a1", "text": "A"}, {"answer_id": "a2", "text": "B"},
            {"answer_id": "a3", "text": "C"}, {"answer_id": "a4", "text": "D"}],
         "correct_answer_id": "a1"},
        {"question_id": "Q3", "text": "3", "answers": [
            {"answer_id": "a1", "text": "A"}, {"answer_id": "a2", "text": "B"},
            {"answer_id": "a3", "text": "C"}, {"answer_id": "a4", "text": "D"}],
         "correct_answer_id": "a1"},
    ],
}, ensure_ascii=True).encode("utf-8")


class TrainingEventContractsTest(unittest.TestCase):
    def test_comment_event_contains_required_payload_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = Path("modules/training/schema.sql")
            db = root / "t.db"
            bus = _Bus()
            comment_repo = TrainingCommentRepository(db, schema)
            svc = TrainingCommentService(comment_repo=comment_repo, event_bus=bus)
            comment = svc.add_comment("user", "DOC-1", 1, "Hinweis")
            self.assertTrue(comment.comment_id)
            event = next(e for e in bus.events if e.name == "domain.training.comment.created.v1")
            required = {"comment_id", "document_id", "version", "user_id"}
            self.assertTrue(required.issubset(set(event.payload.keys())))

    def test_quiz_completion_event_contains_required_payload_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schema = Path("modules/training/schema.sql")
            db = root / "t.db"
            bus = _Bus()
            docs = _FakeDocsPool([
                DocumentVersionState(
                    document_id="DOC-2", version=1, status=DocumentStatus.APPROVED,
                    doc_type=DocumentType.VA, control_class=ControlClass.CONTROLLED,
                    owner_user_id="admin", title="Doc2",
                ),
            ])
            tag_repo = TrainingTagRepository(db, schema)
            override_repo = TrainingOverrideRepository(db, schema)
            snapshot_repo = TrainingSnapshotRepository(db, schema)
            quiz_repo = TrainingQuizRepository(db, schema)
            secure_store = EncryptedTrainingBlobStore(root / "quiz", root / "quiz.key")
            catalog = ReleasedDocumentCatalogReader(documents_pool_api=docs)
            manual_svc = ManualAssignmentService(override_repo=override_repo, event_bus=bus)
            projector = TrainingSnapshotProjector(
                catalog_reader=catalog, snapshot_repo=snapshot_repo, tag_repo=tag_repo,
                override_repo=override_repo, usermanagement_service=_FakeUsers(), event_bus=bus,
            )
            quiz_import = QuizImportService(quiz_repo=quiz_repo, secure_store=secure_store, event_bus=bus)
            quiz_binding = QuizBindingService(quiz_repo=quiz_repo, event_bus=bus)
            quiz_exec = QuizExecutionService(
                quiz_repo=quiz_repo, snapshot_repo=snapshot_repo,
                quiz_import_service=quiz_import, event_bus=bus,
            )
            # Setup: assign + snapshot + read progress
            manual_svc.grant_manual_assignment("user", "DOC-2", "test", "admin")
            projector.rebuild_all()
            from datetime import datetime, timezone
            snapshot_repo.upsert_progress(TrainingProgress(
                user_id="user", document_id="DOC-2", version=1,
                read_confirmed_at=datetime.now(timezone.utc),
            ))
            result = quiz_import.import_quiz_json(SAMPLE_QUIZ)
            quiz_binding.bind_quiz_to_document(result.import_id, "DOC-2", 1)
            session, questions = quiz_exec.start_quiz("user", "DOC-2", 1)
            answers = [next(i for i, a in enumerate(q.answers) if a.answer_id == q.correct_answer_id) for q in questions]
            quiz_exec.submit_quiz_answers(session.session_id, answers)
            event = next(e for e in bus.events if e.name == "domain.training.quiz.completed.v1")
            required = {"user_id", "document_id", "version", "score", "total", "passed"}
            self.assertTrue(required.issubset(set(event.payload.keys())))


if __name__ == "__main__":
    unittest.main()
