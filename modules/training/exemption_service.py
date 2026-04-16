"""Exemption / exception management (§3.8)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import TrainingExemption
from .errors import TrainingValidationError
from .training_override_repository import TrainingOverrideRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExemptionService:
    def __init__(self, *, override_repo: TrainingOverrideRepository, event_bus: object | None = None) -> None:
        self._repo = override_repo
        self._event_bus = event_bus

    def grant_exemption(
        self,
        user_id: str,
        document_id: str,
        version: int,
        reason: str,
        granted_by: str,
        valid_until: datetime | None = None,
    ) -> TrainingExemption:
        if not reason.strip():
            raise TrainingValidationError("reason is required")
        ex = TrainingExemption(
            exemption_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            reason=reason.strip(),
            granted_by=granted_by,
            granted_at=_utcnow(),
            valid_until=valid_until,
        )
        self._repo.create_exemption(ex)
        self._publish("domain.training.exemption.granted.v1", {
            "exemption_id": ex.exemption_id,
            "user_id": user_id,
            "document_id": document_id,
            "version": version,
        }, actor=granted_by)
        return ex

    def revoke_exemption(self, exemption_id: str, revoked_by: str) -> None:
        self._repo.revoke_exemption(exemption_id, _utcnow())
        self._publish("domain.training.exemption.revoked.v1", {
            "exemption_id": exemption_id,
        }, actor=revoked_by)

    def list_active(self) -> list[TrainingExemption]:
        return self._repo.list_active_exemptions()

    def list_for_user_doc(self, user_id: str, document_id: str, version: int) -> list[TrainingExemption]:
        return self._repo.list_exemptions_for_user_doc(user_id, document_id, version)

    def _publish(self, name: str, payload: dict, *, actor: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="training", payload=payload, actor_user_id=actor))

