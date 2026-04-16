"""Quiz JSON import with schema validation (§3.5, §6.5)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import QuizAnswer, QuizImportResult, QuizQuestion
from .errors import TrainingValidationError
from .secure_store import EncryptedTrainingBlobStore
from .training_quiz_repository import TrainingQuizRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuizImportService:
    def __init__(
        self,
        *,
        quiz_repo: TrainingQuizRepository,
        secure_store: EncryptedTrainingBlobStore,
        event_bus: object | None = None,
    ) -> None:
        self._repo = quiz_repo
        self._store = secure_store
        self._event_bus = event_bus

    def import_quiz_json(self, raw_quiz_json: bytes) -> QuizImportResult:
        payload = self._validate_and_parse(raw_quiz_json)
        document_id: str = payload["document_id"]
        document_version: int = payload["document_version"]
        questions = payload["questions"]

        digest = hashlib.sha256(raw_quiz_json).hexdigest()
        storage_key = self._store.put_bytes(raw_quiz_json, ".quiz")

        import_id = uuid4().hex
        now = _utcnow()
        result = QuizImportResult(
            import_id=import_id,
            document_id=document_id,
            document_version=document_version,
            question_count=len(questions),
            auto_bound=False,
            created_at=now,
        )
        self._repo.create_quiz_import(result, storage_key, digest)
        self._publish("domain.training.quiz.imported.v1", {
            "import_id": import_id,
            "document_id": document_id,
            "document_version": document_version,
            "question_count": len(questions),
        })
        return result

    def load_questions(self, import_id: str) -> list[QuizQuestion]:
        info = self._repo.get_import_storage_key(import_id)
        if info is None:
            raise TrainingValidationError("quiz import not found")
        storage_key, expected_sha = info
        raw = self._store.get_bytes(storage_key)
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            raise TrainingValidationError("quiz integrity mismatch")
        data = json.loads(raw.decode("utf-8"))
        return self._parse_questions(data["questions"])

    def load_questions_for_binding(self, document_id: str, version: int) -> list[QuizQuestion]:
        """Load questions for an active binding via quiz_repo."""
        binding = self._repo.get_active_binding(document_id, version)
        if binding is None:
            raise TrainingValidationError("no active quiz binding for this document version")
        return self.load_questions(binding.import_id)

    # --- validation ---

    def _validate_and_parse(self, raw: bytes) -> dict:
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TrainingValidationError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise TrainingValidationError("quiz payload must be an object")
        for key in ("document_id", "document_version", "questions"):
            if key not in data:
                raise TrainingValidationError(f"missing required field: {key}")
        if not isinstance(data["document_id"], str) or not data["document_id"].strip():
            raise TrainingValidationError("document_id must be a non-empty string")
        if not isinstance(data["document_version"], int):
            raise TrainingValidationError("document_version must be an integer")
        questions = data["questions"]
        if not isinstance(questions, list) or len(questions) < 3:
            raise TrainingValidationError("quiz requires at least 3 questions")
        qids: set[str] = set()
        for q in questions:
            self._validate_question(q, qids)
        return data

    def _validate_question(self, q: dict, seen_qids: set[str]) -> None:
        for key in ("question_id", "text", "answers", "correct_answer_id"):
            if key not in q:
                raise TrainingValidationError(f"question missing field: {key}")
        qid = q["question_id"]
        if qid in seen_qids:
            raise TrainingValidationError(f"duplicate question_id: {qid}")
        seen_qids.add(qid)
        answers = q["answers"]
        if not isinstance(answers, list) or len(answers) != 4:
            raise TrainingValidationError(f"question {qid}: exactly 4 answers required")
        aid_set: set[str] = set()
        for a in answers:
            if "answer_id" not in a or "text" not in a:
                raise TrainingValidationError(f"question {qid}: answer missing answer_id or text")
            aid = a["answer_id"]
            if aid in aid_set:
                raise TrainingValidationError(f"question {qid}: duplicate answer_id: {aid}")
            aid_set.add(aid)
        if q["correct_answer_id"] not in aid_set:
            raise TrainingValidationError(
                f"question {qid}: correct_answer_id '{q['correct_answer_id']}' not in answers"
            )

    @staticmethod
    def _parse_questions(raw_questions: list[dict]) -> list[QuizQuestion]:
        questions: list[QuizQuestion] = []
        for raw in raw_questions:
            answers = tuple(
                QuizAnswer(answer_id=str(a["answer_id"]), text=str(a["text"]))
                for a in raw["answers"]
            )
            questions.append(
                QuizQuestion(
                    question_id=str(raw["question_id"]),
                    text=str(raw["text"]),
                    answers=answers,
                    correct_answer_id=str(raw["correct_answer_id"]),
                )
            )
        return questions

    def _publish(self, name: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload))

