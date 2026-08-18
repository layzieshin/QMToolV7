"""J04-M0-P3B: signed documents workflow transitions over HTTP."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.usermanagement.api import login_backend, resolve_session
from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.signature.wiring import register_signature_ports
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from src.backend.api import create_app
from tests.backend.test_documents_http_api import (
    _auth,
    _build_documents_backend_container,
    _login,
    _minimal_pdf_bytes,
    _mutation_headers,
)
from tests.backend.test_signature_http_api import _create_signature_png, _wire_signature_module

EDITOR_HTTP_PASSWORD = "editorpass01"
REVIEWER_HTTP_PASSWORD = "reviewerpass01"
APPROVER_HTTP_PASSWORD = "approverpass01"
QMB_HTTP_PASSWORD = "qmbpass001"


def _create_signed_flow_profile(container) -> None:
    workflow_api = container.get_port("documents_workflow_api")
    issued = login_backend(container, "qmb", "qmbpass001", request_id="signed-flow-profile")
    actor = resolve_session(container, issued.raw_token, request_id="signed-flow-profile")
    workflow_api.create_workflow_profile_definition(
        {
            "profile_code": "signed_http_profile",
            "label": "Signed HTTP Profile",
            "control_class": "CONTROLLED",
            "requires_editors": True,
            "requires_reviewers": True,
            "requires_approvers": True,
            "allows_content_changes": True,
            "release_evidence_mode": "WORKFLOW",
            "transitions": [
                {
                    "transition_no": 1,
                    "from_status": "DRAFT",
                    "to_status": "IN_REVIEW",
                    "required_role": "EDITOR",
                    "decision_policy": "ONE_OF_POOL",
                    "signature_required": True,
                    "four_eyes_required": False,
                },
                {
                    "transition_no": 2,
                    "from_status": "IN_REVIEW",
                    "to_status": "IN_APPROVAL",
                    "required_role": "REVIEWER",
                    "decision_policy": "ONE_OF_POOL",
                    "signature_required": True,
                    "four_eyes_required": False,
                },
                {
                    "transition_no": 3,
                    "from_status": "IN_APPROVAL",
                    "to_status": "APPROVED",
                    "required_role": "APPROVER",
                    "decision_policy": "ONE_OF_POOL",
                    "signature_required": True,
                    "four_eyes_required": False,
                },
            ],
        },
        actor=actor,
        change_reason="test-signed-http-profile",
    )


def _build_signed_backend(tmp_path: Path):
    container, users = _build_documents_backend_container(tmp_path)
    _wire_signature_module(container, tmp_path)
    container.get_port("settings_service").set_module_settings(
        "signature",
        {"require_password": True, "default_mode": "visual"},
        acknowledge_governance_change=True,
        actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
    )
    _create_signed_flow_profile(container)
    return container, users


def _sign_intent_body(password: str) -> dict:
    return {
        "sign_intent": {
            "placement": {"page_index": 0, "x": 72.0, "y": 72.0, "target_width": 120.0},
            "layout": {
                "show_signature": True,
                "show_name": True,
                "show_date": True,
                "name_position": "above",
                "date_position": "below",
            },
            "password": password,
            "reason": "HTTP_TEST",
        }
    }


def _activate_editor_signature(client: TestClient, tmp_path: Path, token: str, *, password: str) -> None:
    png = tmp_path / "editor-sig.png"
    _create_signature_png(png)
    response = client.post(
        "/signature/assets/import-and-activate",
        headers={
            **_auth(token),
            "Content-Type": "image/png",
            "X-Signature-Password": password,
        },
        content=png.read_bytes(),
    )
    assert response.status_code == 200, response.text


def test_signed_transition_requires_sign_intent(tmp_path: Path) -> None:
    container, _users = _build_signed_backend(tmp_path)
    assert container.get_port("settings_service").get_module_settings("signature")["require_password"] is True
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": "DOC-SIGNED-GATE",
            "version": 1,
            "workflow_profile_id": "signed_http_profile",
        },
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        "/documents/versions/DOC-SIGNED-GATE/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    assigned = client.post(
        "/documents/versions/DOC-SIGNED-GATE/1/workflow/assign-roles",
        headers=_mutation_headers(admin, imported),
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert assigned.status_code == 200, assigned.text
    started = client.post(
        "/documents/versions/DOC-SIGNED-GATE/1/workflow/start",
        headers=_mutation_headers(admin, assigned),
        json={"profile_id": "signed_http_profile"},
    )
    assert started.status_code == 200, started.text
    editor = _login(client, "editor", "editorpass01")
    denied = client.post(
        "/documents/versions/DOC-SIGNED-GATE/1/workflow/editing-complete",
        headers=_mutation_headers(editor, started),
        json={},
    )
    assert denied.status_code == 400, denied.text


def test_signed_transition_rejects_sign_intent_without_password(tmp_path: Path) -> None:
    container, _users = _build_signed_backend(tmp_path)
    assert container.get_port("settings_service").get_module_settings("signature")["require_password"] is True
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": "DOC-SIGNED-PW",
            "version": 1,
            "workflow_profile_id": "signed_http_profile",
        },
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        "/documents/versions/DOC-SIGNED-PW/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    assigned = client.post(
        "/documents/versions/DOC-SIGNED-PW/1/workflow/assign-roles",
        headers=_mutation_headers(admin, imported),
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert assigned.status_code == 200, assigned.text
    started = client.post(
        "/documents/versions/DOC-SIGNED-PW/1/workflow/start",
        headers=_mutation_headers(admin, assigned),
        json={"profile_id": "signed_http_profile"},
    )
    assert started.status_code == 200, started.text
    editor = _login(client, "editor", EDITOR_HTTP_PASSWORD)
    _activate_editor_signature(client, tmp_path, editor, password=EDITOR_HTTP_PASSWORD)
    intent = _sign_intent_body(EDITOR_HTTP_PASSWORD)
    intent["sign_intent"]["password"] = None
    denied = client.post(
        "/documents/versions/DOC-SIGNED-PW/1/workflow/editing-complete",
        headers=_mutation_headers(editor, started),
        json=intent,
    )
    assert denied.status_code == 400, denied.text
    assert "password" in denied.text.lower()


def test_signed_workflow_transition_http(tmp_path: Path) -> None:
    if importlib.util.find_spec("pypdf") is None or importlib.util.find_spec("reportlab") is None:
        pytest.skip("visual signing dependencies missing")
    container, _users = _build_signed_backend(tmp_path)
    assert container.get_port("settings_service").get_module_settings("signature")["require_password"] is True
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-SIGNED-OK", "version": 1, "workflow_profile_id": "signed_http_profile"},
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    assigned = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/workflow/assign-roles",
        headers=_mutation_headers(admin, imported),
        json={"editors": ["editor"], "reviewers": ["reviewer"], "approvers": ["approver"]},
    )
    assert assigned.status_code == 200, assigned.text
    started = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/workflow/start",
        headers=_mutation_headers(admin, assigned),
        json={"profile_id": "signed_http_profile"},
    )
    assert started.status_code == 200, started.text

    editor = _login(client, "editor", EDITOR_HTTP_PASSWORD)
    _activate_editor_signature(client, tmp_path, editor, password=EDITOR_HTTP_PASSWORD)
    edited = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/workflow/editing-complete",
        headers=_mutation_headers(editor, started),
        json=_sign_intent_body(EDITOR_HTTP_PASSWORD),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["state"]["status"] == "IN_REVIEW"

    reviewer = _login(client, "reviewer", REVIEWER_HTTP_PASSWORD)
    _activate_editor_signature(client, tmp_path, reviewer, password=REVIEWER_HTTP_PASSWORD)
    reviewed = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/workflow/review/accept",
        headers=_mutation_headers(reviewer, edited),
        json=_sign_intent_body(REVIEWER_HTTP_PASSWORD),
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["state"]["status"] == "IN_APPROVAL"

    approver = _login(client, "approver", APPROVER_HTTP_PASSWORD)
    _activate_editor_signature(client, tmp_path, approver, password=APPROVER_HTTP_PASSWORD)
    approved = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/workflow/approval/accept",
        headers=_mutation_headers(approver, reviewed),
        json=_sign_intent_body(APPROVER_HTTP_PASSWORD),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"]["status"] == "APPROVED"

    artifacts = client.get("/documents/versions/DOC-SIGNED-OK/1/artifacts", headers=_auth(admin))
    assert artifacts.status_code == 200
    assert any(row.get("artifact_type") == "SIGNED_PDF" for row in artifacts.json())
    workflow_scratch = tmp_path / "scratch" / "workflow-sign"
    leftover = [path for path in workflow_scratch.rglob("*") if path.is_file()] if workflow_scratch.exists() else []
    assert leftover == []
    source_still = [
        row for row in artifacts.json() if row.get("artifact_type") == "SOURCE_PDF"
    ]
    assert source_still
    source_bytes = client.get(
        f"/documents/artifacts/{source_still[0]['artifact_id']}/content",
        headers=_auth(admin),
    )
    assert source_bytes.status_code == 200, source_bytes.text
    assert source_bytes.content.startswith(b"%PDF")

    qmb = _login(client, "qmb", QMB_HTTP_PASSWORD)
    _activate_editor_signature(client, tmp_path, qmb, password=QMB_HTTP_PASSWORD)
    extended = client.post(
        "/documents/versions/DOC-SIGNED-OK/1/lifecycle/extend-annual",
        headers=_mutation_headers(qmb, approved),
        json={
            **_sign_intent_body(QMB_HTTP_PASSWORD),
            "duration_days": 30,
            "reason": "annual review completed",
            "review_outcome": "unchanged",
        },
    )
    assert extended.status_code == 200, extended.text
    assert extended.json()["state"]["extension_count"] == 1
    after_extension = client.get(
        "/documents/versions/DOC-SIGNED-OK/1/artifacts", headers=_auth(qmb)
    )
    assert after_extension.status_code == 200
    assert len([row for row in after_extension.json() if row.get("artifact_type") == "SIGNED_PDF"]) >= 4
