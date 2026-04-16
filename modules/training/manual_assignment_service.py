"""Manual assignment management (§3.7)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import ManualAssignment
from .errors import TrainingValidationError
from .training_override_repository import TrainingOverrideRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ManualAssignmentService:
    def __init__(self, *, override_repo: TrainingOverrideRepository, event_bus: object | None = None) -> None:
        self._repo = override_repo
        self._event_bus = event_bus

    def grant_manual_assignment(self, user_id: str, document_id: str, reason: str, granted_by: str) -> ManualAssignment:
        if not reason.strip():
            raise TrainingValidationError("reason is required")
        ma = ManualAssignment(
            assignment_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            reason=reason.strip(),
            granted_by=granted_by,
            granted_at=_utcnow(),
        )
        self._repo.create_manual_assignment(ma)
        self._publish("domain.training.manual_assignment.granted.v1", {
            "assignment_id": ma.assignment_id,
            "user_id": user_id,
            "document_id": document_id,
        }, actor=granted_by)
        return ma

    def revoke_manual_assignment(self, assignment_id: str, revoked_by: str) -> None:
        self._repo.revoke_manual_assignment(assignment_id, _utcnow())
        self._publish("domain.training.manual_assignment.revoked.v1", {
            "assignment_id": assignment_id,
        }, actor=revoked_by)

    def list_active(self) -> list[ManualAssignment]:
        return self._repo.list_active_manual_assignments()

    def list_for_user(self, user_id: str) -> list[ManualAssignment]:
        return self._repo.list_manual_assignments_for_user(user_id)

    def _publish(self, name: str, payload: dict, *, actor: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload, actor_user_id=actor))

