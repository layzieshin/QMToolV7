from __future__ import annotations

from .contracts import (
    OpenTrainingAssignmentItem,
    QuizCapableDocumentItem,
    QuizResult,
    QuizSession,
    TrainingAssignment,
    TrainingCategory,
    TrainingComment,
    TrainingOverviewItem,
)
from .service import TrainingService


class TrainingApi:
    def __init__(self, service: TrainingService) -> None:
        self._service = service

    def list_required_for_user(self, user_id: str) -> list[TrainingAssignment]:
        return self._service.list_required_for_user(user_id)

    def list_open_assignments_for_user(self, user_id: str) -> list[OpenTrainingAssignmentItem]:
        return self._service.list_open_assignments_for_user(user_id)

    def list_training_overview_for_user(self, user_id: str) -> list[TrainingOverviewItem]:
        return self._service.list_training_overview_for_user(user_id)

    def confirm_read(
        self,
        *,
        user_id: str,
        document_id: str,
        version: int,
        last_page_seen: int,
        total_pages: int,
        scrolled_to_end: bool,
    ) -> TrainingAssignment:
        return self._service.confirm_read(
            user_id=user_id,
            document_id=document_id,
            version=version,
            last_page_seen=last_page_seen,
            total_pages=total_pages,
            scrolled_to_end=scrolled_to_end,
        )

    def start_quiz(self, user_id: str, document_id: str, version: int) -> tuple[QuizSession, list[object]]:
        return self._service.start_quiz(user_id, document_id, version)

    def submit_quiz_answers(self, session_id: str, answers: list[int]) -> QuizResult:
        return self._service.submit_quiz_answers(session_id, answers)

    def add_comment(self, user_id: str, document_id: str, version: int, comment_text: str) -> TrainingComment:
        return self._service.add_comment(user_id, document_id, version, comment_text)


class TrainingAdminApi:
    def __init__(self, service: TrainingService) -> None:
        self._service = service

    def list_approved_documents(self) -> list[object]:
        return self._service.list_approved_documents()

    def list_quiz_capable_approved_documents(self) -> list[QuizCapableDocumentItem]:
        return self._service.list_quiz_capable_approved_documents()

    def create_category(self, category_id: str, name: str, description: str | None = None) -> TrainingCategory:
        return self._service.create_category(category_id, name, description)

    def assign_document_to_category(self, category_id: str, document_id: str) -> None:
        self._service.assign_document_to_category(category_id, document_id)

    def assign_user_to_category(self, category_id: str, user_id: str) -> None:
        self._service.assign_user_to_category(category_id, user_id)

    def sync_required_assignments(self) -> int:
        return self._service.sync_required_assignments()

    def import_quiz_questions(self, document_id: str, version: int, raw_questions_json: bytes) -> str:
        return self._service.import_quiz_questions(document_id, version, raw_questions_json)

    def list_matrix(self) -> list[TrainingAssignment]:
        return self._service.list_matrix()
