from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _create_assign_start,
    _login,
    _mutation_headers,
)


def test_home_reads_use_authenticated_actor_not_query_user_id(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-READ-HOME")

    tasks = client.get(
        "/api/v1/documents/home/tasks?user_id=observer",
        headers=_auth(tokens["editor"]),
    )
    assert tasks.status_code == 200, tasks.text
    assert any(row["document_id"] == "DOC-READ-HOME" for row in tasks.json())

    completed = client.post(
        "/api/v1/documents/versions/DOC-READ-HOME/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert completed.status_code == 200, completed.text
    reviews = client.get(
        "/api/v1/documents/home/review-actions?user_id=observer",
        headers=_auth(tokens["reviewer"]),
    )
    assert reviews.status_code == 200, reviews.text
    assert any(
        row["document_id"] == "DOC-READ-HOME" and row["action_required"] == "review"
        for row in reviews.json()
    )

    recent = client.get(
        "/api/v1/documents/home/recent?user_id=observer",
        headers=_auth(tokens["editor"]),
    )
    assert recent.status_code == 200, recent.text
    assert any(row["document_id"] == "DOC-READ-HOME" for row in recent.json())


def test_released_read_returns_current_approved_versions(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-READ-RELEASED")
    edited = client.post(
        "/api/v1/documents/versions/DOC-READ-RELEASED/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    reviewed = client.post(
        "/api/v1/documents/versions/DOC-READ-RELEASED/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    approved = client.post(
        "/api/v1/documents/versions/DOC-READ-RELEASED/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text

    released = client.get("/api/v1/documents/released", headers=_auth(tokens["editor"]))
    assert released.status_code == 200, released.text
    assert any(
        row["document_id"] == "DOC-READ-RELEASED" and row["version"] == 1
        for row in released.json()
    )


def test_global_and_version_capabilities_are_server_computed(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CAPS")
    qmb = _login(client, "qmb", "qmbpass001")

    qmb_caps = client.get("/api/v1/documents/capabilities", headers=_auth(qmb))
    assert qmb_caps.status_code == 200, qmb_caps.text
    qmb_body = qmb_caps.json()
    assert qmb_body["can_create_new_documents"] is True
    assert qmb_body["can_administer_workflow_profiles"] is True
    assert isinstance(qmb_body["can_import_docx"], bool)
    editor_caps = client.get("/api/v1/documents/capabilities", headers=_auth(tokens["editor"]))
    assert editor_caps.status_code == 200, editor_caps.text
    editor_body = editor_caps.json()
    assert editor_body["can_create_new_documents"] is False
    assert editor_body["can_administer_workflow_profiles"] is False
    assert isinstance(editor_body["can_import_docx"], bool)
    admin_caps = client.get("/api/v1/documents/capabilities", headers=_auth(tokens["admin"]))
    assert admin_caps.status_code == 200, admin_caps.text
    admin_body = admin_caps.json()
    # The fixture explicitly marks the admin as QMB, so QMB-only capabilities
    # are expected. A technical admin without is_qmb remains denied.
    assert admin_body["can_create_new_documents"] is True
    assert admin_body["can_administer_workflow_profiles"] is True
    assert isinstance(admin_body["can_import_docx"], bool)

    version = client.get(
        "/api/v1/documents/versions/DOC-CAPS/1",
        headers=_auth(tokens["editor"]),
    )
    assert version.status_code == 200, version.text
    assert set(version.json()["available_actions"]) >= {"open_source", "complete_editing"}
    assert version.json()["state"]["available_actions"] == version.json()["available_actions"]
    assert version.headers["etag"] == version.json()["etag"]


def test_signature_required_profile_exposes_complete_editing_after_p3b(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    editor = _login(client, "editor", "editorpass01")
    created = client.post(
        "/api/v1/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": "DOC-CAPS-SIGNED",
            "version": 1,
            "workflow_profile_id": "long_release",
        },
    )
    assert created.status_code == 200, created.text
    assigned = client.post(
        "/api/v1/documents/versions/DOC-CAPS-SIGNED/1/workflow/assign-roles",
        headers=_mutation_headers(admin, created),
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert assigned.status_code == 200, assigned.text
    started = client.post(
        "/api/v1/documents/versions/DOC-CAPS-SIGNED/1/workflow/start",
        headers=_mutation_headers(admin, assigned),
        json={"profile_id": "long_release"},
    )
    assert started.status_code == 200, started.text

    version = client.get(
        "/api/v1/documents/versions/DOC-CAPS-SIGNED/1",
        headers=_auth(editor),
    )
    assert version.status_code == 200, version.text
    actions = set(version.json()["available_actions"])
    assert "open_source" in actions
    assert "complete_editing" in actions
    assert "extend_validity" not in actions
