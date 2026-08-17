from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _create_assign_start,
    _login,
    _minimal_pdf_bytes,
    _mutation_headers,
)


def test_observer_cannot_create_or_spoof_owner(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    observer = _login(client, "observer", "observerpass01")

    denied = client.post(
        "/documents/versions/create",
        headers=_auth(observer),
        json={"document_id": "DOC-AUTH-OBS", "version": 1, "owner_user_id": "qmb"},
    )
    assert denied.status_code == 403


def test_draft_and_artifact_access_is_parent_authorized(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    observer = _login(client, "observer", "observerpass01")

    created = client.post(
        "/documents/versions/create",
        headers=_auth(qmb),
        json={"document_id": "DOC-AUTH-DRAFT", "version": 1},
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        "/documents/versions/DOC-AUTH-DRAFT/1/import-pdf",
        headers={**_mutation_headers(qmb, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    artifact_id = client.get(
        "/documents/versions/DOC-AUTH-DRAFT/1/artifacts", headers=_auth(qmb)
    ).json()[0]["artifact_id"]

    assert client.get("/documents/versions/DOC-AUTH-DRAFT/1", headers=_auth(observer)).status_code == 404
    assert client.get(
        f"/documents/versions/DOC-AUTH-DRAFT/1/artifacts", headers=_auth(observer)
    ).status_code == 404
    assert client.get(f"/documents/artifacts/{artifact_id}/content", headers=_auth(observer)).status_code == 404


def test_approved_document_and_current_pdf_are_readable_by_observer(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-APPROVED")
    edited = client.post(
        "/documents/versions/DOC-AUTH-APPROVED/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    reviewed = client.post(
        "/documents/versions/DOC-AUTH-APPROVED/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    approved = client.post(
        "/documents/versions/DOC-AUTH-APPROVED/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text
    observer = _login(client, "observer", "observerpass01")
    visible = client.get("/documents/versions/DOC-AUTH-APPROVED/1", headers=_auth(observer))
    assert visible.status_code == 200, visible.text
    artifacts = client.get(
        "/documents/versions/DOC-AUTH-APPROVED/1/artifacts", headers=_auth(observer)
    )
    assert artifacts.status_code == 200


def test_non_reviewer_cannot_accept_review(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-REV")
    edited = client.post(
        "/documents/versions/DOC-AUTH-REV/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    denied = client.post(
        "/documents/versions/DOC-AUTH-REV/1/workflow/review/accept",
        headers=_mutation_headers(tokens["editor"], edited),
    )
    assert denied.status_code == 403, denied.text


def test_non_qmb_cannot_archive_or_new_version(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-LIFE")
    edited = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    reviewed = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    approved = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text
    denied_archive = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/lifecycle/archive",
        headers=_mutation_headers(tokens["editor"], approved),
    )
    assert denied_archive.status_code == 403, denied_archive.text

    qmb = _login(client, "qmb", "qmbpass001")
    archived = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/lifecycle/archive",
        headers=_mutation_headers(qmb, approved),
    )
    assert archived.status_code == 200, archived.text

    users_api = container.get_port("usermanagement_service")
    try:
        users_api.create_user("plainadmin", "plainadmin01", role="Admin", is_qmb=False)
    except Exception:
        pass
    plain_admin = _login(client, "plainadmin", "plainadmin01")
    denied_new = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/lifecycle/new-version-after-archive",
        headers=_mutation_headers(plain_admin, archived),
        json={"next_version": 2},
    )
    assert denied_new.status_code == 403, denied_new.text

    allowed_new = client.post(
        "/documents/versions/DOC-AUTH-LIFE/1/lifecycle/new-version-after-archive",
        headers=_mutation_headers(qmb, archived),
        json={"next_version": 2},
    )
    assert allowed_new.status_code == 200, allowed_new.text
    assert allowed_new.json()["state"]["version"] == 2


def test_stale_if_match_on_new_version_returns_409_without_mutation(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-STALE-NV")
    edited = client.post(
        "/documents/versions/DOC-AUTH-STALE-NV/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    reviewed = client.post(
        "/documents/versions/DOC-AUTH-STALE-NV/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    approved = client.post(
        "/documents/versions/DOC-AUTH-STALE-NV/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    qmb = _login(client, "qmb", "qmbpass001")
    archived = client.post(
        "/documents/versions/DOC-AUTH-STALE-NV/1/lifecycle/archive",
        headers=_mutation_headers(qmb, approved),
    )
    assert archived.status_code == 200, archived.text
    stale_headers = _mutation_headers(qmb, archived)
    bumped = client.patch(
        "/documents/versions/DOC-AUTH-STALE-NV/1/metadata",
        headers=_mutation_headers(qmb, archived),
        json={"title": "archived-title-bump"},
    )
    assert bumped.status_code == 200, bumped.text
    assert bumped.json()["etag"] not in {"", "none"}
    assert bumped.json()["etag"] != stale_headers["If-Match"]
    denied = client.post(
        "/documents/versions/DOC-AUTH-STALE-NV/1/lifecycle/new-version-after-archive",
        headers=stale_headers,
        json={"next_version": 2},
    )
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"]["error"] == "document_conflict"
    missing = client.get("/documents/versions/DOC-AUTH-STALE-NV/2", headers=_auth(qmb))
    assert missing.status_code == 404


def test_new_version_consumes_source_etag_and_links_successor(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-NV-CAS")
    edited = client.post(
        "/documents/versions/DOC-AUTH-NV-CAS/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    reviewed = client.post(
        "/documents/versions/DOC-AUTH-NV-CAS/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    approved = client.post(
        "/documents/versions/DOC-AUTH-NV-CAS/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    qmb = _login(client, "qmb", "qmbpass001")
    archived = client.post(
        "/documents/versions/DOC-AUTH-NV-CAS/1/lifecycle/archive",
        headers=_mutation_headers(qmb, approved),
    )
    assert archived.status_code == 200, archived.text
    source_etag = archived.json()["etag"]
    created = client.post(
        "/documents/versions/DOC-AUTH-NV-CAS/1/lifecycle/new-version-after-archive",
        headers=_mutation_headers(qmb, archived),
        json={"next_version": 2},
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["state"]["version"] == 2
    assert payload["etag"] not in {"", "none", None}
    assert payload["etag"] == payload["state"]["last_event_id"]
    source = client.get("/documents/versions/DOC-AUTH-NV-CAS/1", headers=_auth(qmb))
    assert source.status_code == 200, source.text
    assert source.json()["state"]["superseded_by_version"] == 2
    assert source.json()["etag"] == payload["etag"]
    assert source.json()["etag"] != source_etag
    replay = client.post(
        "/documents/versions/DOC-AUTH-NV-CAS/1/lifecycle/new-version-after-archive",
        headers={**_auth(qmb), "If-Match": source_etag},
        json={"next_version": 3},
    )
    assert replay.status_code == 409, replay.text
    missing = client.get("/documents/versions/DOC-AUTH-NV-CAS/3", headers=_auth(qmb))
    assert missing.status_code == 404


def test_non_qmb_cannot_update_header(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(qmb),
        json={"document_id": "DOC-AUTH-HDR", "version": 1, "workflow_profile_id": "http_flow_profile"},
    )
    assert created.status_code == 200, created.text
    header_before = client.get("/documents/headers/DOC-AUTH-HDR", headers=_auth(qmb))
    assert header_before.status_code == 200
    editor = _login(client, "editor", "editorpass01")
    denied = client.put(
        "/documents/headers/DOC-AUTH-HDR",
        headers={**_auth(editor), "If-Match": header_before.headers["etag"]},
        json={"department": "QA"},
    )
    assert denied.status_code == 403, denied.text


def test_open_source_denied_for_assigned_non_editor(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-OPEN")
    listed = client.get(
        "/documents/versions/DOC-AUTH-OPEN/1/artifacts",
        headers=_auth(tokens["editor"]),
    )
    assert listed.status_code == 200, listed.text
    artifact_id = listed.json()[0]["artifact_id"]
    allowed = client.get(f"/documents/artifacts/{artifact_id}/content", headers=_auth(tokens["editor"]))
    assert allowed.status_code == 200, allowed.text
    denied = client.get(f"/documents/artifacts/{artifact_id}/content", headers=_auth(tokens["reviewer"]))
    assert denied.status_code == 404, denied.text


def test_assign_start_abort_http_public_boundaries(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": "DOC-AUTH-ASA",
            "version": 1,
            "title": "DOC-AUTH-ASA",
            "doc_type": "OTHER",
            "control_class": "CONTROLLED",
            "workflow_profile_id": "http_flow_profile",
        },
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    editor = _login(client, "editor", "editorpass01")
    denied_assign = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/workflow/assign-roles",
        headers=_mutation_headers(editor, imported),
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert denied_assign.status_code == 403, denied_assign.text
    assigned = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/workflow/assign-roles",
        headers=_mutation_headers(admin, imported),
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert assigned.status_code == 200, assigned.text
    denied_start = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/workflow/start",
        headers=_mutation_headers(editor, assigned),
        json={"profile_id": "http_flow_profile"},
    )
    assert denied_start.status_code == 403, denied_start.text
    started = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/workflow/start",
        headers=_mutation_headers(admin, assigned),
        json={"profile_id": "http_flow_profile"},
    )
    assert started.status_code == 200, started.text
    denied_abort = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/workflow/abort",
        headers=_mutation_headers(editor, started),
    )
    assert denied_abort.status_code == 403, denied_abort.text
    aborted = client.post(
        "/documents/versions/DOC-AUTH-ASA/1/workflow/abort",
        headers=_mutation_headers(admin, started),
    )
    assert aborted.status_code == 200, aborted.text
    assert aborted.json()["state"]["status"] == "PLANNED"


def test_review_and_approval_reject_http(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-AUTH-REJ")
    edited = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    denied_reject = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/review/reject",
        headers=_mutation_headers(tokens["editor"], edited),
        json={"template_id": "T1", "template_text": "no", "free_text": None},
    )
    assert denied_reject.status_code == 403, denied_reject.text
    rejected = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/review/reject",
        headers=_mutation_headers(tokens["reviewer"], edited),
        json={"template_id": "T1", "template_text": "rework", "free_text": None},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"]["status"] == "IN_PROGRESS"
    edited2 = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], rejected),
    )
    reviewed = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited2),
    )
    assert reviewed.status_code == 200, reviewed.text
    denied_approval_reject = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/approval/reject",
        headers=_mutation_headers(tokens["reviewer"], reviewed),
        json={"template_id": "T1", "template_text": "no", "free_text": None},
    )
    assert denied_approval_reject.status_code == 403, denied_approval_reject.text
    approval_rejected = client.post(
        "/documents/versions/DOC-AUTH-REJ/1/workflow/approval/reject",
        headers=_mutation_headers(tokens["approver"], reviewed),
        json={"template_id": "T1", "template_text": "rework approval", "free_text": None},
    )
    assert approval_rejected.status_code == 200, approval_rejected.text
    assert approval_rejected.json()["state"]["status"] == "IN_PROGRESS"