from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from modules.documents.contracts import (
    DocumentStatus,
    DocumentVersionState,
    SystemRole,
    WorkflowCommentContext,
    WorkflowCommentListItem,
    WorkflowCommentStatus,
)
from modules.documents.errors import ValidationError
from modules.documents.repository import document_query_keyset_sort_value, document_query_sort_sql_expression
from modules.documents.service import (
    DocumentsService,
    _decode_document_query_cursor,
    _encode_document_query_cursor,
    build_version_history_events,
)


def _moment(hour: int) -> datetime:
    return datetime(2024, 6, 1, hour, 0, tzinfo=timezone.utc)


def _state(**overrides) -> DocumentVersionState:
    base = DocumentVersionState(
        document_id="DOC-A",
        version=1,
        title="Alpha",
        status=DocumentStatus.IN_PROGRESS,
        owner_user_id="owner",
        created_at=_moment(1),
        created_by="owner",
        updated_at=_moment(2),
    )
    return DocumentVersionState(**{**base.__dict__, **overrides})


def test_build_version_history_events_maps_timestamps_and_comments() -> None:
    state = replace(
        _state(),
        review_completed_at=_moment(3),
        review_completed_by="reviewer",
        approval_completed_at=_moment(4),
        approval_completed_by="approver",
        released_at=_moment(5),
        archived_at=_moment(6),
        archived_by="qmb",
        edit_signature_done=True,
        edit_signed_at=_moment(7),
        edit_signed_by="editor",
        last_event_at=_moment(9),
        last_actor_user_id="later-actor",
    )
    comment = WorkflowCommentListItem(
        comment_id="c1",
        ref_no="R1",
        document_id="DOC-A",
        version=1,
        context=WorkflowCommentContext.PDF_REVIEW,
        page_number=1,
        anchor_json=None,
        author_display="Reviewer",
        created_at=_moment(8),
        preview_text="Needs clarification on section 2",
        status=WorkflowCommentStatus.ACTIVE,
        updated_at=_moment(8),
    )
    events = build_version_history_events(state, comment_items=(comment,))
    types = [event.event_type for event in events]
    assert types == [
        "created",
        "status_changed",
        "status_changed",
        "released",
        "archived",
        "signed",
        "comment_added",
    ]
    assert all("full_text" not in event.summary for event in events)
    assert events[-1].summary == "Needs clarification on section 2"
    assert events[1].summary == "review completed"
    assert events[2].summary == "approval completed"
    signed = next(event for event in events if event.event_type == "signed")
    assert signed.occurred_at == _moment(7)
    assert signed.actor_user_id == "editor"


def test_signed_history_uses_edit_signed_fields_not_last_event() -> None:
    state = replace(
        _state(),
        edit_signature_done=True,
        edit_signed_at=_moment(4),
        edit_signed_by="signer-1",
        last_event_at=_moment(8),
        last_actor_user_id="later-actor",
    )
    events = build_version_history_events(state)
    signed = [event for event in events if event.event_type == "signed"]
    assert len(signed) == 1
    assert signed[0].occurred_at == _moment(4)
    assert signed[0].actor_user_id == "signer-1"


def test_edit_signature_done_without_edit_signed_at_does_not_emit_signed() -> None:
    state = replace(
        _state(),
        edit_signature_done=True,
        last_event_at=_moment(5),
        last_actor_user_id="editor",
    )
    events = build_version_history_events(state)
    assert "signed" not in [event.event_type for event in events]


def test_document_query_cursor_roundtrip_and_mismatch() -> None:
    state = _state(document_id="DOC-B", version=2, title="Beta")
    cursor = _encode_document_query_cursor(
        status=DocumentStatus.IN_PROGRESS,
        search_q="beta",
        sort="title",
        order="asc",
        state=state,
    )
    keyset = _decode_document_query_cursor(
        cursor,
        status=DocumentStatus.IN_PROGRESS,
        search_q="beta",
        sort="title",
        order="asc",
    )
    assert keyset.document_id == "DOC-B"
    assert keyset.version == 2
    assert keyset.sort_value == "Beta"
    with pytest.raises(ValidationError) as exc:
        _decode_document_query_cursor(
            cursor,
            status=DocumentStatus.IN_PROGRESS,
            search_q="other",
            sort="title",
            order="asc",
        )
    assert exc.value.field_errors[0]["field"] == "cursor"


def test_document_query_keyset_sort_value_prefers_updated_at_chain() -> None:
    state = _state(updated_at=None, last_event_at=_moment(9), created_at=_moment(1))
    assert document_query_keyset_sort_value(state, "updated_at") == _moment(9).isoformat()
    assert document_query_keyset_sort_value(state, "status") == DocumentStatus.IN_PROGRESS.value


def test_postgres_updated_at_sort_expression_is_timestamptz_safe() -> None:
    expr = document_query_sort_sql_expression("updated_at", dialect="postgres")
    assert expr == "COALESCE(updated_at, last_event_at, created_at)"
    assert ", '')" not in expr


def test_query_validation_rejects_invalid_sort_and_limit() -> None:
    service = DocumentsService()
    with pytest.raises(ValidationError) as sort_exc:
        service.query_document_versions_for_actor(
            actor_user_id="user",
            actor_role=SystemRole.USER,
            sort="invalid",
        )
    assert sort_exc.value.field_errors[0]["field"] == "sort"
    with pytest.raises(ValidationError) as limit_exc:
        service.query_document_versions_for_actor(
            actor_user_id="user",
            actor_role=SystemRole.USER,
            limit=101,
        )
    assert limit_exc.value.field_errors[0]["field"] == "limit"


def test_execute_sign_dispatch_routes_template_id_to_for_actor() -> None:
    from pathlib import Path

    from modules.documents.errors import SignatureTransitionError
    from modules.documents.signature_guard import execute_sign_dispatch
    from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput, SignRequest
    from modules.usermanagement.contracts import issue_user_context
    from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID

    recorded: dict[str, object] = {}

    class _Api:
        def sign_with_template_for_actor(self, actor, **kwargs):
            recorded["actor_id"] = actor.user_id
            recorded["template_id"] = kwargs["template_id"]

        def sign_with_fixed_position(self, request):
            recorded["fixed"] = True

    actor = issue_user_context(
        user_id="editor-1",
        session_id="sess",
        request_id="req",
        organization_id=INSTALLATION_ORGANIZATION_ID,
        username="editor",
        global_roles=(),
        is_qmb=False,
        authenticated_at=_moment(1),
    )
    request = SignRequest(
        input_pdf=Path("in.pdf"),
        placement=SignaturePlacementInput(page_index=0, x=1.0, y=2.0, target_width=3.0),
        layout=LabelLayoutInput(),
        signer_user="editor",
        template_id="tpl-extend",
    )
    execute_sign_dispatch(request, signature_api=_Api(), actor=actor)
    assert recorded["template_id"] == "tpl-extend"
    assert recorded["actor_id"] == "editor-1"
    assert "fixed" not in recorded

    with pytest.raises(SignatureTransitionError):
        execute_sign_dispatch(request, signature_api=_Api(), actor=None)


def test_execute_sign_dispatch_without_template_uses_fixed_position() -> None:
    from pathlib import Path

    from modules.documents.signature_guard import execute_sign_dispatch
    from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput, SignRequest

    recorded: dict[str, object] = {}

    class _Api:
        def sign_with_template_for_actor(self, actor, **kwargs):
            recorded["template"] = True

        def sign_with_fixed_position(self, request):
            recorded["fixed"] = request.reason

    request = SignRequest(
        input_pdf=Path("in.pdf"),
        placement=SignaturePlacementInput(page_index=0, x=1.0, y=2.0, target_width=3.0),
        layout=LabelLayoutInput(),
        signer_user="editor",
        reason="EXTEND_VALIDITY",
    )
    execute_sign_dispatch(request, signature_api=_Api(), actor=None)
    assert recorded["fixed"] == "EXTEND_VALIDITY"
    assert "template" not in recorded
