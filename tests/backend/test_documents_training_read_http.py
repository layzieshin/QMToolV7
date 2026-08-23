"""J04-M0-P3C: documents training read HTTP transport."""
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


def _approve_document(client: TestClient, tokens: dict, *, doc_id: str) -> None:
    edited = client.post(
        f"/api/v1/documents/versions/{doc_id}/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    reviewed = client.post(
        f"/api/v1/documents/versions/{doc_id}/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(
        f"/api/v1/documents/versions/{doc_id}/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"]["status"] == "APPROVED"


def test_open_confirm_and_receipt_use_session_actor(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, _users, doc_id="DOC-TRAIN-READ")
    _approve_document(client, tokens, doc_id="DOC-TRAIN-READ")

    opened = client.post(
        "/api/v1/documents/reads/open-released",
        headers=_auth(tokens["editor"]),
        json={"document_id": "DOC-TRAIN-READ", "version": 1, "source": "training"},
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["user_id"] == "editor"
    assert body["document_id"] == "DOC-TRAIN-READ"

    missing = client.get(
        "/api/v1/documents/reads/receipt/DOC-TRAIN-READ/1",
        headers=_auth(tokens["editor"]),
    )
    assert missing.status_code == 204, missing.text

    confirmed = client.post(
        "/api/v1/documents/reads/confirm",
        headers=_auth(tokens["editor"]),
        json={
            "document_id": "DOC-TRAIN-READ",
            "version": 1,
            "source": "training-http-test",
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    receipt = confirmed.json()
    assert receipt["user_id"] == "editor"
    assert receipt["source"] == "training-http-test"

    fetched = client.get(
        "/api/v1/documents/reads/receipt/DOC-TRAIN-READ/1",
        headers=_auth(tokens["editor"]),
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["receipt_id"] == receipt["receipt_id"]


def test_tracked_read_session_is_scoped_to_session_actor(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, _users, doc_id="DOC-TRAIN-TRACK")
    _approve_document(client, tokens, doc_id="DOC-TRAIN-TRACK")

    started = client.post(
        "/api/v1/documents/reads/tracked/start",
        headers=_auth(tokens["editor"]),
        json={
            "document_id": "DOC-TRAIN-TRACK",
            "version": 1,
            "source": "TRAINING_READ",
            "artifact_id": None,
            "total_pages": 1,
            "min_seconds_per_page": 10,
        },
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]
    assert started.json()["user_id"] == "editor"

    observer = _login(client, "observer", "observerpass01")
    forbidden = client.post(
        f"/api/v1/documents/reads/tracked/{session_id}/dwell",
        headers=_auth(observer),
        json={"page_number": 1, "dwell_seconds": 15},
    )
    assert forbidden.status_code == 403, forbidden.text

    progress = client.post(
        f"/api/v1/documents/reads/tracked/{session_id}/dwell",
        headers=_auth(tokens["editor"]),
        json={"page_number": 1, "dwell_seconds": 15},
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["is_complete"] is True

    finalized = client.post(
        f"/api/v1/documents/reads/tracked/{session_id}/finalize",
        headers=_auth(tokens["editor"]),
        json={"source": "TRAINING_READ"},
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["user_id"] == "editor"

    status = client.get(
        f"/api/v1/documents/reads/tracked/{session_id}/progress",
        headers=_auth(tokens["editor"]),
    )
    assert status.status_code == 200, status.text
    assert status.json()["is_complete"] is True
