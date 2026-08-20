"""Domain event publishing for documents module.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

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


def stamp_event_on_state(
    state: DocumentVersionState,
    event: object | None,
    actor_user_id: str | None = None,
) -> DocumentVersionState:
    """Stamp last_event_id/at/actor onto the version state (shared CAS token owner)."""
    if event is None:
        return state
    try:
        occurred_at_raw = getattr(event, "occurred_at_utc", None)
        occurred_at: datetime | None = datetime.fromisoformat(str(occurred_at_raw)) if occurred_at_raw else None
        if occurred_at is not None and occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    except Exception:
        occurred_at = datetime.now(timezone.utc)
    event_id = getattr(event, "event_id", None)
    event_actor = getattr(event, "actor_user_id", None)
    return replace(
        state,
        last_event_id=str(event_id) if event_id else state.last_event_id,
        last_event_at=occurred_at if occurred_at else state.last_event_at,
        last_actor_user_id=actor_user_id or event_actor or state.last_actor_user_id,
    )


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
