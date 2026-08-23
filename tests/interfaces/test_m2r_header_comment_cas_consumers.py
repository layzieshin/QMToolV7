"""M2R consumer CAS: header If-Match and comment-status If-Match."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from interfaces.clients.documents_http import DocumentsHttpClient
from interfaces.clients.documents_http_ports import HttpDocumentsCommentsApi, HttpDocumentsWorkflowApi
from interfaces.pyqt.contributions.documents_workflow.actions_mixin import DocumentsWorkflowActionsMixin
from interfaces.pyqt.contributions.documents_workflow.selection_mixin import DocumentsWorkflowSelectionMixin
from modules.documents.api import (
    DocumentHeader,
    DocumentStatus,
    DocumentType,
    ControlClass,
    WorkflowCommentStatus,
)
from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _create_assign_start,
    _login,
    _mutation_headers,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class _HeaderSaveProbe(DocumentsWorkflowActionsMixin):
    def __init__(self) -> None:
        self.captured: dict[str, object] = {}
        self._wf = MagicMock()
        self._wf.update_document_header.side_effect = self._capture
        self._um = MagicMock()
        self._um.get_current_user.return_value = SimpleNamespace(user_id="qmb", role="QMB", is_qmb=True)
        self._current_state = SimpleNamespace(document_id="DOC-HDR-CAS", version=1, status=DocumentStatus.PLANNED)
        self._current_header = None
        self._doc_type = MagicMock()
        self._doc_type.currentData.return_value = DocumentType.OTHER
        self._control_class = MagicMock()
        self._control_class.currentData.return_value = ControlClass.CONTROLLED
        self._profile = MagicMock()
        self._profile.text.return_value = "http_flow_profile"
        self._department = MagicMock()
        self._department.text.return_value = "QA"
        self._site = MagicMock()
        self._site.text.return_value = "Site-1"
        self._regulatory_scope = MagicMock()
        self._regulatory_scope.text.return_value = "MDR"
        self._errors: list[Exception] = []

    def _capture(self, document_id: str, **kwargs):
        self.captured = {"document_id": document_id, **kwargs}
        return SimpleNamespace(document_id=document_id, updated_at=datetime.now(timezone.utc))

    def _state_from_selection(self):
        return self._current_state

    def _current_user_role(self):
        from modules.documents.api import SystemRole

        return self._um.get_current_user(), SystemRole.QMB

    def _append(self, *args, **kwargs) -> None:
        return None

    def _refresh_details(self) -> None:
        return None

    def _show_error(self, exc: Exception, *, critical: bool = False) -> None:
        self._errors.append(exc)


class _CommentStatusProbe(DocumentsWorkflowSelectionMixin):
    def __init__(self) -> None:
        self.captured: dict[str, object] = {}
        self._comments_api = MagicMock()
        self._comments_api.set_workflow_comment_status.side_effect = self._capture
        self._um = MagicMock()
        self._um.get_current_user.return_value = SimpleNamespace(user_id="reviewer", role="User", is_qmb=False)
        self._current_state = SimpleNamespace(
            document_id="DOC-CMT-CAS",
            version=1,
            status=DocumentStatus.IN_REVIEW,
            available_actions=frozenset({"comments"}),
        )
        self._presenter = MagicMock()
        self._presenter.visible_actions_for_context.return_value = {"comments"}
        self._tab_comments = MagicMock()
        self._tab_comments.currentRow.return_value = 0
        item = MagicMock()
        item.data.side_effect = lambda role: "cmt-1" if role == 0x0100 else "ACTIVE"
        self._tab_comments.item.return_value = item
        self._errors: list[Exception] = []

    def _capture(self, comment_id: str, **kwargs):
        self.captured = {"comment_id": comment_id, **kwargs}
        return SimpleNamespace(comment_id=comment_id, updated_at=datetime.now(timezone.utc))

    def _current_user_role(self):
        from modules.documents.api import SystemRole

        return self._um.get_current_user(), SystemRole.USER

    def _can_current_user_create_documents(self) -> bool:
        return False

    def _state_from_selection(self):
        return self._current_state

    def _refresh_workflow_comments(self, state) -> None:
        return None

    def _show_error(self, exc: Exception, *, critical: bool = False) -> None:
        self._errors.append(exc)


def test_pyqt_header_save_passes_loaded_header_etag_not_doc_type() -> None:
    probe = _HeaderSaveProbe()
    token = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
    probe._current_header = DocumentHeader(
        document_id="DOC-HDR-CAS",
        doc_type=DocumentType.OTHER,
        control_class=ControlClass.CONTROLLED,
        workflow_profile_id="http_flow_profile",
        updated_at=token,
    )
    probe._update_header()
    assert probe._errors == []
    assert probe.captured.get("if_match") == _iso(token)
    assert "doc_type" not in probe.captured
    assert "control_class" not in probe.captured
    assert probe.captured.get("department") == "QA"
    assert probe.captured.get("workflow_profile_id") == "http_flow_profile"


def test_pyqt_header_save_fail_closed_without_loaded_token() -> None:
    probe = _HeaderSaveProbe()
    probe._current_header = None
    probe._update_header()
    assert probe._wf.update_document_header.call_count == 0
    assert probe._errors


def test_http_port_rejects_silent_doc_type_kwargs(monkeypatch) -> None:
    monkeypatch.setattr(
        "interfaces.clients.documents_http_ports.DocumentsHttpClient.for_runtime",
        lambda: MagicMock(),
    )
    api = HttpDocumentsWorkflowApi()
    with pytest.raises(TypeError, match="doc_type|control_class|unsupported"):
        api.update_document_header("DOC-1", doc_type=DocumentType.OTHER, department="QA", if_match="t")


def test_pyqt_comment_status_passes_row_token() -> None:
    probe = _CommentStatusProbe()
    token_item = MagicMock()
    token_item.data.side_effect = lambda role: {
        0x0100: "cmt-1",
        0x0101: "ACTIVE",
        0x0102: "2026-08-07T12:00:00+00:00",
    }.get(role)
    probe._tab_comments.item.return_value = token_item
    probe._resolve_selected_comment()
    assert probe._errors == []
    assert probe.captured.get("expected_updated_at") == "2026-08-07T12:00:00+00:00"


def test_pyqt_comment_status_fail_closed_without_token() -> None:
    probe = _CommentStatusProbe()
    item = MagicMock()
    item.data.side_effect = lambda role: "cmt-1" if role == 0x0100 else ("ACTIVE" if role == 0x0101 else None)
    probe._tab_comments.item.return_value = item
    probe._resolve_selected_comment()
    assert probe._comments_api.set_workflow_comment_status.call_count == 0
    assert probe._errors


def test_header_update_without_if_match_is_428(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    created = client.post(
        "/api/v1/documents/versions/create",
        headers=_auth(qmb),
        json={"document_id": "DOC-HDR-428", "version": 1, "workflow_profile_id": "http_flow_profile"},
    )
    assert created.status_code == 200, created.text
    denied = client.put(
        "/api/v1/documents/headers/DOC-HDR-428",
        headers=_auth(qmb),
        json={"department": "QA"},
    )
    assert denied.status_code == 428, denied.text
    detail = denied.json()["detail"]
    assert detail["error"] == "if_match_required"
    assert detail.get("message")


def test_header_stale_if_match_is_409_without_mutation(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    created = client.post(
        "/api/v1/documents/versions/create",
        headers=_auth(qmb),
        json={"document_id": "DOC-HDR-409", "version": 1, "workflow_profile_id": "http_flow_profile"},
    )
    assert created.status_code == 200, created.text
    before = client.get("/api/v1/documents/headers/DOC-HDR-409", headers=_auth(qmb))
    assert before.status_code == 200
    etag = before.headers["etag"]
    first = client.put(
        "/api/v1/documents/headers/DOC-HDR-409",
        headers={**_auth(qmb), "If-Match": etag},
        json={"department": "QA-1"},
    )
    assert first.status_code == 200, first.text
    stale = client.put(
        "/api/v1/documents/headers/DOC-HDR-409",
        headers={**_auth(qmb), "If-Match": etag},
        json={"department": "QA-2"},
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["error"] == "header_conflict"
    assert detail.get("message")
    current = client.get("/api/v1/documents/headers/DOC-HDR-409", headers=_auth(qmb))
    assert current.json()["department"] == "QA-1"


def test_comment_status_without_if_match_is_428(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CMT-428")
    edited = client.post(
        "/api/v1/documents/versions/DOC-CMT-428/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    created = client.post(
        "/api/v1/documents/versions/DOC-CMT-428/1/comments",
        headers=_mutation_headers(tokens["reviewer"], edited),
        json={"context": "PDF_REVIEW", "page_number": 1, "comment_text": "note"},
    )
    assert created.status_code == 200, created.text
    comment_id = created.json()["comment_id"]
    denied = client.post(
        f"/api/v1/documents/comments/{comment_id}/status",
        headers=_auth(tokens["reviewer"]),
        json={"new_status": "RESOLVED", "note": "done"},
    )
    assert denied.status_code == 428, denied.text
    detail = denied.json()["detail"]
    assert detail["error"] == "if_match_required"
    assert detail.get("message")


def test_comment_list_exposes_updated_at_and_stale_status_is_409(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CMT-409")
    edited = client.post(
        "/api/v1/documents/versions/DOC-CMT-409/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    created = client.post(
        "/api/v1/documents/versions/DOC-CMT-409/1/comments",
        headers=_mutation_headers(tokens["reviewer"], edited),
        json={"context": "PDF_REVIEW", "page_number": 1, "comment_text": "note"},
    )
    assert created.status_code == 200, created.text
    listed = client.get(
        "/api/v1/documents/versions/DOC-CMT-409/1/comments?context=PDF_REVIEW",
        headers=_auth(tokens["reviewer"]),
    )
    assert listed.status_code == 200, listed.text
    assert listed.json(), "expected at least one comment"
    row = listed.json()[0]
    assert "updated_at" in row and row["updated_at"]
    token = row["updated_at"]
    comment_id = row["comment_id"]
    first = client.post(
        f"/api/v1/documents/comments/{comment_id}/status",
        headers={**_auth(tokens["reviewer"]), "If-Match": token},
        json={"new_status": "RESOLVED", "note": "done"},
    )
    assert first.status_code == 200, first.text
    stale = client.post(
        f"/api/v1/documents/comments/{comment_id}/status",
        headers={**_auth(tokens["reviewer"]), "If-Match": token},
        json={"new_status": "ACTIVE", "note": "replay"},
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["error"] == "comment_conflict"
    assert detail.get("message")
    listed_after = client.get(
        "/api/v1/documents/versions/DOC-CMT-409/1/comments?context=PDF_REVIEW",
        headers=_auth(tokens["reviewer"]),
    )
    assert listed_after.json()[0]["status"] == "RESOLVED"


def test_http_client_set_comment_status_sends_if_match() -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="t")
    client._transport.request = MagicMock(  # type: ignore[method-assign]
        return_value={
            "comment_id": "c1",
            "ref_no": "C-1",
            "document_id": "DOC-1",
            "version": 1,
            "context": "PDF_REVIEW",
            "status": "RESOLVED",
            "page_number": 1,
            "preview_text": "x",
            "updated_at": "2026-08-07T12:01:00+00:00",
            "etag": "2026-08-07T12:01:00+00:00",
        }
    )
    client.set_workflow_comment_status(
        "c1",
        new_status="RESOLVED",
        note="done",
        if_match="2026-08-07T12:00:00+00:00",
    )
    assert client._transport.request.call_args.kwargs["headers"] == {
        "If-Match": "2026-08-07T12:00:00+00:00"
    }


def test_http_client_set_comment_status_missing_token_does_not_request() -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="t")
    client._transport.request = MagicMock()  # type: ignore[method-assign]
    with pytest.raises((TypeError, ValueError)):
        client.set_workflow_comment_status("c1", new_status="RESOLVED")
    assert client._transport.request.call_count == 0


def test_http_comments_port_forwards_expected_updated_at(monkeypatch) -> None:
    mock_client = MagicMock()
    mock_client.set_workflow_comment_status.return_value = {
        "comment_id": "c1",
        "ref_no": "C-1",
        "document_id": "DOC-1",
        "version": 1,
        "context": "PDF_REVIEW",
        "status": "RESOLVED",
        "page_number": 1,
        "preview_text": "x",
        "updated_at": "2026-08-07T12:01:00+00:00",
        "etag": "2026-08-07T12:01:00+00:00",
        "source_kind": "PDF_APP",
    }
    monkeypatch.setattr(
        "interfaces.clients.documents_http_ports.DocumentsHttpClient.for_runtime",
        lambda: mock_client,
    )
    api = HttpDocumentsCommentsApi()
    api.set_workflow_comment_status(
        "c1",
        new_status=WorkflowCommentStatus.RESOLVED,
        expected_updated_at="2026-08-07T12:00:00+00:00",
        note="done",
    )
    mock_client.set_workflow_comment_status.assert_called_once_with(
        "c1",
        new_status="RESOLVED",
        note="done",
        if_match="2026-08-07T12:00:00+00:00",
    )
