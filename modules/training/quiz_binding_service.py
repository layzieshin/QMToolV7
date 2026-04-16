"""Quiz binding management with replacement detection (§3.6, §6.3)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import (
    QuizBinding,
    QuizBindingReplacementResult,
    QuizReplacementCheckResult,
    PendingQuizMapping,
)
from .errors import TrainingValidationError
from .training_quiz_repository import TrainingQuizRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuizBindingService:
    def __init__(self, *, quiz_repo: TrainingQuizRepository, event_bus: object | None = None) -> None:
        self._repo = quiz_repo
        self._event_bus = event_bus

    def bind_quiz_to_document(self, import_id: str, document_id: str, version: int) -> QuizBinding:
        existing = self._repo.get_active_binding(document_id, version)
        if existing is not None:
            raise TrainingValidationError(
                f"active binding already exists for {document_id} v{version}. "
                "Use check_quiz_replacement_conflict / replace_quiz_binding."
            )
        binding = QuizBinding(
            binding_id=uuid4().hex,
            document_id=document_id,
            version=version,
            import_id=import_id,
            active=True,
            created_at=_utcnow(),
        )
        self._repo.create_binding(binding)
        self._publish("domain.training.quiz.binding.created.v1", {
            "binding_id": binding.binding_id,
            "document_id": document_id,
            "version": version,
            "import_id": import_id,
        })
        return binding

    def check_quiz_replacement_conflict(self, document_id: str, version: int, new_import_id: str) -> QuizReplacementCheckResult:
        existing = self._repo.get_active_binding(document_id, version)
        if existing is None:
            return QuizReplacementCheckResult(conflict_id=None, existing_binding=None, has_conflict=False)
        conflict_id = uuid4().hex
        self._publish("domain.training.quiz.replacement.detected.v1", {
            "conflict_id": conflict_id,
            "document_id": document_id,
            "version": version,
            "existing_binding_id": existing.binding_id,
            "new_import_id": new_import_id,
        })
        return QuizReplacementCheckResult(conflict_id=conflict_id, existing_binding=existing, has_conflict=True)

    def replace_quiz_binding(
        self, document_id: str, version: int, new_import_id: str, confirmed_by: str
    ) -> QuizBindingReplacementResult:
        existing = self._repo.get_active_binding(document_id, version)
        if existing is None:
            raise TrainingValidationError("no active binding to replace")
        now = _utcnow()
        self._repo.deactivate_binding(existing.binding_id, now, confirmed_by)
        new_binding = QuizBinding(
            binding_id=uuid4().hex,
            document_id=document_id,
            version=version,
            import_id=new_import_id,
            active=True,
            created_at=now,
        )
        self._repo.create_binding(new_binding)
        self._repo.create_replacement_history(
            uuid4().hex, existing.binding_id, new_binding.binding_id, confirmed_by, now,
        )
        result = QuizBindingReplacementResult(
            old_binding_id=existing.binding_id,
            new_binding_id=new_binding.binding_id,
            replaced_by=confirmed_by,
            replaced_at=now,
        )
        self._publish("domain.training.quiz.replaced.v1", {
            "old_binding_id": existing.binding_id,
            "new_binding_id": new_binding.binding_id,
            "document_id": document_id,
            "version": version,
            "confirmed_by": confirmed_by,
        })
        return result

    def list_quiz_bindings(self) -> list[QuizBinding]:
        return self._repo.list_bindings()

    def list_pending_quiz_mappings(self) -> list[PendingQuizMapping]:
        return self._repo.list_pending_mappings()

    def _publish(self, name: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload))

