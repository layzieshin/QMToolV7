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
        last_actor_user_id="approver",
        archived_at=_moment(6),
        archived_by="qmb",
        edit_signature_done=True,
        last_event_at=_moment(7),
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
