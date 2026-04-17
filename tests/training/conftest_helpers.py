"""Shared test helpers for training tests."""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from modules.documents.contracts import (
    ControlClass, DocumentHeader, DocumentStatus, DocumentType, DocumentVersionState,
)
from modules.training.secure_store import EncryptedTrainingBlobStore
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


SCHEMA_PATH = Path("modules/training/schema.sql")

SAMPLE_QUIZ_JSON = json.dumps({
    "document_id": "DOC-1", "document_version": 1,
    "questions": [
        {"question_id": f"Q{i}", "text": f"F{i}", "answers": [
            {"answer_id": "a1", "text": "A"}, {"answer_id": "a2", "text": "B"},
            {"answer_id": "a3", "text": "C"}, {"answer_id": "a4", "text": "D"}],
         "correct_answer_id": "a1"} for i in range(1, 5)
    ],
}, ensure_ascii=True).encode("utf-8")


@dataclass
class FakeUser:
    user_id: str
    username: str
    role: str
    department: str | None = None
    scope: str | None = None
    organization_unit: str | None = None
    is_active: bool = True


class FakeDocsPool:
    def __init__(self, rows=None):
        self._rows = rows or [
            DocumentVersionState(
                document_id="DOC-1", version=1, status=DocumentStatus.APPROVED,
                doc_type=DocumentType.VA, control_class=ControlClass.CONTROLLED,
                owner_user_id="admin", title="Test Doc",
            ),
        ]

    def list_by_status(self, status):
        return [r for r in self._rows if r.status == status]

    def get_header(self, document_id):
        return DocumentHeader(
            document_id=document_id, doc_type=DocumentType.VA,
            control_class=ControlClass.CONTROLLED, workflow_profile_id="long_release",
        )


class FakeUserService:
    def list_users(self):
        return [
            FakeUser("admin", "admin", "Admin"),
            FakeUser("qmb", "qmb", "QMB"),
            FakeUser("user", "user", "User"),
        ]


class FakeBus:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)

    def subscribe(self, name, handler):
        pass

    def event_names(self):
        return [e.name for e in self.events]


class FakeSettingsService:
    def __init__(self) -> None:
        self._modules = {
            "training": {
                "questions_per_quiz": 3,
                "min_correct_answers": 3,
                "shuffle_answers": True,
                "retry_cooldown_seconds": 0,
                "force_reread_on_fail": False,
            }
        }

    def get_module_settings(self, module_id: str):
        return dict(self._modules.get(module_id, {}))


def make_repos(root: Path):
    db = root / "training.db"
    return {
        "tag_repo": TrainingTagRepository(db, SCHEMA_PATH),
        "override_repo": TrainingOverrideRepository(db, SCHEMA_PATH),
        "snapshot_repo": TrainingSnapshotRepository(db, SCHEMA_PATH),
        "quiz_repo": TrainingQuizRepository(db, SCHEMA_PATH),
        "comment_repo": TrainingCommentRepository(db, SCHEMA_PATH),
        "report_repo": TrainingReportRepository(db, SCHEMA_PATH),
    }


def make_full_stack(root: Path):
    repos = make_repos(root)
    bus = FakeBus()
    docs = FakeDocsPool()
    um = FakeUserService()
    secure_store = EncryptedTrainingBlobStore(root / "quiz", root / "quiz.key")
    catalog = ReleasedDocumentCatalogReader(documents_pool_api=docs)
    settings = FakeSettingsService()
    quiz_import = QuizImportService(
        quiz_repo=repos["quiz_repo"],
        secure_store=secure_store,
        catalog_reader=catalog,
        event_bus=bus,
    )
    quiz_binding = QuizBindingService(quiz_repo=repos["quiz_repo"], event_bus=bus)
    projector = TrainingSnapshotProjector(
        catalog_reader=catalog, snapshot_repo=repos["snapshot_repo"], tag_repo=repos["tag_repo"],
        override_repo=repos["override_repo"], usermanagement_service=um, event_bus=bus,
    )
    inbox = TrainingInboxQueryService(
        snapshot_repo=repos["snapshot_repo"], quiz_repo=repos["quiz_repo"], catalog_reader=catalog,
    )
    quiz_exec = QuizExecutionService(
        quiz_repo=repos["quiz_repo"], snapshot_repo=repos["snapshot_repo"],
        quiz_import_service=quiz_import, settings_service=settings, event_bus=bus,
    )
    comment_svc = TrainingCommentService(comment_repo=repos["comment_repo"], event_bus=bus)
    report_svc = TrainingReportService(report_repo=repos["report_repo"], event_bus=bus)
    manual_svc = ManualAssignmentService(override_repo=repos["override_repo"], event_bus=bus)
    exemption_svc = ExemptionService(override_repo=repos["override_repo"], event_bus=bus)
    doc_tag_svc = DocumentTagService(tag_repo=repos["tag_repo"])
    user_tag_svc = UserTagService(tag_repo=repos["tag_repo"])
    return {
        **repos, "bus": bus, "catalog": catalog,
        "settings": settings,
        "quiz_import": quiz_import, "quiz_binding": quiz_binding,
        "projector": projector, "inbox": inbox, "quiz_exec": quiz_exec,
        "comment_svc": comment_svc, "report_svc": report_svc,
        "manual_svc": manual_svc, "exemption_svc": exemption_svc,
        "doc_tag_svc": doc_tag_svc, "user_tag_svc": user_tag_svc,
    }

