"""Quiz execution service (§3.12)."""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import (
    QuizAnswer,
    QuizAnswerReview,
    QuizQuestion,
    QuizQuestionReview,
    QuizResult,
    QuizResultDetail,
    QuizSession,
    TrainingProgress,
)
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
        settings_service: object,
        event_bus: object | None = None,
    ) -> None:
        self._quiz_repo = quiz_repo
        self._snapshot_repo = snapshot_repo
        self._import_svc = quiz_import_service
        self._settings = settings_service
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
        cooldown_seconds = self._get_retry_cooldown_seconds()
        if cooldown_seconds > 0 and progress.last_failed_at is not None:
            available_at = progress.last_failed_at.timestamp() + cooldown_seconds
            now_ts = _utcnow().timestamp()
            if available_at > now_ts:
                raise TrainingValidationError("Naechster Quiz-Versuch ist noch nicht freigegeben.")
        # Load questions via active binding
        questions = self._import_svc.load_questions_for_binding(document_id, version)
        selected_count = min(self._get_questions_per_quiz(), len(questions))
        selected = random.sample(questions, selected_count)
        presented = self._build_presented_questions(selected)
        selected_for_display = self._display_questions(selected, presented)
        session = QuizSession(
            session_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            selected_question_ids=tuple(q.question_id for q in selected),
            presented_questions_json=json.dumps(presented, ensure_ascii=True),
            created_at=_utcnow(),
        )
        self._quiz_repo.create_quiz_session(session)
        self._publish("domain.training.quiz.started.v1", {
            "session_id": session.session_id,
            "user_id": user_id,
            "document_id": document_id,
            "version": version,
        }, actor=user_id)
        return session, selected_for_display

    def submit_quiz_answers(self, session_id: str, answers: list[str | int | None]) -> QuizResultDetail:
        session = self._quiz_repo.get_quiz_session(session_id)
        if session is None:
            raise TrainingValidationError("unknown quiz session")
        if len(answers) != len(session.selected_question_ids):
            raise TrainingValidationError(f"exactly {len(session.selected_question_ids)} answers are required")
        questions = self._import_svc.load_questions_for_binding(session.document_id, session.version)
        q_map = {q.question_id: q for q in questions}
        selected = [q_map[qid] for qid in session.selected_question_ids]
        presented = self._decode_presented(session.presented_questions_json, selected)
        chosen_answer_ids = self._normalize_answers(answers, presented)
        score = 0
        review_questions: list[QuizQuestionReview] = []
        for idx, q in enumerate(selected):
            chosen = chosen_answer_ids[idx]
            if chosen is not None and chosen == q.correct_answer_id:
                score += 1
            displayed_answers = self._ordered_answers(q, presented[idx]["answer_id_order"])
            answer_reviews: list[QuizAnswerReview] = []
            for answer in displayed_answers:
                answer_reviews.append(
                    QuizAnswerReview(
                        answer_id=answer.answer_id,
                        text=answer.text,
                        is_chosen=answer.answer_id == chosen,
                        is_correct=answer.answer_id == q.correct_answer_id,
                    )
                )
            review_questions.append(
                QuizQuestionReview(
                    question_id=q.question_id,
                    text=q.text,
                    answers=tuple(answer_reviews),
                    chosen_answer_id=chosen,
                    correct_answer_id=q.correct_answer_id,
                    is_correct=(chosen == q.correct_answer_id),
                )
            )
        total = len(selected)
        passed = score >= self._resolve_min_correct_answers(total)
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
        self._quiz_repo.complete_quiz_session(result, chosen_answer_ids)
        # Update progress
        progress = self._snapshot_repo.get_progress(session.user_id, session.document_id, session.version)
        attempts = (progress.quiz_attempts_count if progress else 0) + 1
        force_reread = self._get_force_reread_on_fail()
        failed_at = now if not passed else (progress.last_failed_at if progress else None)
        read_confirmed = progress.read_confirmed_at if progress else None
        if not passed and force_reread:
            read_confirmed = None
        new_progress = TrainingProgress(
            user_id=session.user_id,
            document_id=session.document_id,
            version=session.version,
            read_confirmed_at=read_confirmed,
            quiz_passed_at=now if passed else (progress.quiz_passed_at if progress else None),
            last_failed_at=failed_at,
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
        return QuizResultDetail(
            session_id=result.session_id,
            user_id=result.user_id,
            document_id=result.document_id,
            version=result.version,
            score=result.score,
            total=result.total,
            passed=result.passed,
            completed_at=result.completed_at,
            questions=tuple(review_questions),
        )

    def get_last_quiz_review(self, user_id: str, document_id: str, version: int) -> QuizResultDetail | None:
        row = self._quiz_repo.get_last_completed_attempt(user_id, document_id, version)
        if row is None:
            return None
        session = self._quiz_repo.get_quiz_session(str(row["session_id"]))
        if session is None:
            return None
        questions = self._import_svc.load_questions_for_binding(document_id, version)
        q_map = {q.question_id: q for q in questions}
        selected = [q_map[qid] for qid in session.selected_question_ids if qid in q_map]
        presented = self._decode_presented(session.presented_questions_json, selected)
        raw_answers = json.loads(str(row["answers_json"] or "[]"))
        chosen = self._normalize_answers(raw_answers, presented)
        reviews: list[QuizQuestionReview] = []
        score = 0
        for idx, q in enumerate(selected):
            chosen_id = chosen[idx] if idx < len(chosen) else None
            if chosen_id is not None and chosen_id == q.correct_answer_id:
                score += 1
            answers = tuple(
                QuizAnswerReview(
                    answer_id=a.answer_id,
                    text=a.text,
                    is_chosen=a.answer_id == chosen_id,
                    is_correct=a.answer_id == q.correct_answer_id,
                )
                for a in self._ordered_answers(q, presented[idx]["answer_id_order"])
            )
            reviews.append(
                QuizQuestionReview(
                    question_id=q.question_id,
                    text=q.text,
                    answers=answers,
                    chosen_answer_id=chosen_id,
                    correct_answer_id=q.correct_answer_id,
                    is_correct=chosen_id == q.correct_answer_id,
                )
            )
        completed_at = self._parse_iso_datetime(row.get("completed_at"))
        return QuizResultDetail(
            session_id=str(row["session_id"]),
            user_id=user_id,
            document_id=document_id,
            version=version,
            score=int(row["score"] if row["score"] is not None else score),
            total=int(row["total"] if row["total"] is not None else len(reviews)),
            passed=bool(row["passed"]),
            completed_at=completed_at or _utcnow(),
            questions=tuple(reviews),
        )

    def _module_settings(self) -> dict:
        getter = getattr(self._settings, "get_module_settings", None)
        if not callable(getter):
            return {}
        return dict(getter("training") or {})

    def _get_questions_per_quiz(self) -> int:
        settings = self._module_settings()
        value = int(settings.get("questions_per_quiz", 3) or 3)
        return max(1, value)

    def _resolve_min_correct_answers(self, total: int) -> int:
        settings = self._module_settings()
        value = int(settings.get("min_correct_answers", total) or total)
        value = max(1, value)
        return min(total, value)

    def _get_retry_cooldown_seconds(self) -> int:
        settings = self._module_settings()
        return max(0, int(settings.get("retry_cooldown_seconds", 0) or 0))

    def _get_force_reread_on_fail(self) -> bool:
        settings = self._module_settings()
        return bool(settings.get("force_reread_on_fail", False))

    def _get_shuffle_answers(self) -> bool:
        settings = self._module_settings()
        return bool(settings.get("shuffle_answers", True))

    def _build_presented_questions(self, selected: list[QuizQuestion]) -> list[dict[str, object]]:
        presented: list[dict[str, object]] = []
        for q in selected:
            answer_ids = [a.answer_id for a in q.answers]
            if self._get_shuffle_answers():
                random.shuffle(answer_ids)
            presented.append({"question_id": q.question_id, "answer_id_order": answer_ids})
        return presented

    def _display_questions(self, selected: list[QuizQuestion], presented: list[dict[str, object]]) -> list[QuizQuestion]:
        by_id = {q.question_id: q for q in selected}
        rendered: list[QuizQuestion] = []
        for item in presented:
            q = by_id[str(item["question_id"])]
            ordered = self._ordered_answers(q, list(item["answer_id_order"]))
            rendered.append(
                QuizQuestion(
                    question_id=q.question_id,
                    text=q.text,
                    answers=tuple(ordered),
                    correct_answer_id=q.correct_answer_id,
                )
            )
        return rendered

    @staticmethod
    def _ordered_answers(question: QuizQuestion, answer_order: list[str]) -> list[QuizAnswer]:
        by_id = {a.answer_id: a for a in question.answers}
        ordered = [by_id[aid] for aid in answer_order if aid in by_id]
        if len(ordered) != len(question.answers):
            ordered = list(question.answers)
        return ordered

    def _decode_presented(self, raw: str, selected: list[QuizQuestion]) -> list[dict[str, object]]:
        try:
            decoded = json.loads(raw or "[]")
            if isinstance(decoded, list) and len(decoded) == len(selected):
                return decoded
        except Exception:
            pass
        return [
            {"question_id": q.question_id, "answer_id_order": [a.answer_id for a in q.answers]}
            for q in selected
        ]

    def _normalize_answers(
        self,
        answers: list[str | int | None],
        presented: list[dict[str, object]],
    ) -> list[str | None]:
        normalized: list[str | None] = []
        for idx, value in enumerate(answers):
            answer_ids = [str(v) for v in presented[idx].get("answer_id_order", [])]
            if isinstance(value, str):
                normalized.append(value if value in answer_ids else None)
                continue
            if isinstance(value, int):
                if 0 <= value < len(answer_ids):
                    normalized.append(answer_ids[value])
                else:
                    normalized.append(None)
                continue
            normalized.append(None)
        return normalized

    @staticmethod
    def _parse_iso_datetime(raw: object) -> datetime | None:
        if raw is None:
            return None
        text = str(raw).strip()
        if not text:
            return None
        value = datetime.fromisoformat(text)
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _publish(self, name: str, payload: dict, *, actor: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload, actor_user_id=actor))

