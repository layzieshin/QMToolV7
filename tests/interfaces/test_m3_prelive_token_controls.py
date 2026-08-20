"""M3.0 pre-live hardening: token-gated controls and no invented CAS tokens."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from interfaces.clients.documents_http_ports import _comment_record
from interfaces.pyqt.contributions.documents_workflow.selection_mixin import DocumentsWorkflowSelectionMixin
from modules.documents.api import DocumentStatus, WorkflowCommentStatus


class _CommentButtonsProbe(DocumentsWorkflowSelectionMixin):
    def __init__(self) -> None:
        self._um = MagicMock()
        self._um.get_current_user.return_value = SimpleNamespace(user_id="reviewer")
        self._presenter = MagicMock()
        self._presenter.visible_actions_for_context.return_value = {"comments"}
        self._current_state = SimpleNamespace(
            document_id="DOC-1",
            version=1,
            status=DocumentStatus.IN_REVIEW,
            available_actions=frozenset({"comments"}),
        )
        self._tab_comments = MagicMock()
        self._resolve_comment_btn = MagicMock()
        self._activate_comment_btn = MagicMock()

    def _can_current_user_create_documents(self) -> bool:
        return False


def test_comment_buttons_disabled_without_row_token() -> None:
    probe = _CommentButtonsProbe()
    probe._tab_comments.currentRow.return_value = 0
    item0 = MagicMock()
    item0.data.side_effect = lambda role: "cmt-1" if role == 0x0100 else None
    item1 = MagicMock()
    item1.data.return_value = WorkflowCommentStatus.ACTIVE.value
    probe._tab_comments.item.side_effect = lambda row, col: item0 if col == 0 else item1
    probe._update_comment_action_state()
    probe._resolve_comment_btn.setEnabled.assert_called_with(False)
    probe._activate_comment_btn.setEnabled.assert_called_with(False)


def test_comment_buttons_enabled_with_action_selection_and_token() -> None:
    probe = _CommentButtonsProbe()
    probe._tab_comments.currentRow.return_value = 0
    item0 = MagicMock()
    item0.data.side_effect = lambda role: {
        0x0100: "cmt-1",
        0x0102: "2026-08-07T12:00:00+00:00",
    }.get(role)
    item1 = MagicMock()
    item1.data.return_value = WorkflowCommentStatus.ACTIVE.value
    probe._tab_comments.item.side_effect = lambda row, col: item0 if col == 0 else item1
    probe._update_comment_action_state()
    probe._resolve_comment_btn.setEnabled.assert_called_with(True)
    probe._activate_comment_btn.setEnabled.assert_called_with(False)


def test_comment_record_rejects_missing_updated_at() -> None:
    with pytest.raises(ValueError, match="missing updated_at"):
        _comment_record(
            {
                "comment_id": "c1",
                "ref_no": "C-1",
                "document_id": "DOC-1",
                "version": 1,
                "context": "PDF_REVIEW",
                "status": "ACTIVE",
                "page_number": 1,
                "preview_text": "x",
            }
        )


def test_comment_record_uses_backend_updated_at() -> None:
    record = _comment_record(
        {
            "comment_id": "c1",
            "ref_no": "C-1",
            "document_id": "DOC-1",
            "version": 1,
            "context": "PDF_REVIEW",
            "status": "ACTIVE",
            "page_number": 1,
            "preview_text": "x",
            "updated_at": "2026-08-07T12:00:00+00:00",
            "created_at": "2026-08-07T11:00:00+00:00",
            "source_kind": "PDF_APP",
        }
    )
    assert record.updated_at == datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    assert record.created_at == datetime(2026, 8, 7, 11, 0, tzinfo=timezone.utc)
