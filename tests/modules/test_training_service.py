"""Integration test for the new training module (clean-slate)."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from modules.documents.contracts import DocumentStatus, DocumentType, ControlClass, DocumentVersionState, DocumentHeader
from modules.training.secure_store import EncryptedTrainingBlobStore
from modules.training.contracts import CommentStatus
from modules.training.training_tag_repository import TrainingTagRepository
from modules.training.training_override_repository import TrainingOverrideRepository
from modules.training.training_snapshot_repository import TrainingSnapshotRepository
from modules.training.training_quiz_repository import TrainingQuizRepository
from modules.training.training_comment_repository import TrainingCommentRepository
from modules.training.training_report_repository import TrainingReportRepository
from modules.training.released_document_catalog_reader import ReleasedDocumentCatalogReader
from modules.training.document_tag_service import DocumentTagService
from modules.training.user_tag_service import UserTagService
from modules.training.quiz_import_service import QuizImportService
from modules.training.quiz_binding_service import QuizBindingService
from modules.training.manual_assignment_service import ManualAssignmentService
from modules.training.exemption_service import ExemptionService
from modules.training.training_snapshot_projector import TrainingSnapshotProjector
from modules.training.training_inbox_query_service import TrainingInboxQueryService
from modules.training.quiz_execution_service import QuizExecutionService
from modules.training.training_comment_service import TrainingCommentService
from modules.training.training_report_service import TrainingReportService


SAMPLE_QUIZ_JSON = json.dumps(
    {
        "document_id": "DOC-1",
        "document_version": 1,
        "questions": [
            {
                "question_id": "Q1",
                "text": "F1",
                "answers": [
                    {"answer_id": "a1", "text": "A"},
                    {"answer_id": "a2", "text": "B"},
                    {"answer_id": "a3", "text": "C"},
                    {"answer_id": "a4", "text": "D"},
                ],
                "correct_answer_id": "a1",
            },
            {
                "question_id": "Q2",
                "text": "F2",
                "answers": [
                    {"answer_id": "a1", "text": "A"},
                    {"answer_id": "a2", "text": "B"},
                    {"answer_id": "a3", "text": "C"},
                    {"answer_id": "a4", "text": "D"},
                ],
                "correct_answer_id": "a2",
            },
            {
                "question_id": "Q3",
                "text": "F3",
                "answers": [
                    {"answer_id": "a1", "text": "A"},
                    {"answer_id": "a2", "text": "B"},
                    {"answer_id": "a3", "text": "C"},
                    {"answer_id": "a4", "text": "D"},
                ],
                "correct_answer_id": "a3",
            },
            {
                "question_id": "Q4",
                "text": "F4",
                "answers": [
                    {"answer_id": "a1", "text": "A"},
                    {"answer_id": "a2", "text": "B"},
                    {"answer_id": "a3", "text": "C"},
                    {"answer_id": "a4", "text": "D"},
                ],
                "correct_answer_id": "a1",
            },
        ],
    },
    ensure_ascii=True,
).encode("utf-8")


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
    def __init__(self, rows: list[DocumentVersionState]) -> None:
        self._rows = rows

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        return [r for r in self._rows if r.status == status]

    def get_header(self, document_id: str) -> DocumentHeader | None:
        return DocumentHeader(
            document_id=document_id, doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED, workflow_profile_id="long_release",
        )


class _FakeUserService:
    def list_users(self) -> list[_FakeUser]:
        return [
            _FakeUser(user_id="admin", username="admin", role="Admin"),
            _FakeUser(user_id="qmb", username="qmb", role="QMB"),
            _FakeUser(user_id="user", username="user", role="User"),
        ]


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[object] = []

    def publish(self, event) -> None:
        self.events.append(event)

    def subscribe(self, name, handler) -> None:
        pass


def _make_services(root: Path):
    schema = Path("modules/training/schema.sql")
    db = root / "training.db"
    tag_repo = TrainingTagRepository(db, schema)
    override_repo = TrainingOverrideRepository(db, schema)
    snapshot_repo = TrainingSnapshotRepository(db, schema)
    quiz_repo = TrainingQuizRepository(db, schema)
    comment_repo = TrainingCommentRepository(db, schema)
    report_repo = TrainingReportRepository(db, schema)
    secure_store = EncryptedTrainingBlobStore(root / "quiz", root / "quiz.key")
    bus = _FakeBus()
    docs = _FakeDocsPool([
        DocumentVersionState(
            document_id="DOC-1", version=1, status=DocumentStatus.APPROVED,
            doc_type=DocumentType.VA, control_class=ControlClass.CONTROLLED,
            owner_user_id="admin", title="Test Doc",
        ),
    ])
    um = _FakeUserService()
    catalog = ReleasedDocumentCatalogReader(documents_pool_api=docs)
    quiz_import = QuizImportService(quiz_repo=quiz_repo, secure_store=secure_store, event_bus=bus)
    quiz_binding = QuizBindingService(quiz_repo=quiz_repo, event_bus=bus)
    projector = TrainingSnapshotProjector(
        catalog_reader=catalog, snapshot_repo=snapshot_repo, tag_repo=tag_repo,
        override_repo=override_repo, usermanagement_service=um, event_bus=bus,
    )
    inbox = TrainingInboxQueryService(snapshot_repo=snapshot_repo, quiz_repo=quiz_repo, catalog_reader=catalog)
    quiz_exec = QuizExecutionService(
        quiz_repo=quiz_repo, snapshot_repo=snapshot_repo,
        quiz_import_service=quiz_import, event_bus=bus,
    )
    comment_svc = TrainingCommentService(comment_repo=comment_repo, event_bus=bus)
    report_svc = TrainingReportService(report_repo=report_repo, event_bus=bus)
    manual_svc = ManualAssignmentService(override_repo=override_repo, event_bus=bus)
    exemption_svc = ExemptionService(override_repo=override_repo, event_bus=bus)
    doc_tag_svc = DocumentTagService(tag_repo=tag_repo)
    user_tag_svc = UserTagService(tag_repo=tag_repo)
    return {
        "bus": bus, "snapshot_repo": snapshot_repo, "quiz_import": quiz_import,
        "quiz_binding": quiz_binding, "projector": projector, "inbox": inbox,
        "quiz_exec": quiz_exec, "comment_svc": comment_svc, "report_svc": report_svc,
        "manual_svc": manual_svc, "exemption_svc": exemption_svc,
        "doc_tag_svc": doc_tag_svc, "user_tag_svc": user_tag_svc,
    }


class TrainingServiceTest(unittest.TestCase):
    def test_full_training_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            s = _make_services(root)
            # 1. manual assignment + rebuild snapshots
            s["manual_svc"].grant_manual_assignment("user", "DOC-1", "Pflicht", "admin")
            count = s["projector"].rebuild_all()
            self.assertGreaterEqual(count, 1)
            # 2. inbox
            inbox = s["inbox"].list_training_inbox_for_user("user")
            self.assertEqual(len(inbox), 1)
            self.assertFalse(inbox[0].read_confirmed)
            # 3. simulate read confirmation via progress
            from modules.training.contracts import TrainingProgress
            from datetime import datetime, timezone
            s["snapshot_repo"].upsert_progress(TrainingProgress(
                user_id="user", document_id="DOC-1", version=1,
                read_confirmed_at=datetime.now(timezone.utc),
            ))
            # 4. import quiz + bind
            result = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            self.assertEqual(result.question_count, 4)
            binding = s["quiz_binding"].bind_quiz_to_document(result.import_id, "DOC-1", 1)
            self.assertTrue(binding.active)
            # 5. start + submit quiz
            session, questions = s["quiz_exec"].start_quiz("user", "DOC-1", 1)
            self.assertEqual(len(questions), 3)
            # find correct indices
            answers = []
            for q in questions:
                idx = next(i for i, a in enumerate(q.answers) if a.answer_id == q.correct_answer_id)
                answers.append(idx)
            qr = s["quiz_exec"].submit_quiz_answers(session.session_id, answers)
            self.assertTrue(qr.passed)
            # 6. comment
            comment = s["comment_svc"].add_comment("user", "DOC-1", 1, "Hinweis")
            self.assertEqual(comment.status, CommentStatus.ACTIVE)
            active = s["comment_svc"].list_active_comments()
            self.assertEqual(len(active), 1)
            # 7. resolve comment
            s["comment_svc"].resolve_comment(comment.comment_id, "qmb")
            active2 = s["comment_svc"].list_active_comments()
            self.assertEqual(len(active2), 0)
            # 8. events published
            event_names = [e.name for e in s["bus"].events]
            self.assertIn("domain.training.quiz.imported.v1", event_names)
            self.assertIn("domain.training.quiz.binding.created.v1", event_names)
            self.assertIn("domain.training.quiz.started.v1", event_names)
            self.assertIn("domain.training.quiz.completed.v1", event_names)
            self.assertIn("domain.training.comment.created.v1", event_names)
            self.assertIn("domain.training.comment.resolved.v1", event_names)


if __name__ == "__main__":
    unittest.main()
