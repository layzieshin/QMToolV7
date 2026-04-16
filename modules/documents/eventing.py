"""Domain event publishing for documents module.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations

from .contracts import DocumentVersionState
from qm_platform.events.event_envelope import EventEnvelope


def publish_event(
    event_bus: object | None,
    name: str,
    state: DocumentVersionState,
    payload: dict[str, object],
    *,
    actor_user_id: str | None = None,
) -> EventEnvelope | None:
    envelope = EventEnvelope.create(
        name=name,
        module_id="documents",
        actor_user_id=actor_user_id,
        payload={"document_id": state.document_id, "version": state.version, **payload},
    )
    if event_bus is None:
        return envelope
    publish = getattr(event_bus, "publish", None)
    if not callable(publish):
        return envelope
    publish(envelope)
    return envelope


def emit_audit(
    audit_logger: object | None,
    *,
    action: str,
    actor: str,
    target: str,
    result: str,
    reason: str = "",
) -> None:
    if audit_logger is None:
        return
    emit = getattr(audit_logger, "emit", None)
    if not callable(emit):
        return
    emit(action=action, actor=actor, target=target, result=result, reason=reason)

