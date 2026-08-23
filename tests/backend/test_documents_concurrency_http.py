from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from interfaces.clients.documents_http import (
    DocumentsBackendConflictError,
    DocumentsHttpClient,
)
from interfaces.clients.http_transport import BackendTransportError
from modules.documents.api import (
    DocumentStatus,
    DocumentVersionState,
    document_version_state_to_payload,
)
from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _login,
    _mutation_headers,
)


def _create(client: TestClient, admin: str, document_id: str):
    response = client.post(
        "/api/v1/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": document_id,
            "version": 1,
            "workflow_profile_id": "http_flow_profile",
        },
    )
    assert response.status_code == 200, response.text
    return response


@pytest.mark.parametrize(
    ("method", "path", "json_body", "content", "content_type"),
    [
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/assign-roles", {"editors": [], "reviewers": [], "approvers": []}, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/start", {"profile_id": "http_flow_profile"}, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/editing-complete", None, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/review/accept", None, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/review/reject", {"template_text": "reject"}, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/approval/accept", None, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/approval/reject", {"template_text": "reject"}, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/abort", None, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/import-pdf", None, b"%PDF-1.4\n%%EOF\n", "application/pdf"),
        (
            "POST",
            "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/workflow/ensure-source-pdf",
            None,
            None,
            None,
        ),
        (
            "POST",
            "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/import-docx",
            None,
            b"PK\x03\x04docx-stub",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/lifecycle/archive", None, None, None),
        (
            "POST",
            "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/lifecycle/extend-annual",
            {
                "duration_days": 365,
                "reason": "annual",
                "review_outcome": "UNCHANGED",
                "sign_intent": {
                    "placement": {"page": 1, "x": 0, "y": 0},
                    "layout": {"width": 100, "height": 40},
                },
            },
            None,
            None,
        ),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/lifecycle/new-version-after-archive", {"next_version": 2}, None, None),
        ("PATCH", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/metadata", {"title": "x"}, None, None),
        ("PUT", "/api/v1/documents/headers/DOC-CONFLICT-REQUIRED", {"department": "QA"}, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/change-requests", {"change_id": "CR-1", "reason": "r", "impact_refs": []}, None, None),
        ("POST", "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/comments/sync-docx", None, None, None),
        (
            "POST",
            "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1/comments",
            {"context": "PDF_REVIEW", "page_number": 1, "comment_text": "note"},
            None,
            None,
        ),
        ("POST", "/api/v1/documents/comments/missing-comment/status", {"new_status": "OPEN"}, None, None),
    ],
)
def test_every_active_version_mutation_requires_if_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    json_body: dict | None,
    content: bytes | None,
    content_type: str | None,
) -> None:
    monkeypatch.setattr(
        "src.backend.documents_routes.docx_conversion_available",
        lambda: True,
    )
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    _create(client, admin, "DOC-CONFLICT-REQUIRED")
    headers = _auth(admin)
    if content_type is not None:
        headers["Content-Type"] = content_type
    denied = client.request(
        method,
        path,
        headers=headers,
        json=json_body,
        content=content,
    )
    assert denied.status_code == 428, denied.text
    assert denied.json()["detail"]["error"] == "if_match_required"
    current = client.get(
        "/api/v1/documents/versions/DOC-CONFLICT-REQUIRED/1",
        headers=_auth(admin),
    )
    assert current.json()["state"]["assignments"]["editors"] == []


_TEMPLATE_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.template"
_TEMPLATE_DOCX_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MINIMAL_DOTX = b"PK\x03\x04minimal-dotx-stub"
_MINIMAL_DOCX = b"PK\x03\x04minimal-docx-stub"


def test_create_from_template_without_if_match_succeeds_when_target_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.backend.documents_routes.docx_conversion_available",
        lambda: True,
    )
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/api/v1/documents/versions/DOC-TEMPLATE-NEW/1/create-from-template",
        headers={**_auth(admin), "Content-Type": _TEMPLATE_CT},
        content=_MINIMAL_DOTX,
    )
    assert created.status_code == 200, created.text
    assert created.json()["state"]["document_id"] == "DOC-TEMPLATE-NEW"
    assert "available_actions" in created.json()


def test_create_from_docx_template_succeeds_and_records_docx_source_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.backend.documents_routes.docx_conversion_available",
        lambda: True,
    )
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/api/v1/documents/versions/DOC-TEMPLATE-DOCX/1/create-from-template",
        headers={**_auth(admin), "Content-Type": _TEMPLATE_DOCX_CT},
        content=_MINIMAL_DOCX,
    )
    assert created.status_code == 200, created.text
    artifacts = client.get(
        "/api/v1/documents/versions/DOC-TEMPLATE-DOCX/1/artifacts",
        headers=_auth(admin),
    )
    assert artifacts.status_code == 200, artifacts.text
    assert [row["source_type"] for row in artifacts.json()] == ["TEMPLATE_DOCX"]


def test_create_from_template_without_if_match_returns_428_when_target_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.backend.documents_routes.docx_conversion_available",
        lambda: True,
    )
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    _create(client, admin, "DOC-TEMPLATE-EXISTS")
    denied = client.post(
        "/api/v1/documents/versions/DOC-TEMPLATE-EXISTS/1/create-from-template",
        headers={**_auth(admin), "Content-Type": _TEMPLATE_CT},
        content=_MINIMAL_DOTX,
    )
    assert denied.status_code == 428, denied.text
    assert denied.json()["detail"]["error"] == "if_match_required"


def test_stale_if_match_returns_current_etag_and_state_without_mutation(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = _create(client, admin, "DOC-CONFLICT-STALE")
    stale_headers = _mutation_headers(admin, created)

    first = client.post(
        "/api/v1/documents/versions/DOC-CONFLICT-STALE/1/workflow/assign-roles",
        headers=stale_headers,
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert first.status_code == 200, first.text
    stale = client.post(
        "/api/v1/documents/versions/DOC-CONFLICT-STALE/1/workflow/assign-roles",
        headers=stale_headers,
        json={"editors": ["observer"], "reviewers": [], "approvers": []},
    )
    assert stale.status_code == 409, stale.text
    detail = stale.json()["detail"]
    assert detail["error"] == "document_conflict"
    assert detail["current_etag"] == first.json()["etag"]
    assert stale.headers["etag"] == detail["current_etag"]
    assert detail["current_state"]["assignments"]["editors"] == ["editor"]
    assert "state" not in detail

    current = client.get("/api/v1/documents/versions/DOC-CONFLICT-STALE/1", headers=_auth(admin))
    assert current.json()["state"]["assignments"]["editors"] == ["editor"]


def test_two_writers_with_same_if_match_have_one_winner(tmp_path: Path) -> None:
    """Serial two-client proof: same ETag yields exactly one success and one 409.

    Avoids flaky SQLite thread races under ThreadPoolExecutor.
    """
    container, _users = _build_documents_backend_container(tmp_path)
    app = create_app(container)
    client_a = TestClient(app)
    client_b = TestClient(app)
    admin = _login(client_a, "admin", "adminpass01")
    created = _create(client_a, admin, "DOC-CONFLICT-RACE")
    headers = _mutation_headers(admin, created)

    first = client_a.post(
        "/api/v1/documents/versions/DOC-CONFLICT-RACE/1/workflow/assign-roles",
        headers=headers,
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    second = client_b.post(
        "/api/v1/documents/versions/DOC-CONFLICT-RACE/1/workflow/assign-roles",
        headers=headers,
        json={"editors": ["observer"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["current_etag"] == first.json()["etag"]
    assert (
        second.json()["detail"]["current_state"]["assignments"]
        == first.json()["state"]["assignments"]
    )
    assert "state" not in second.json()["detail"]


def test_parallel_duplicate_create_has_one_200_and_one_409(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    app = create_app(container)
    client = TestClient(app)
    admin = _login(client, "admin", "adminpass01")
    payload = {
        "document_id": "DOC-DUP-RACE-HTTP",
        "version": 1,
        "title": "Race",
        "workflow_profile_id": "http_flow_profile",
    }

    def _create():
        worker = TestClient(app)
        return worker.post(
            "/api/v1/documents/versions/create",
            headers=_auth(admin),
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_create)
        second = pool.submit(_create)
        responses = [first.result(), second.result()]

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409], [response.text for response in responses]
    winner = next(response for response in responses if response.status_code == 200)
    conflict = next(response for response in responses if response.status_code == 409)
    detail = conflict.json()["detail"]
    assert detail["error"] == "document_conflict"
    assert detail["current_etag"] == winner.json()["etag"]
    assert detail["current_state"]["status"] == winner.json()["state"]["status"]
    current = client.get("/api/v1/documents/versions/DOC-DUP-RACE-HTTP/1", headers=_auth(admin))
    assert current.status_code == 200, current.text
    assert current.json()["etag"] == winner.json()["etag"]
    assert current.json()["state"]["status"] == "PLANNED"


def test_parallel_import_pdf_has_one_200_and_one_409(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    app = create_app(container)
    client = TestClient(app)
    admin = _login(client, "admin", "adminpass01")
    created = _create(client, admin, "DOC-IMP-RACE")
    headers = {
        **_mutation_headers(admin, created),
        "Content-Type": "application/pdf",
    }

    def _import():
        worker = TestClient(app)
        return worker.post(
            "/api/v1/documents/versions/DOC-IMP-RACE/1/import-pdf",
            headers=headers,
            content=b"%PDF-1.4\n%%EOF\n",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_import)
        second = pool.submit(_import)
        responses = [first.result(), second.result()]

    statuses = sorted(response.status_code for response in responses)
    assert statuses == [200, 409], [response.text for response in responses]
    winner = next(response for response in responses if response.status_code == 200)
    conflict = next(response for response in responses if response.status_code == 409)
    detail = conflict.json()["detail"]
    assert detail["error"] == "document_conflict"
    assert detail["current_etag"] == winner.json()["etag"]
    current = client.get("/api/v1/documents/versions/DOC-IMP-RACE/1", headers=_auth(admin))
    assert current.status_code == 200, current.text
    assert current.json()["etag"] == winner.json()["etag"]


def test_documents_http_client_sends_if_match_and_maps_conflict() -> None:
    client = DocumentsHttpClient(base_url="http://127.0.0.1:8000", token="token")
    state = DocumentVersionState(
        document_id="DOC-CLIENT-CONFLICT",
        version=1,
        status=DocumentStatus.IN_PROGRESS,
        last_event_id="evt-old",
    )
    payload = document_version_state_to_payload(state)
    client._transport.request = MagicMock(  # type: ignore[method-assign]
        return_value={"state": payload, "available_actions": [], "etag": "evt-old"}
    )
    client.abort_workflow(state)
    assert client._transport.request.call_args.kwargs["headers"] == {"If-Match": "evt-old"}

    current = DocumentVersionState(
        document_id=state.document_id,
        version=1,
        status=DocumentStatus.IN_REVIEW,
        last_event_id="evt-current",
    )
    body = json.dumps(
        {
            "detail": {
                "error": "document_conflict",
                "current_etag": "evt-current",
                "current_state": document_version_state_to_payload(current),
            }
        }
    )
    client._transport.request = MagicMock(  # type: ignore[method-assign]
        side_effect=BackendTransportError(
            "conflict",
            status_code=409,
            body=body,
        )
    )
    with pytest.raises(DocumentsBackendConflictError) as captured:
        client.abort_workflow(state)
    assert captured.value.current_etag == "evt-current"
    assert captured.value.current_state.status == DocumentStatus.IN_REVIEW
