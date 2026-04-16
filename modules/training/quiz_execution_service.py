"""Quiz execution service (§3.12)."""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import QuizQuestion, QuizResult, QuizSession, TrainingProgress
from .errors import TrainingValidationError
from .quiz_import_service import QuizImportService
from .training_quiz_repository import TrainingQuizRepository
from .training_snapshot_repository import TrainingSnapshotRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuizExecutionService:
    def __init__(
        self,
        *,
        quiz_repo: TrainingQuizRepository,
        snapshot_repo: TrainingSnapshotRepository,
        quiz_import_service: QuizImportService,
        event_bus: object | None = None,
    ) -> None:
        self._quiz_repo = quiz_repo
        self._snapshot_repo = snapshot_repo
        self._import_svc = quiz_import_service
        self._event_bus = event_bus

    def start_quiz(self, user_id: str, document_id: str, version: int) -> tuple[QuizSession, list[QuizQuestion]]:
        # Check snapshot exists
        snap = self._snapshot_repo.get_snapshot(user_id, document_id, version)
        if snap is None:
            raise TrainingValidationError("no active assignment for this document version")
        # Check read confirmed
        progress = self._snapshot_repo.get_progress(user_id, document_id, version)
        if progress is None or progress.read_confirmed_at is None:
            raise TrainingValidationError("quiz can start only after read confirmation")
        # Load questions via active binding
        questions = self._import_svc.load_questions_for_binding(document_id, version)
        selected = random.sample(questions, min(3, len(questions)))
        session = QuizSession(
            session_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            selected_question_ids=tuple(q.question_id for q in selected),
            created_at=_utcnow(),
        )
        self._quiz_repo.create_quiz_session(session)
        self._publish("domain.training.quiz.started.v1", {
            "session_id": session.session_id,
            "user_id": user_id,
            "document_id": document_id,
            "version": version,
        }, actor=user_id)
        return session, selected

    def submit_quiz_answers(self, session_id: str, answers: list[int]) -> QuizResult:
        session = self._quiz_repo.get_quiz_session(session_id)
        if session is None:
            raise TrainingValidationError("unknown quiz session")
        if len(answers) != len(session.selected_question_ids):
            raise TrainingValidationError(f"exactly {len(session.selected_question_ids)} answers are required")
        questions = self._import_svc.load_questions_for_binding(session.document_id, session.version)
        q_map = {q.question_id: q for q in questions}
        selected = [q_map[qid] for qid in session.selected_question_ids]
        score = 0
        for idx, q in enumerate(selected):
            # answers[idx] is index into shuffled/presented answers list
            # For simplicity: answers[idx] is the index of the answer in q.answers
            if 0 <= answers[idx] < len(q.answers) and q.answers[answers[idx]].answer_id == q.correct_answer_id:
                score += 1
        total = len(selected)
        passed = score == total
        now = _utcnow()
        result = QuizResult(
            session_id=session.session_id,
            user_id=session.user_id,
            document_id=session.document_id,
            version=session.version,
            score=score,
            total=total,
            passed=passed,
            completed_at=now,
        )
        self._quiz_repo.complete_quiz_session(result, answers)
        # Update progress
        progress = self._snapshot_repo.get_progress(session.user_id, session.document_id, session.version)
        attempts = (progress.quiz_attempts_count if progress else 0) + 1
        new_progress = TrainingProgress(
            user_id=session.user_id,
            document_id=session.document_id,
            version=session.version,
            read_confirmed_at=progress.read_confirmed_at if progress else None,
            quiz_passed_at=now if passed else (progress.quiz_passed_at if progress else None),
            last_score=score,
            quiz_attempts_count=attempts,
        )
        self._snapshot_repo.upsert_progress(new_progress)
        self._publish("domain.training.quiz.completed.v1", {
            "session_id": result.session_id,
            "user_id": result.user_id,
            "document_id": result.document_id,
            "version": result.version,
            "score": result.score,
            "total": result.total,
            "passed": result.passed,
        }, actor=result.user_id)
        return result

    def _publish(self, name: str, payload: dict, *, actor: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload, actor_user_id=actor))

