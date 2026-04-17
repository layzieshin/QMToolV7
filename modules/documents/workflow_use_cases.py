from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from .contracts import (
    DocumentStatus,
    DocumentVersionState,
    RejectionReason,
    SystemRole,
    ValidityExtensionOutcome,
    WorkflowAssignments,
    WorkflowProfile,
)
from .errors import InvalidTransitionError, PermissionDeniedError, ValidationError


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp_event(
    state: DocumentVersionState,
    event: object,
    actor_user_id: str | None = None,
) -> DocumentVersionState:
    """Stamp last_event_id/at/actor onto the state so the audit trail stays current."""
    if event is None:
        return state
    try:
        occurred_at_raw = getattr(event, "occurred_at_utc", None)
        occurred_at: datetime | None = datetime.fromisoformat(str(occurred_at_raw)) if occurred_at_raw else None
        if occurred_at is not None and occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    except Exception:
        occurred_at = _utcnow()
    event_id = getattr(event, "event_id", None)
    event_actor = getattr(event, "actor_user_id", None)
    return replace(
        state,
        last_event_id=str(event_id) if event_id else state.last_event_id,
        last_event_at=occurred_at if occurred_at else state.last_event_at,
        last_actor_user_id=actor_user_id or event_actor or state.last_actor_user_id,
    )


class DocumentsWorkflowUseCases:
    def __init__(self, service: object) -> None:
        self._service = service

    def assign_workflow_roles(
        self,
        state: DocumentVersionState,
        *,
        editors: set[str],
        reviewers: set[str],
        approvers: set[str],
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if actor_user_id is not None and actor_role is not None:
            self._service._ensure_assignment_update_allowed(
                state,
                actor_user_id,
                actor_role,
                new_editors=frozenset(editors),
                new_reviewers=frozenset(reviewers),
                new_approvers=frozenset(approvers),
            )
        updated = replace(
            state,
            assignments=WorkflowAssignments(
                editors=frozenset(editors),
                reviewers=frozenset(reviewers),
                approvers=frozenset(approvers),
            ),
        )
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.assignments.updated.v1",
                updated,
                {
                    "editors_count": len(updated.assignments.editors),
                    "reviewers_count": len(updated.assignments.reviewers),
                    "approvers_count": len(updated.assignments.approvers),
                },
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.roles.assigned",
            actor=str(actor_user_id or updated.owner_user_id or "system"),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason="assign_workflow_roles",
        )
        return updated

    def start_workflow(
        self,
        state: DocumentVersionState,
        profile: WorkflowProfile,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if actor_user_id is not None and actor_role is not None:
            self._service._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        if state.status != DocumentStatus.PLANNED:
            raise InvalidTransitionError("workflow can only start from PLANNED")
        self._service._assert_profile(profile)
        if profile.control_class != state.control_class:
            raise ValidationError(
                f"profile control_class '{profile.control_class.value}' does not match document control_class '{state.control_class.value}'"
            )
        self._service._assert_assignments_for_profile(state, profile)
        updated = replace(
            state,
            status=DocumentStatus.IN_PROGRESS,
            workflow_active=True,
            workflow_profile=profile,
            workflow_profile_id=profile.profile_id,
            reviewed_by=frozenset(),
            approved_by=frozenset(),
        )
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.workflow.started.v1",
                updated,
                {"profile_id": profile.profile_id},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.started",
            actor=str(actor_user_id or updated.owner_user_id or "system"),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason=f"profile:{profile.profile_id}",
        )
        return updated

    def complete_editing(
        self,
        state: DocumentVersionState,
        *,
        sign_request: object | None = None,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if actor_user_id is not None and actor_role is not None:
            self._service._ensure_editor_or_owner_or_privileged(state, actor_user_id, actor_role)
        self._service._assert_active_profile(state)
        if state.status != DocumentStatus.IN_PROGRESS:
            raise InvalidTransitionError("editing can only be completed from IN_PROGRESS")
        self._service._ensure_source_pdf_artifact_for_signing(state, actor_user_id=actor_user_id)
        self._service._enforce_signature_transition(state, "IN_PROGRESS->IN_REVIEW", sign_request)
        next_status = self._service._next_status_from_profile(state.workflow_profile, DocumentStatus.IN_PROGRESS)
        updated = replace(state, status=next_status)
        if self._service._is_signature_required(state, "IN_PROGRESS->IN_REVIEW"):
            updated = replace(updated, edit_signature_done=True)
        now = _utcnow()
        if next_status == DocumentStatus.APPROVED:
            updated = replace(
                updated,
                approval_completed_at=now,
                approval_completed_by=actor_user_id,
                released_at=now,
                valid_from=now,
                valid_until=updated.valid_until if updated.valid_until else (now + timedelta(days=365)),
                next_review_at=now + timedelta(days=365),
                workflow_active=False,
            )
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.editing.completed.v1",
                updated,
                {"to_status": next_status.value},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            if updated.status == DocumentStatus.APPROVED:
                self._service._ensure_release_pdf_artifact(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.editing.completed",
            actor=str(actor_user_id or updated.owner_user_id or "system"),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason=f"to:{next_status.value}",
        )
        return updated

    def accept_review(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        *,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        self._service._assert_active_profile(state)
        if state.status != DocumentStatus.IN_REVIEW:
            raise InvalidTransitionError("review accept can only be executed in IN_REVIEW")
        if actor_user_id not in state.assignments.reviewers:
            raise PermissionDeniedError("actor is not assigned as reviewer")
        self._service._enforce_signature_transition(state, "IN_REVIEW->IN_APPROVAL", sign_request)
        next_status = self._service._next_status_from_profile(state.workflow_profile, DocumentStatus.IN_REVIEW)
        updated = replace(
            state,
            status=next_status,
            reviewed_by=frozenset(set(state.reviewed_by) | {actor_user_id}),
            review_completed_at=_utcnow(),
            review_completed_by=actor_user_id,
        )
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.review.accepted.v1",
                updated,
                {"actor_user_id": actor_user_id},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.review.accepted",
            actor=str(actor_user_id),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason="review_accept",
        )
        return updated

    def reject_review(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        reason: RejectionReason,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if state.status != DocumentStatus.IN_REVIEW:
            raise InvalidTransitionError("review reject can only be executed in IN_REVIEW")
        if actor_user_id not in state.assignments.reviewers:
            raise PermissionDeniedError("actor is not assigned as reviewer")
        self._service._assert_rejection_reason(reason)
        updated = replace(state, status=DocumentStatus.IN_PROGRESS)
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.review.rejected.v1",
                updated,
                {"actor_user_id": actor_user_id},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.review.rejected",
            actor=str(actor_user_id),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason=(reason.template_text or reason.free_text or "review_reject"),
        )
        return updated

    def accept_approval(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        *,
        sign_request: object | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        self._service._assert_active_profile(state)
        if state.status != DocumentStatus.IN_APPROVAL:
            raise InvalidTransitionError("approval accept can only be executed in IN_APPROVAL")
        if actor_user_id not in state.assignments.approvers:
            raise PermissionDeniedError("actor is not assigned as approver")
        if state.workflow_profile and state.workflow_profile.four_eyes_required and actor_user_id in state.reviewed_by:
            raise PermissionDeniedError("four-eyes principle prevents reviewer from approving the same version")
        self._service._enforce_signature_transition(state, "IN_APPROVAL->APPROVED", sign_request)
        now = _utcnow()
        with self._service._write_transaction():
            superseded = self._service._supersede_other_approved_versions(state, actor_user_id)
            released_at = state.released_at or now
            distribution_snapshot = self._service._build_distribution_snapshot(state)
            merged_custom_fields = dict(state.custom_fields)
            if distribution_snapshot:
                merged_custom_fields["distribution_snapshot"] = distribution_snapshot
            updated = replace(
                state,
                status=DocumentStatus.APPROVED,
                approved_by=frozenset(set(state.approved_by) | {actor_user_id}),
                approval_completed_at=now,
                approval_completed_by=actor_user_id,
                released_at=released_at,
                valid_from=state.valid_from or now,
                valid_until=state.valid_until if state.valid_until else (released_at + timedelta(days=365)),
                next_review_at=state.next_review_at or (now + timedelta(days=365)),
                workflow_active=False,
                custom_fields=merged_custom_fields,
            )
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.approval.accepted.v1",
                updated,
                {
                    "actor_user_id": actor_user_id,
                    "superseded_versions": superseded,
                    "distribution_snapshot": distribution_snapshot,
                },
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._ensure_release_pdf_artifact(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.approval.accepted",
            actor=str(actor_user_id),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason="approval_accept",
        )
        return updated

    def reject_approval(
        self,
        state: DocumentVersionState,
        actor_user_id: str,
        reason: RejectionReason,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if state.status != DocumentStatus.IN_APPROVAL:
            raise InvalidTransitionError("approval reject can only be executed in IN_APPROVAL")
        if actor_user_id not in state.assignments.approvers:
            raise PermissionDeniedError("actor is not assigned as approver")
        self._service._assert_rejection_reason(reason)
        updated = replace(state, status=DocumentStatus.IN_PROGRESS)
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.approval.rejected.v1",
                updated,
                {"actor_user_id": actor_user_id},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.approval.rejected",
            actor=str(actor_user_id),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason=(reason.template_text or reason.free_text or "approval_reject"),
        )
        return updated

    def abort_workflow(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str | None = None,
        actor_role: SystemRole | None = None,
    ) -> DocumentVersionState:
        if actor_user_id is not None and actor_role is not None:
            self._service._ensure_owner_or_privileged(state, actor_user_id, actor_role)
        if state.status not in (DocumentStatus.IN_PROGRESS, DocumentStatus.IN_REVIEW, DocumentStatus.IN_APPROVAL):
            raise InvalidTransitionError("workflow abort is only allowed during active workflow phases")
        updated = replace(state, status=DocumentStatus.PLANNED, workflow_active=False)
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.workflow.aborted.v1",
                updated,
                {},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.aborted",
            actor=str(actor_user_id or updated.owner_user_id or "system"),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason="workflow_abort",
        )
        return updated

    def archive_approved(
        self,
        state: DocumentVersionState,
        actor_role: SystemRole,
        actor_user_id: str | None = None,
    ) -> DocumentVersionState:
        if state.status != DocumentStatus.APPROVED:
            raise InvalidTransitionError("archiving is only allowed from APPROVED")
        if actor_role not in (SystemRole.QMB, SystemRole.ADMIN):
            raise PermissionDeniedError("only QMB or ADMIN can archive approved documents")
        archived_at = _utcnow()
        updated = replace(
            state,
            status=DocumentStatus.ARCHIVED,
            workflow_active=False,
            archived_at=archived_at,
            archived_by=actor_user_id,
            valid_until=archived_at,
        )
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.archived.v1",
                updated,
                {"actor_role": actor_role.value},
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.archived",
            actor=str(actor_user_id or "system"),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason=f"role:{actor_role.value}",
        )
        return updated

    def extend_annual_validity(
        self,
        state: DocumentVersionState,
        *,
        actor_user_id: str,
        signature_present: bool,
        duration_days: int,
        reason: str,
        review_outcome: ValidityExtensionOutcome,
    ) -> tuple[DocumentVersionState, bool]:
        if state.status != DocumentStatus.APPROVED:
            raise InvalidTransitionError("annual validity check is only allowed in APPROVED")
        if not actor_user_id.strip():
            raise ValidationError("annual validity extension requires actor_user_id")
        if not signature_present:
            raise ValidationError("annual validity extension requires a signature")
        if duration_days <= 0:
            raise ValidationError("annual validity extension requires a positive duration_days")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValidationError("annual validity extension requires a reason")
        if review_outcome == ValidityExtensionOutcome.NEW_VERSION_REQUIRED:
            raise InvalidTransitionError("new version is required; annual extension is not allowed")
        if state.extension_count >= 3:
            return state, True
        now = _utcnow()
        base = state.valid_until or now
        if base < now:
            base = now
        new_valid_until = base + timedelta(days=duration_days)
        updated = replace(
            state,
            extension_count=state.extension_count + 1,
            valid_until=new_valid_until,
            next_review_at=new_valid_until,
            last_extended_at=now,
            last_extended_by=actor_user_id,
            last_extension_reason=normalized_reason,
            last_extension_review_outcome=review_outcome.value,
        )
        with self._service._write_transaction():
            self._service._store_state(updated)
            event = self._service._publish(
                "domain.documents.validity.extended.v1",
                updated,
                {
                    "extension_count": updated.extension_count,
                    "old_valid_until": state.valid_until.isoformat() if state.valid_until else None,
                    "new_valid_until": updated.valid_until.isoformat() if updated.valid_until else None,
                    "old_next_review_at": state.next_review_at.isoformat() if state.next_review_at else None,
                    "new_next_review_at": updated.next_review_at.isoformat() if updated.next_review_at else None,
                    "duration_days": duration_days,
                    "reason": normalized_reason,
                    "review_outcome": review_outcome.value,
                    "actor_user_id": actor_user_id,
                },
                actor_user_id=actor_user_id,
            )
            updated = _stamp_event(updated, event, actor_user_id)
            self._service._store_state(updated)
            self._service._sync_registry(updated, event)
        self._service._emit_audit(
            action="documents.workflow.validity.extended",
            actor=str(actor_user_id or "system"),
            target=f"{updated.document_id}:{updated.version}",
            result="ok",
            reason=f"extension_count:{updated.extension_count}; outcome:{review_outcome.value}",
        )
        return updated, False

    def create_new_version_after_archive(self, state: DocumentVersionState, next_version: int) -> DocumentVersionState:
        if state.status != DocumentStatus.ARCHIVED:
            raise InvalidTransitionError("new version can only be created from ARCHIVED")
        created = DocumentVersionState(
            document_id=state.document_id,
            version=next_version,
            title=state.title,
            description=state.description,
            doc_type=state.doc_type,
            control_class=state.control_class,
            workflow_profile_id=state.workflow_profile_id,
            created_at=_utcnow(),
        )
        with self._service._write_transaction():
            self._service._store_state(created)
            self._service._sync_registry(created, None)
        return created
