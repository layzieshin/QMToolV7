"""WCON00-PIS-1: cross-checkpoint HTTP contract walk (no Vue)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.api import create_app
from tests.backend.test_documents_artifacts_http import _artifact_id_for_editor
from tests.backend.test_documents_http_api import (
    _auth,
    _create_assign_start,
    _mutation_headers,
)
from tests.backend.test_session_http import _build_licensed_test_container
from tests.backend.test_signature_http_api import _build_signature_backend, _login


def test_wcon00_pis1_connection_and_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unauth = TestClient(create_app())
    connection = unauth.get("/api/v1/session/connection")
    assert connection.status_code == 200
    assert connection.json()["contract_version"] == "1"
    assert unauth.get("/api/v1/session/bootstrap").status_code == 401

    client = TestClient(create_app(_build_licensed_test_container(tmp_path, monkeypatch)))
    license_service = client.app.state.container.get_port("license_service")
    original_allowed = license_service.is_module_allowed

    def _is_module_allowed(module_id: str) -> bool:
        if module_id == "training":
            return False
        return original_allowed(module_id)

    monkeypatch.setattr(license_service, "is_module_allowed", _is_module_allowed)
    login = client.post("/api/v1/auth/token", json={"username": "admin", "password": "admin"})
    assert login.status_code == 200
    bootstrap = client.get(
        "/api/v1/session/bootstrap",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    assert bootstrap.status_code == 200
    modules = {item["id"]: item for item in bootstrap.json()["modules"]}
    assert modules["documents"]["licensed"] is True
    assert modules["documents"]["authorized"] is True
    assert modules["usermanagement"]["licensed"] is True
    assert modules["usermanagement"]["authorized"] is True
    assert modules["training"]["licensed"] is False
    assert modules["training"]["authorized"] is False


def test_wcon00_pis1_documents_admin_signature_and_users(tmp_path: Path) -> None:
    container, users = _build_signature_backend(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-PIS-1")
    admin = tokens["admin"]

    queried = client.get("/api/v1/documents/query?limit=10", headers=_auth(admin))
    assert queried.status_code == 200, queried.text
    items = queried.json()["items"]
    assert items
    row = next(item for item in items if item["document_id"] == "DOC-PIS-1")
    assert isinstance(row["available_actions"], list)
    assert isinstance(row["allowed_actions"], list)
    assert row["available_actions"] == sorted(
        item["code"] for item in row["allowed_actions"] if item["enabled"]
    )

    history = client.get("/api/v1/documents/versions/DOC-PIS-1/1/history", headers=_auth(admin))
    assert history.status_code == 200, history.text
    events = history.json()
    assert isinstance(events, list)
    assert events
    event = events[0]
    assert set(event) <= {"occurred_at", "event_type", "actor_user_id", "summary"}
    assert "storage_key" not in event
    assert "storage_key" not in str(events).lower()

    invalid_metadata = client.patch(
        "/api/v1/documents/versions/DOC-PIS-1/1/metadata",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
        json={"valid_until": "not-a-date"},
    )
    assert invalid_metadata.status_code == 400, invalid_metadata.text
    assert invalid_metadata.json()["detail"]["field_errors"][0]["field"] == "valid_until"

    artifact_id = _artifact_id_for_editor(client, tokens, "DOC-PIS-1")
    preview = client.get(
        f"/api/v1/documents/artifacts/{artifact_id}/preview",
        headers=_auth(tokens["editor"]),
    )
    assert preview.status_code == 200
    assert "inline" in preview.headers.get("Content-Disposition", "")
    assert "no-store" in preview.headers.get("Cache-Control", "")

    download = client.get(
        f"/api/v1/documents/artifacts/{artifact_id}/download",
        headers=_auth(tokens["editor"]),
    )
    assert download.status_code == 200
    assert "attachment" in download.headers.get("Content-Disposition", "")
    assert "no-store" in download.headers.get("Cache-Control", "")
    assert preview.content == download.content

    observer = _login(client, "observer", "observerpass01")
    for suffix in ("preview", "download"):
        hidden = client.get(
            f"/api/v1/documents/artifacts/{artifact_id}/{suffix}",
            headers=_auth(observer),
        )
        assert hidden.status_code == 404, hidden.text

    invalid = client.get("/api/v1/documents/query?sort=bad", headers=_auth(admin))
    assert invalid.status_code == 400
    assert "field_errors" in invalid.json()["detail"]

    edited = client.post(
        "/api/v1/documents/versions/DOC-PIS-1/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    reviewed = client.post(
        "/api/v1/documents/versions/DOC-PIS-1/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(
        "/api/v1/documents/versions/DOC-PIS-1/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text
    listed = client.get(
        "/api/v1/documents/versions/DOC-PIS-1/1/artifacts",
        headers=_auth(tokens["editor"]),
    )
    assert listed.status_code == 200, listed.text
    released_ids = [row["artifact_id"] for row in listed.json()]
    assert released_ids
    released_download = None
    for released_id in released_ids:
        candidate = client.get(
            f"/api/v1/documents/artifacts/{released_id}/download",
            headers=_auth(tokens["editor"]),
        )
        if candidate.status_code == 200:
            released_download = candidate
            break
    assert released_download is not None
    assert "attachment" in released_download.headers.get("Content-Disposition", "")
    assert released_download.content.startswith(b"%PDF")

    created = client.post(
        "/api/v1/signature/templates/user",
        headers=_auth(tokens["editor"]),
        json={
            "name": "pis-preset",
            "placement": {"page_index": 0, "x": 72.0, "y": 72.0, "target_width": 120.0},
            "layout": {
                "show_signature": False,
                "show_name": True,
                "show_date": True,
                "show_time": True,
            },
            "document_type": "SOP",
            "role_context": "approver",
        },
    )
    assert created.status_code == 200, created.text
    suggested = client.get(
        "/api/v1/signature/templates/suggestion",
        headers=_auth(tokens["editor"]),
        params={"document_type": "SOP", "role_context": "approver"},
    )
    assert suggested.status_code == 200
    assert suggested.json()["template_id"] == created.json()["template_id"]

    deactivated = client.patch(
        "/api/v1/users/editor/access",
        headers=_auth(admin),
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    listed = client.get("/api/v1/users", headers=_auth(admin))
    assert listed.status_code == 200
    editor_row = next(item for item in listed.json() if item["username"] == "editor")
    assert editor_row["is_active"] is False
    directory = client.get("/api/v1/users/directory", headers=_auth(admin))
    assert directory.status_code == 200
    assert "editor" not in {item["username"] for item in directory.json()}
    detail = client.get("/api/v1/users/editor", headers=_auth(admin))
    assert detail.status_code == 200
    assert "must_change_password" in detail.json()
    reset = client.post(
        "/api/v1/users/editor/password-actions",
        headers=_auth(admin),
        json={"new_password": "resetpassword1"},
    )
    assert reset.status_code == 204
    after = client.get("/api/v1/users/editor", headers=_auth(admin))
    assert after.json()["must_change_password"] is True
