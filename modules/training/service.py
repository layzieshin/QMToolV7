from __future__ import annotations

import hashlib
import json
import random
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from modules.documents.contracts import DocumentStatus
from qm_platform.events.event_envelope import EventEnvelope

from .contracts import (
    OpenTrainingAssignmentItem,
    QuizCapableDocumentItem,
    QuizQuestion,
    QuizResult,
    QuizSession,
    TrainingCategory,
    TrainingComment,
    TrainingAssignment,
    TrainingAssignmentStatus,
    TrainingOverviewItem,
)
from .assignment_use_cases import TrainingAssignmentUseCases
from .errors import TrainingValidationError
from .secure_store import EncryptedTrainingBlobStore
from .sqlite_repository import SQLiteTrainingRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingService:
    def __init__(
        self,
        *,
        repository: SQLiteTrainingRepository,
        documents_pool_api: object,
        usermanagement_service: object,
        secure_store: EncryptedTrainingBlobStore,
        event_bus: object | None = None,
    ) -> None:
        self._repository = repository
        self._documents_pool_api = documents_pool_api
        self._usermanagement_service = usermanagement_service
        self._secure_store = secure_store
        self._event_bus = event_bus
        self._assignment_use_cases = TrainingAssignmentUseCases(self)

    def list_approved_documents(self) -> list[object]:
        return self._documents_pool_api.list_by_status(DocumentStatus.APPROVED)

    def create_category(self, category_id: str, name: str, description: str | None = None) -> TrainingCategory:
        if not category_id.strip():
            raise TrainingValidationError("category_id is required")
        if not name.strip():
            raise TrainingValidationError("name is required")
        category = TrainingCategory(
            category_id=category_id.strip(),
            name=name.strip(),
            description=description.strip() if description and description.strip() else None,
            created_at=_utcnow(),
        )
        self._repository.upsert_category(category)
        return category

    def assign_document_to_category(self, category_id: str, document_id: str) -> None:
        self._repository.assign_document_to_category(category_id, document_id)

    def assign_user_to_category(self, category_id: str, user_id: str) -> None:
        self._repository.assign_user_to_category(category_id, user_id)

    def sync_required_assignments(self) -> int:
        return self._assignment_use_cases.sync_required_assignments()

    def list_required_for_user(self, user_id: str) -> list[TrainingAssignment]:
        return self._repository.list_assignments_by_user(user_id)

    def list_open_assignments_for_user(self, user_id: str) -> list[OpenTrainingAssignmentItem]:
        return self._assignment_use_cases.list_open_assignments_for_user(user_id)

    def list_training_overview_for_user(self, user_id: str) -> list[TrainingOverviewItem]:
        return self._assignment_use_cases.list_training_overview_for_user(user_id)

    def list_quiz_capable_approved_documents(self) -> list[QuizCapableDocumentItem]:
        items: list[QuizCapableDocumentItem] = []
        for state in self.list_approved_documents():
            if getattr(state, "superseded_by_version", None) is not None:
                continue
            items.append(
                QuizCapableDocumentItem(
                    document_id=state.document_id,
                    version=state.version,
                    title=state.title,
                    owner_user_id=state.owner_user_id,
                )
            )
        return items

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
        return self._assignment_use_cases.confirm_read(
            user_id=user_id,
            document_id=document_id,
            version=version,
            last_page_seen=last_page_seen,
            total_pages=total_pages,
            scrolled_to_end=scrolled_to_end,
        )

    def import_quiz_questions(self, document_id: str, version: int, raw_questions_json: bytes) -> str:
        payload = json.loads(raw_questions_json.decode("utf-8"))
        if not isinstance(payload, dict):
            raise TrainingValidationError("quiz payload must be an object")
        questions = payload.get("questions")
        if not isinstance(questions, list) or len(questions) < 3:
            raise TrainingValidationError("quiz requires at least 3 questions")
        digest = hashlib.sha256(raw_questions_json).hexdigest()
        storage_key = self._secure_store.put_bytes(raw_questions_json, ".quiz")
        self._repository.upsert_quiz_set(document_id, version, storage_key, digest)
        return digest

    def start_quiz(self, user_id: str, document_id: str, version: int) -> tuple[QuizSession, list[QuizQuestion]]:
        assignment = self._repository.get_assignment(user_id, document_id, version)
        if assignment is None:
            raise TrainingValidationError("no active assignment for this document version")
        if assignment.status not in (TrainingAssignmentStatus.READ_CONFIRMED, TrainingAssignmentStatus.QUIZ_PASSED):
            raise TrainingValidationError("quiz can start only after read confirmation")
        questions = self._load_quiz_questions(document_id, version)
        selected = random.sample(questions, 3)
        session = QuizSession(
            session_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            selected_question_ids=tuple(q.question_id for q in selected),
            created_at=_utcnow(),
        )
        self._repository.create_quiz_session(session)
        return session, selected

    def submit_quiz_answers(self, session_id: str, answers: list[int]) -> QuizResult:
        session = self._repository.get_quiz_session(session_id)
        if session is None:
            raise TrainingValidationError("unknown quiz session")
        if len(answers) != 3:
            raise TrainingValidationError("exactly 3 answers are required")
        questions_map = {q.question_id: q for q in self._load_quiz_questions(session.document_id, session.version)}
        selected = [questions_map[qid] for qid in session.selected_question_ids]
        score = 0
        for idx, q in enumerate(selected):
            if answers[idx] == q.correct_index:
                score += 1
        passed = score == 3
        result = QuizResult(
            session_id=session.session_id,
            user_id=session.user_id,
            document_id=session.document_id,
            version=session.version,
            score=score,
            total=3,
            passed=passed,
            completed_at=_utcnow(),
        )
        self._repository.complete_quiz_session(result, answers)
        assignment = self._repository.get_assignment(session.user_id, session.document_id, session.version)
        if assignment is None:
            raise TrainingValidationError("assignment disappeared during quiz submit")
        updated = replace(
            assignment,
            status=TrainingAssignmentStatus.QUIZ_PASSED if passed else TrainingAssignmentStatus.READ_CONFIRMED,
            quiz_passed_at=result.completed_at if passed else assignment.quiz_passed_at,
            last_score=score,
            updated_at=_utcnow(),
        )
        self._repository.upsert_assignment(updated)
        self._publish(
            "domain.training.quiz.completed.v1",
            {
                "user_id": result.user_id,
                "document_id": result.document_id,
                "version": result.version,
                "score": result.score,
                "total": result.total,
                "passed": result.passed,
            },
            actor_user_id=result.user_id,
        )
        return result

    def add_comment(self, user_id: str, document_id: str, version: int, comment_text: str) -> TrainingComment:
        text = comment_text.strip()
        if not text:
            raise TrainingValidationError("comment_text is required")
        comment = TrainingComment(
            comment_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            comment_text=text,
            created_at=_utcnow(),
        )
        self._repository.add_comment(comment)
        owner_user_id = None
        for state in self.list_approved_documents():
            if state.document_id == document_id and state.version == version:
                owner_user_id = state.owner_user_id
                break
        qmb_users = [
            u.user_id
            for u in self._usermanagement_service.list_users()
            if getattr(u, "role", "") == "QMB"
        ]
        self._publish(
            "domain.training.comment.created.v1",
            {
                "comment_id": comment.comment_id,
                "document_id": document_id,
                "version": version,
                "owner_user_id": owner_user_id,
                "qmb_user_ids": qmb_users,
            },
            actor_user_id=user_id,
        )
        return comment

    def list_matrix(self) -> list[TrainingAssignment]:
        return self._repository.list_assignments_matrix()

    def _load_quiz_questions(self, document_id: str, version: int) -> list[QuizQuestion]:
        quiz_set = self._repository.get_quiz_set(document_id, version)
        if quiz_set is None:
            raise TrainingValidationError("quiz set not found for document version")
        storage_key, expected_sha = quiz_set
        payload = self._secure_store.get_bytes(storage_key)
        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_sha != expected_sha:
            raise TrainingValidationError("quiz set integrity mismatch")
        data = json.loads(payload.decode("utf-8"))
        raw_questions = data.get("questions", [])
        questions: list[QuizQuestion] = []
        for raw in raw_questions:
            options = tuple(str(x) for x in raw["options"])
            questions.append(
                QuizQuestion(
                    question_id=str(raw["id"]),
                    question_text=str(raw["text"]),
                    options=options,
                    correct_index=int(raw["correct_index"]),
                )
            )
        if len(questions) < 3:
            raise TrainingValidationError("quiz requires at least 3 questions")
        return questions

    def _publish(self, name: str, payload: dict[str, object], *, actor_user_id: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if not callable(publish):
            return
        publish(EventEnvelope.create(name=name, module_id="training", payload=payload, actor_user_id=actor_user_id))
