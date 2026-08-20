"""M2.1 Documents HTTP client fail-closed available_actions / current_state."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from interfaces.clients.documents_http import DocumentsBackendConflictError, DocumentsHttpClient
from interfaces.clients.http_transport import BackendTransportError
from modules.documents.api import DocumentStatus, DocumentVersionState, document_version_state_to_payload


def test_coerce_available_actions_accepts_only_string_lists() -> None:
    coerce = DocumentsHttpClient._coerce_available_actions
    assert coerce(["start", "abort"]) == ["start", "abort"]
    assert coerce([]) == []
    assert coerce(None) == []
    assert coerce("start") == []
    assert coerce(["start", 1]) == []
    assert coerce({"start": True}) == []


def test_state_from_response_fail_closed_on_invalid_actions() -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="t")
    base = {
        "document_id": "DOC-1",
        "version": 1,
        "status": "PLANNED",
        "last_event_id": "evt-1",
        "title": "",
        "description": None,
        "doc_type": "OTHER",
        "control_class": "CONTROLLED",
        "workflow_profile_id": None,
        "owner_user_id": "u1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "created_by": None,
        "assignments": {"editors": [], "reviewers": [], "approvers": []},
        "workflow_active": False,
        "custom_fields": {},
    }
    valid = client._state_from_response({"state": base, "available_actions": ["start", "unknown_x"], "etag": "evt-1"})
    assert set(valid.available_actions or []) == {"start", "unknown_x"}

    missing = client._state_from_response({"state": base, "etag": "evt-1"})
    assert list(missing.available_actions or []) == []

    bad_type = client._state_from_response({"state": base, "available_actions": "start", "etag": "evt-1"})
    assert list(bad_type.available_actions or []) == []

    mixed = client._state_from_response({"state": base, "available_actions": ["start", 2], "etag": "evt-1"})
    assert list(mixed.available_actions or []) == []


def test_conflict_maps_current_state_only() -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="t")
    state = DocumentVersionState(document_id="DOC-C", version=1, status=DocumentStatus.IN_PROGRESS, last_event_id="old")
    current = DocumentVersionState(
        document_id="DOC-C", version=1, status=DocumentStatus.IN_REVIEW, last_event_id="new"
    )
    body = json.dumps(
        {
            "detail": {
                "error": "document_conflict",
                "current_etag": "new",
                "current_state": document_version_state_to_payload(current),
                "state": {"status": "should_be_ignored"},
            }
        }
    )
    client._transport.request = MagicMock(
        side_effect=BackendTransportError("conflict", status_code=409, body=body)
    )
    with pytest.raises(DocumentsBackendConflictError) as captured:
        client.abort_workflow(state)
    assert captured.value.current_etag == "new"
    assert captured.value.current_state is not None
    assert captured.value.current_state.status == DocumentStatus.IN_REVIEW


def test_document_paths_encode_legacy_ids_and_query_values() -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="t")
    client._request = MagicMock(return_value=[])

    client.list_artifacts("DOC-2026_08.~", 1)
    assert client._request.call_args.args == (
        "GET",
        "/documents/versions/DOC-2026_08.~/1/artifacts",
    )

    legacy_state = DocumentVersionState(document_id="LEGACY ?#%", version=1)
    client.list_workflow_comments(legacy_state, context="PDF REVIEW/ARCHIVE")
    assert client._request.call_args.args == (
        "GET",
        "/documents/versions/LEGACY%20%3F%23%25/1/comments?context=PDF%20REVIEW%2FARCHIVE",
    )

    client.list_tasks(scope="mine/team")
    assert client._request.call_args.args == ("GET", "/documents/home/tasks?scope=mine%2Fteam")


def test_create_from_template_maps_docx_to_document_media_type(tmp_path: Path) -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="t")
    client._request = MagicMock(return_value={})
    client._state_from_response = MagicMock(return_value=object())
    source = tmp_path / "template.docx"
    source.write_bytes(b"PK\x03\x04docx-stub")

    client.create_from_template_for_version("DOC-TEMPLATE", 1, source, state=None)

    assert client._request.call_args.args == (
        "POST",
        "/documents/versions/DOC-TEMPLATE/1/create-from-template",
    )
    assert client._request.call_args.kwargs["content_type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
