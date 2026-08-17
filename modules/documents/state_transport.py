"""JSON transport for DocumentVersionState (HTTP adapter boundary)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .contracts import (
    ControlClass,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    WorkflowAssignments,
    WorkflowProfile,
)


def _dt_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _dt_from_str(raw: object | None) -> datetime | None:
    if raw is None or raw == "":
        return None
    return datetime.fromisoformat(str(raw))


def _profile_to_dict(profile: WorkflowProfile | None) -> dict[str, object] | None:
    if profile is None:
        return None
    return {
        "profile_id": profile.profile_id,
        "label": profile.label,
        "phases": [phase.value for phase in profile.phases],
        "four_eyes_required": profile.four_eyes_required,
        "control_class": profile.control_class.value,
        "signature_required_transitions": list(profile.signature_required_transitions),
        "requires_editors": profile.requires_editors,
        "requires_reviewers": profile.requires_reviewers,
        "requires_approvers": profile.requires_approvers,
        "allows_content_changes": profile.allows_content_changes,
        "release_evidence_mode": profile.release_evidence_mode,
    }


def _profile_from_dict(data: dict[str, object] | None) -> WorkflowProfile | None:
    if not data:
        return None
    return WorkflowProfile(
        profile_id=str(data["profile_id"]),
        label=str(data["label"]),
        phases=tuple(DocumentStatus(str(value)) for value in data.get("phases", [])),
        four_eyes_required=bool(data.get("four_eyes_required", False)),
        control_class=ControlClass(str(data.get("control_class", "CONTROLLED"))),
        signature_required_transitions=tuple(str(v) for v in data.get("signature_required_transitions", [])),
        requires_editors=bool(data.get("requires_editors", True)),
        requires_reviewers=bool(data.get("requires_reviewers", True)),
        requires_approvers=bool(data.get("requires_approvers", True)),
        allows_content_changes=bool(data.get("allows_content_changes", True)),
        release_evidence_mode=str(data.get("release_evidence_mode", "WORKFLOW")),
    )


def document_version_state_to_payload(state: DocumentVersionState) -> dict[str, Any]:
    assignments = state.assignments
    payload: dict[str, Any] = {
        "document_id": state.document_id,
        "version": state.version,
        "title": state.title,
        "description": state.description,
        "doc_type": state.doc_type.value,
        "control_class": state.control_class.value,
        "workflow_profile_id": state.workflow_profile_id,
        "owner_user_id": state.owner_user_id,
        "status": state.status.value,
        "workflow_active": state.workflow_active,
        "workflow_profile": _profile_to_dict(state.workflow_profile),
        "assignments": {
            "editors": sorted(assignments.editors),
            "reviewers": sorted(assignments.reviewers),
            "approvers": sorted(assignments.approvers),
        },
        "reviewed_by": sorted(state.reviewed_by),
        "approved_by": sorted(state.approved_by),
        "edit_signature_done": state.edit_signature_done,
        "valid_from": _dt_to_str(state.valid_from),
        "valid_until": _dt_to_str(state.valid_until),
        "next_review_at": _dt_to_str(state.next_review_at),
        "review_completed_at": _dt_to_str(state.review_completed_at),
        "review_completed_by": state.review_completed_by,
        "approval_completed_at": _dt_to_str(state.approval_completed_at),
        "approval_completed_by": state.approval_completed_by,
        "released_at": _dt_to_str(state.released_at),
        "archived_at": _dt_to_str(state.archived_at),
        "archived_by": state.archived_by,
        "superseded_by_version": state.superseded_by_version,
        "extension_count": state.extension_count,
        "last_extended_at": _dt_to_str(state.last_extended_at),
        "last_extended_by": state.last_extended_by,
        "last_extension_reason": state.last_extension_reason,
        "last_extension_review_outcome": state.last_extension_review_outcome,
        "custom_fields": dict(state.custom_fields),
        "last_event_id": state.last_event_id,
        "last_event_at": _dt_to_str(state.last_event_at),
        "last_actor_user_id": state.last_actor_user_id,
        "created_at": _dt_to_str(state.created_at),
        "created_by": state.created_by,
    }
    if state.available_actions is not None:
        payload["available_actions"] = sorted(state.available_actions)
    return payload


def document_version_state_from_payload(payload: dict[str, Any]) -> DocumentVersionState:
    raw_assignments = payload.get("assignments") or {}
    if not isinstance(raw_assignments, dict):
        raw_assignments = {}
    profile_raw = payload.get("workflow_profile")
    profile_dict = profile_raw if isinstance(profile_raw, dict) else None
    custom = payload.get("custom_fields") or {}
    if not isinstance(custom, dict):
        custom = {}
    return DocumentVersionState(
        document_id=str(payload["document_id"]),
        version=int(payload["version"]),
        title=str(payload.get("title") or ""),
        description=str(payload["description"]) if payload.get("description") else None,
        doc_type=DocumentType(str(payload.get("doc_type", DocumentType.OTHER.value))),
        control_class=ControlClass(str(payload.get("control_class", ControlClass.CONTROLLED.value))),
        workflow_profile_id=str(payload.get("workflow_profile_id") or "long_release"),
        owner_user_id=str(payload["owner_user_id"]) if payload.get("owner_user_id") else None,
        status=DocumentStatus(str(payload["status"])),
        workflow_active=bool(payload.get("workflow_active", False)),
        workflow_profile=_profile_from_dict(profile_dict),
        assignments=WorkflowAssignments(
            editors=frozenset(str(v) for v in raw_assignments.get("editors", [])),
            reviewers=frozenset(str(v) for v in raw_assignments.get("reviewers", [])),
            approvers=frozenset(str(v) for v in raw_assignments.get("approvers", [])),
        ),
        reviewed_by=frozenset(str(v) for v in payload.get("reviewed_by", [])),
        approved_by=frozenset(str(v) for v in payload.get("approved_by", [])),
        edit_signature_done=bool(payload.get("edit_signature_done", False)),
        valid_from=_dt_from_str(payload.get("valid_from")),
        valid_until=_dt_from_str(payload.get("valid_until")),
        next_review_at=_dt_from_str(payload.get("next_review_at")),
        review_completed_at=_dt_from_str(payload.get("review_completed_at")),
        review_completed_by=str(payload["review_completed_by"]) if payload.get("review_completed_by") else None,
        approval_completed_at=_dt_from_str(payload.get("approval_completed_at")),
        approval_completed_by=str(payload["approval_completed_by"]) if payload.get("approval_completed_by") else None,
        released_at=_dt_from_str(payload.get("released_at")),
        archived_at=_dt_from_str(payload.get("archived_at")),
        archived_by=str(payload["archived_by"]) if payload.get("archived_by") else None,
        superseded_by_version=int(payload["superseded_by_version"]) if payload.get("superseded_by_version") is not None else None,
        extension_count=int(payload.get("extension_count", 0)),
        last_extended_at=_dt_from_str(payload.get("last_extended_at")),
        last_extended_by=str(payload["last_extended_by"]) if payload.get("last_extended_by") else None,
        last_extension_reason=str(payload["last_extension_reason"]) if payload.get("last_extension_reason") else None,
        last_extension_review_outcome=str(payload["last_extension_review_outcome"])
        if payload.get("last_extension_review_outcome")
        else None,
        custom_fields=dict(custom),
        last_event_id=str(payload["last_event_id"]) if payload.get("last_event_id") else None,
        last_event_at=_dt_from_str(payload.get("last_event_at")),
        last_actor_user_id=str(payload["last_actor_user_id"]) if payload.get("last_actor_user_id") else None,
        created_at=_dt_from_str(payload.get("created_at")),
        created_by=str(payload["created_by"]) if payload.get("created_by") else None,
        available_actions=(
            frozenset(str(value) for value in payload.get("available_actions", []))
            if "available_actions" in payload
            else None
        ),
    )


def document_version_state_to_json(state: DocumentVersionState) -> str:
    return json.dumps(document_version_state_to_payload(state), ensure_ascii=True)


def document_version_state_from_json(raw: str) -> DocumentVersionState:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("document version state payload must be an object")
    return document_version_state_from_payload(payload)
