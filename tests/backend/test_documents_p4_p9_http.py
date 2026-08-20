"""J04-M0 P4–P9: comments, header/metadata, lifecycle, CR, profile admin HTTP."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _create_assign_start,
    _login,
    _mutation_headers,
)


def _approve_document(client: TestClient, tokens: dict, doc_id: str) -> dict:
    edited = client.post(
        f"/documents/versions/{doc_id}/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    reviewed = client.post(
        f"/documents/versions/{doc_id}/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(
        f"/documents/versions/{doc_id}/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def test_capabilities_exposes_docx_import_flag(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    response = client.get("/documents/capabilities", headers=_auth(admin))
    assert response.status_code == 200, response.text
    body = response.json()
    assert "can_import_docx" in body
    assert isinstance(body["can_import_docx"], bool)


def test_metadata_patch_updates_title(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-META-P5")
    read = client.get("/documents/versions/DOC-META-P5/1", headers=_auth(tokens["admin"]))
    assert read.status_code == 200
    patched = client.patch(
        "/documents/versions/DOC-META-P5/1/metadata",
        headers=_mutation_headers(tokens["admin"], read),
        json={"title": "Updated HTTP Title"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["state"]["title"] == "Updated HTTP Title"


def test_header_update_department(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(qmb),
        json={"document_id": "DOC-HDR-P5", "version": 1, "workflow_profile_id": "http_flow_profile"},
    )
    assert created.status_code == 200
    header_before = client.get("/documents/headers/DOC-HDR-P5", headers=_auth(qmb))
    assert header_before.status_code == 200
    updated = client.put(
        "/documents/headers/DOC-HDR-P5",
        headers={**_auth(qmb), "If-Match": header_before.headers["etag"]},
        json={"department": "QA-Lab"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["department"] == "QA-Lab"


def test_change_request_list_and_create(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CR-P8")
    read = client.get("/documents/versions/DOC-CR-P8/1", headers=_auth(tokens["admin"]))
    empty = client.get("/documents/versions/DOC-CR-P8/1/change-requests", headers=_auth(tokens["admin"]))
    assert empty.status_code == 200
    assert empty.json() == []
    created = client.post(
        "/documents/versions/DOC-CR-P8/1/change-requests",
        headers=_mutation_headers(tokens["admin"], read),
        json={"change_id": "CR-1", "reason": "scope", "impact_refs": ["TR-1"]},
    )
    assert created.status_code == 200, created.text
    listed = client.get("/documents/versions/DOC-CR-P8/1/change-requests", headers=_auth(tokens["admin"]))
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["change_id"] == "CR-1"


def test_archive_approved_version(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-ARCH-P7")
    approved = _approve_document(client, tokens, "DOC-ARCH-P7")
    qmb = _login(client, "qmb", "qmbpass001")
    archived = client.post(
        "/documents/versions/DOC-ARCH-P7/1/lifecycle/archive",
        headers=_mutation_headers(qmb, approved["etag"]),
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["state"]["status"] == "ARCHIVED"


def _valid_profile_transitions() -> list[dict[str, object]]:
    return [
        {
            "transition_no": 1,
            "from_status": "DRAFT",
            "to_status": "IN_REVIEW",
            "required_role": "EDITOR",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": False,
            "four_eyes_required": False,
        },
        {
            "transition_no": 2,
            "from_status": "IN_REVIEW",
            "to_status": "IN_APPROVAL",
            "required_role": "REVIEWER",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": False,
            "four_eyes_required": False,
        },
        {
            "transition_no": 3,
            "from_status": "IN_APPROVAL",
            "to_status": "APPROVED",
            "required_role": "APPROVER",
            "decision_policy": "ONE_OF_POOL",
            "signature_required": False,
            "four_eyes_required": False,
        },
    ]


def test_profile_create_over_http_by_qmb(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    response = client.post(
        "/documents/workflow-profiles/definitions",
        headers=_auth(qmb),
        json={
            "payload": {
                "profile_code": "http_admin_profile_p9",
                "label": "HTTP Admin Profile P9",
                "control_class": "CONTROLLED",
                "requires_editors": True,
                "requires_reviewers": True,
                "requires_approvers": True,
                "allows_content_changes": True,
                "release_evidence_mode": "WORKFLOW",
                "transitions": _valid_profile_transitions(),
            },
            "change_reason": "p9-http-test",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["profile_code"] == "http_admin_profile_p9"
    versions = client.get(
        "/documents/workflow-profiles/definitions/http_admin_profile_p9/versions",
        headers=_auth(qmb),
    )
    assert versions.status_code == 200
    assert len(versions.json()) >= 1


def test_pdf_comment_create_then_immediate_list_over_http(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CMT-IMMED")
    edited = client.post(
        "/documents/versions/DOC-CMT-IMMED/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["state"]["status"] == "IN_REVIEW"
    reviewer = tokens["reviewer"]
    created = client.post(
        "/documents/versions/DOC-CMT-IMMED/1/comments",
        headers=_mutation_headers(reviewer, edited),
        json={"context": "PDF_REVIEW", "page_number": 1, "comment_text": "immediate list test"},
    )
    assert created.status_code == 200, created.text
    comment_id = created.json().get("comment_id")
    assert comment_id, "comment_id missing from create response"
    listed = client.get(
        "/documents/versions/DOC-CMT-IMMED/1/comments?context=PDF_REVIEW",
        headers=_auth(reviewer),
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert isinstance(rows, list) and rows, "comment list is empty after create"
    ids = [row.get("comment_id") for row in rows if isinstance(row, dict)]
    assert comment_id in ids, f"created comment_id {comment_id!r} not found in list {ids}"
    matching = next(row for row in rows if isinstance(row, dict) and row.get("comment_id") == comment_id)
    assert matching.get("context") == "PDF_REVIEW"


def test_comments_list_requires_auth_context(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CMT-P4")
    response = client.get(
        "/documents/versions/DOC-CMT-P4/1/comments?context=PDF_REVIEW",
        headers=_auth(tokens["reviewer"]),
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_comments_are_hidden_from_unassigned_observer(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CMT-AUTH")
    observer = _login(client, "observer", "observerpass01")
    response = client.get(
        "/documents/versions/DOC-CMT-AUTH/1/comments?context=PDF_REVIEW",
        headers=_auth(observer),
    )
    assert response.status_code == 404, response.text
    assert "current_state" not in response.text


def _comments_docx_bytes(comments: list[tuple[str, str, str | None, str]]) -> bytes:
    from io import BytesIO
    from zipfile import ZipFile

    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    nodes = []
    for cid, author, date, text in comments:
        attrs = f'w:id="{cid}" w:author="{author}"'
        if date:
            attrs += f' w:date="{date}"'
        nodes.append(f'<w:comment {attrs}><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:comment>')
    xml = f'<?xml version="1.0" encoding="UTF-8"?><w:comments xmlns:w="{ns}">{"".join(nodes)}</w:comments>'
    buf = BytesIO()
    with ZipFile(buf, "w") as zf:
        zf.writestr("word/comments.xml", xml)
    return buf.getvalue()


def test_http_docx_comment_sync_in_review_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.backend.documents_routes.docx_conversion_available", lambda: True)
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-CMT-SYNC-HTTP")
    imported = client.post(
        "/documents/versions/DOC-CMT-SYNC-HTTP/1/import-docx",
        headers={
            **_mutation_headers(tokens["admin"], tokens["state_response"]),
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        content=_comments_docx_bytes([("1", "Ann", "2026-01-01T00:00:00Z", "hello")]),
    )
    assert imported.status_code == 200, imported.text
    edited = client.post(
        "/documents/versions/DOC-CMT-SYNC-HTTP/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], imported),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["state"]["status"] == "IN_REVIEW"
    first = client.post(
        "/documents/versions/DOC-CMT-SYNC-HTTP/1/comments/sync-docx",
        headers=_mutation_headers(tokens["editor"], edited),
    )
    assert first.status_code == 200, first.text
    rows = first.json()
    assert len(rows) == 1
    comment_id = rows[0]["comment_id"]
    second = client.post(
        "/documents/versions/DOC-CMT-SYNC-HTTP/1/comments/sync-docx",
        headers=_mutation_headers(tokens["editor"], edited),
    )
    assert second.status_code == 200, second.text
    assert len(second.json()) == 1
    assert second.json()[0]["comment_id"] == comment_id
    observer = _login(client, "observer", "observerpass01")
    hidden = client.post(
        "/documents/versions/DOC-CMT-SYNC-HTTP/1/comments/sync-docx",
        headers={**_auth(observer), "If-Match": edited.json()["etag"]},
    )
    assert hidden.status_code == 404, hidden.text
    assert "current_state" not in hidden.text
