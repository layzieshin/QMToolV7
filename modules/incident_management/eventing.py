"""Timeline, audit, and domain event helpers."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import TimelineEntryType


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def new_id(prefix: str = "") -> str:
    value = uuid.uuid4().hex
    return f"{prefix}{value}" if prefix else value


def publish_event(
    event_bus: object | None,
    name: str,
    *,
    actor_user_id: str | None = None,
    payload: dict[str, object],
) -> EventEnvelope | None:
    envelope = EventEnvelope.create(
        name=name,
        module_id="incident_management",
        actor_user_id=actor_user_id,
        payload=payload,
    )
    if event_bus is None:
        return envelope
    publish = getattr(event_bus, "publish", None)
    if callable(publish):
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
    if callable(emit):
        emit(action=action, actor=actor, target=target, result=result, reason=reason)


def timeline_summary(entry_type: TimelineEntryType, **details: str) -> tuple[str, dict[str, str]]:
    mapping = {
        TimelineEntryType.SUBMITTED: "Incident submitted",
        TimelineEntryType.INQUIRY_OPENED: "Inquiry opened",
        TimelineEntryType.INQUIRY_ANSWERED: "Inquiry answered",
        TimelineEntryType.ASSESSED: "Incident assessed",
        TimelineEntryType.ACTION_CREATED: "Action created",
        TimelineEntryType.ACTION_COMPLETED: "Action completed",
        TimelineEntryType.CAPA_STARTED: "CAPA started",
        TimelineEntryType.CAPA_UPDATED: "CAPA updated",
        TimelineEntryType.RCA_CREATED: "Root cause analysis created",
        TimelineEntryType.EFFECTIVENESS_PLANNED: "Effectiveness review planned",
        TimelineEntryType.EFFECTIVENESS_REVIEWED: "Effectiveness review completed",
        TimelineEntryType.LEADERSHIP_FORWARDED: "Forwarded to leadership",
        TimelineEntryType.LEADERSHIP_ACKNOWLEDGED: "Leadership acknowledged",
        TimelineEntryType.GROUPED: "Incident grouped",
        TimelineEntryType.ARTIFACT_ATTACHED: "Artifact attached",
        TimelineEntryType.REPORT_GENERATED: "Report generated",
        TimelineEntryType.CLOSED: "Incident closed",
        TimelineEntryType.ARCHIVED: "Incident archived",
        TimelineEntryType.STATUS_CHANGED: "Status changed",
        TimelineEntryType.MANAGEMENT_REVIEW_CREATED: "Management review batch created",
        TimelineEntryType.MANAGEMENT_REVIEW_IN_DISCUSSION: "Management review in discussion",
        TimelineEntryType.MANAGEMENT_REVIEW_ACKNOWLEDGED: "Management review item acknowledged",
    }
    summary = mapping.get(entry_type, entry_type.value)
    return summary, {k: str(v) for k, v in details.items() if v is not None}


def details_json(details: dict[str, str]) -> str:
    return json.dumps(details, ensure_ascii=True, sort_keys=True)
