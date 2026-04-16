"""Public ports for the training module (§4.1).

Contains only TrainingApi and TrainingAdminApi – no business logic.
"""
from __future__ import annotations

from .contracts import (
    DocumentTagSet,
    ManualAssignment,
    PendingQuizMapping,
    QuizBinding,
    QuizBindingReplacementResult,
    QuizImportResult,
    QuizQuestion,
    QuizReplacementCheckResult,
    QuizResult,
    QuizSession,
    TrainingAssignmentSnapshot,
    TrainingAuditLogItem,
    TrainingCommentListItem,
    TrainingCommentRecord,
    TrainingDocumentRef,
    TrainingExemption,
    TrainingInboxItem,
    TrainingMatrixExportResult,
    TrainingStatistics,
    UserTagSet,
)
from .document_tag_service import DocumentTagService
from .exemption_service import ExemptionService
from .manual_assignment_service import ManualAssignmentService
from .quiz_binding_service import QuizBindingService
from .quiz_execution_service import QuizExecutionService
from .quiz_import_service import QuizImportService
from .released_document_catalog_reader import ReleasedDocumentCatalogReader
from .training_comment_service import TrainingCommentService
from .training_inbox_query_service import TrainingInboxQueryService
from .training_report_service import TrainingReportService
from .training_snapshot_projector import TrainingSnapshotProjector
from .user_tag_service import UserTagService


class TrainingApi:
    """Public user-facing API."""

    def __init__(
        self,
        *,
        inbox_query: TrainingInboxQueryService,
        quiz_execution: QuizExecutionService,
        comment_service: TrainingCommentService,
    ) -> None:
        self._inbox = inbox_query
        self._quiz = quiz_execution
        self._comments = comment_service

    def list_training_inbox_for_user(self, user_id: str, open_only: bool = False) -> list[TrainingInboxItem]:
        return self._inbox.list_training_inbox_for_user(user_id, open_only=open_only)

    def start_quiz(self, user_id: str, document_id: str, version: int) -> tuple[QuizSession, list[QuizQuestion]]:
        return self._quiz.start_quiz(user_id, document_id, version)

    def submit_quiz_answers(self, session_id: str, answers: list[int]) -> QuizResult:
        return self._quiz.submit_quiz_answers(session_id, answers)

    def add_comment(
        self, user_id: str, document_id: str, version: int, comment_text: str,
        *, document_title_snapshot: str = "", username_snapshot: str = "",
    ) -> TrainingCommentRecord:
        return self._comments.add_comment(
            user_id, document_id, version, comment_text,
            document_title_snapshot=document_title_snapshot,
            username_snapshot=username_snapshot,
        )

    def list_comments_for_document(self, document_id: str, version: int) -> list[TrainingCommentListItem]:
        return self._comments.list_comments_for_document(document_id, version)


class TrainingAdminApi:
    """Public admin/QMB API."""

    def __init__(
        self,
        *,
        catalog_reader: ReleasedDocumentCatalogReader,
        quiz_import: QuizImportService,
        quiz_binding: QuizBindingService,
        doc_tag_service: DocumentTagService,
        user_tag_service: UserTagService,
        manual_service: ManualAssignmentService,
        exemption_service: ExemptionService,
        projector: TrainingSnapshotProjector,
        comment_service: TrainingCommentService,
        report_service: TrainingReportService,
    ) -> None:
        self._catalog = catalog_reader
        self._quiz_import = quiz_import
        self._quiz_binding = quiz_binding
        self._doc_tags = doc_tag_service
        self._user_tags = user_tag_service
        self._manual = manual_service
        self._exemption = exemption_service
        self._projector = projector
        self._comments = comment_service
        self._report = report_service

    # --- Document catalog ---
    def list_assignable_documents(self) -> list[TrainingDocumentRef]:
        return self._catalog.list_released_documents()

    # --- Quiz import ---
    def import_quiz_json(self, raw_quiz_json: bytes) -> QuizImportResult:
        return self._quiz_import.import_quiz_json(raw_quiz_json)

    def list_pending_quiz_mappings(self) -> list[PendingQuizMapping]:
        return self._quiz_binding.list_pending_quiz_mappings()

    def bind_quiz_to_document(self, import_id: str, document_id: str, version: int) -> QuizBinding:
        return self._quiz_binding.bind_quiz_to_document(import_id, document_id, version)

    def list_quiz_bindings(self) -> list[QuizBinding]:
        return self._quiz_binding.list_quiz_bindings()

    def check_quiz_replacement_conflict(self, document_id: str, version: int, new_import_id: str) -> QuizReplacementCheckResult:
        return self._quiz_binding.check_quiz_replacement_conflict(document_id, version, new_import_id)

    def replace_quiz_binding(self, document_id: str, version: int, new_import_id: str, confirmed_by: str) -> QuizBindingReplacementResult:
        return self._quiz_binding.replace_quiz_binding(document_id, version, new_import_id, confirmed_by)

    # --- Tags ---
    def list_document_tags(self, document_id: str) -> DocumentTagSet:
        return self._doc_tags.list_document_tags(document_id)

    def set_document_tags(self, document_id: str, tags: list[str]) -> DocumentTagSet:
        return self._doc_tags.set_document_tags(document_id, tags)

    def list_user_tags(self, user_id: str) -> UserTagSet:
        return self._user_tags.list_user_tags(user_id)

    def set_user_tags(self, user_id: str, tags: list[str]) -> UserTagSet:
        return self._user_tags.set_user_tags(user_id, tags)

    # --- Manual assignment ---
    def grant_manual_assignment(self, user_id: str, document_id: str, reason: str, granted_by: str) -> ManualAssignment:
        return self._manual.grant_manual_assignment(user_id, document_id, reason, granted_by)

    def revoke_manual_assignment(self, assignment_id: str, revoked_by: str) -> None:
        self._manual.revoke_manual_assignment(assignment_id, revoked_by)

    # --- Exemption ---
    def grant_exemption(self, user_id: str, document_id: str, version: int, reason: str, granted_by: str, valid_until=None) -> TrainingExemption:
        return self._exemption.grant_exemption(user_id, document_id, version, reason, granted_by, valid_until)

    def revoke_exemption(self, exemption_id: str, revoked_by: str) -> None:
        self._exemption.revoke_exemption(exemption_id, revoked_by)

    # --- Snapshots ---
    def rebuild_assignment_snapshots(self) -> int:
        return self._projector.rebuild_all()

    def list_assignment_snapshots(self) -> list[TrainingAssignmentSnapshot]:
        return self._projector._snapshot_repo.list_snapshots()

    # --- Comments ---
    def list_active_comments(self) -> list[TrainingCommentListItem]:
        return self._comments.list_active_comments()

    def resolve_comment(self, comment_id: str, resolved_by: str, resolution_note: str | None = None) -> TrainingCommentRecord:
        return self._comments.resolve_comment(comment_id, resolved_by, resolution_note)

    def inactivate_comment(self, comment_id: str, inactive_by: str, inactive_note: str | None = None) -> TrainingCommentRecord:
        return self._comments.inactivate_comment(comment_id, inactive_by, inactive_note)

    # --- Reporting ---
    def get_training_statistics(self) -> TrainingStatistics:
        return self._report.get_training_statistics()

    def list_training_audit_log(self) -> list[TrainingAuditLogItem]:
        return self._report.list_training_audit_log()

    def export_training_matrix(self) -> TrainingMatrixExportResult:
        return self._report.export_training_matrix()
