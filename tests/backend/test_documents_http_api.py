from __future__ import annotations

from types import MappingProxyType
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from modules.documents.wiring import register_documents_ports
from modules.registry.projection_api import RegistryProjectionApi
from modules.registry.service import RegistryService
from modules.usermanagement.api import login_backend, resolve_session
from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import UserManagementService
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.persistence.database_evolution import DATABASE_PREFLIGHT_STATUSES_PORT, DatabaseStatus
from qm_platform.runtime.backend_bootstrap import wire_backend_documents
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.testing import build_settings_service_for_tests
from src.backend.api import create_app
from tests.database_helpers import prepare_test_database, registry_repository, user_repository

ROOT = Path(__file__).resolve().parents[2]


class _TestSettingsProxy:
    """Keep the fixture's delegated-create setting local to the test host."""

    def __init__(self, delegate) -> None:
        self._delegate = delegate

    def get_module_settings(self, module_id: str):
        values = dict(self._delegate.get_module_settings(module_id))
        if module_id == "documents":
            values["can_create_new_documents"] = {"admin": True}
        return values

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)


class _FakeSignatureApi:
    def sign_with_fixed_position(self, request: object) -> object:
        return request


def _build_documents_backend_container(root: Path) -> tuple[RuntimeContainer, object]:
    container = RuntimeContainer()
    events = EventBus()
    docs_db = root / "storage" / "documents" / "documents.db"
    docs_db.parent.mkdir(parents=True, exist_ok=True)
    prepare_test_database("documents", docs_db)
    container.register_port("logger", LoggerService(root / "platform.log"))
    container.register_port("audit_logger", AuditLogger(root / "audit.log"))
    container.register_port("event_bus", events)
    settings = build_settings_service_for_tests(root)
    container.register_port("settings_service", _TestSettingsProxy(settings))
    container.register_port("app_home", root)
    container.register_port("resource_root", ROOT)
    container.register_port(
        DATABASE_PREFLIGHT_STATUSES_PORT,
        MappingProxyType(
            {
                "documents": DatabaseStatus(
                    database_id="documents",
                    path=str(docs_db),
                    state="adoptable_v1",
                    current_version=1,
                    target_version=2,
                    pending_versions=(2,),
                    integrity="ok",
                    detail=None,
                )
            }
        ),
    )
    container.register_port("signature_api", _FakeSignatureApi())
    reg_api = RegistryProjectionApi(RegistryService(registry_repository(root / "registry.db")))
    container.register_port("registry_projection_api", reg_api)
    users = user_repository(root / "users.db")
    try:
        users.ensure_initial_admin("admin", "adminpass01", role="Admin", must_change_password=False)
    except Exception:
        pass
    service = UserManagementService(
        event_bus=events,
        repository=users,
        session_repository=InMemorySessionRepository(),
    )
    service.set_user_qmb("admin", True)
    for username, password, role, is_qmb in (
        ("qmb", "qmbpass001", "QMB", True),
        ("editor", "editorpass01", "User", False),
        ("reviewer", "reviewerpass01", "User", False),
        ("approver", "approverpass01", "User", False),
        ("observer", "observerpass01", "User", False),
    ):
        try:
            service.create_user(username, password, role=role, is_qmb=is_qmb)
        except Exception:
            pass
    container.register_port("usermanagement_service", service)
    container.register_port("documents_runtime_owner", "backend")
    register_documents_ports(container)

    issued = login_backend(container, "qmb", "qmbpass001", request_id="seed-http-profile")
    actor = resolve_session(container, issued.raw_token, request_id="seed-http-profile")
    workflow_api = container.get_port("documents_workflow_api")
    try:
        workflow_api.create_workflow_profile_definition(
            {
                "profile_code": "http_flow_profile",
                "label": "HTTP Flow Profile",
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
                ],
            },
            actor=actor,
            change_reason="test-http-flow-profile",
        )
    except Exception:
        pass
    return container, users


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mutation_headers(token: str, state_response, *, extra: dict[str, str] | None = None) -> dict[str, str]:
    if isinstance(state_response, str):
        etag = state_response
    else:
        state = state_response.json()["state"]
        etag = str(state.get("last_event_id") or "none")
    headers = {**_auth(token), "If-Match": etag}
    if extra:
        headers.update(extra)
    return headers


def _minimal_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000117 00000 n \n"
        b"trailer << /Root 1 0 R /Size 4 >>\nstartxref\n188\n%%EOF\n"
    )


def _create_assign_start(client: TestClient, users, *, doc_id: str) -> dict:
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": doc_id,
            "version": 1,
            "title": doc_id,
            "doc_type": "OTHER",
            "control_class": "CONTROLLED",
            "workflow_profile_id": "http_flow_profile",
        },
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        f"/documents/versions/{doc_id}/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    assigned = client.post(
        f"/documents/versions/{doc_id}/1/workflow/assign-roles",
        headers=_mutation_headers(admin, imported),
        json={
            "editors": ["editor"],
            "reviewers": ["reviewer"],
            "approvers": ["approver"],
        },
    )
    assert assigned.status_code == 200, assigned.text
    editor_token = _login(client, "editor", "editorpass01")
    started = client.post(
        f"/documents/versions/{doc_id}/1/workflow/start",
        headers=_mutation_headers(admin, assigned),
        json={"profile_id": "http_flow_profile"},
    )
    assert started.status_code == 200, started.text
    return {
        "admin": admin,
        "editor": editor_token,
        "reviewer": _login(client, "reviewer", "reviewerpass01"),
        "approver": _login(client, "approver", "approverpass01"),
        "state_response": started,
    }


def test_flow_create_assign_start_approve(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-HTTP-A")
    edited = client.post(
        "/documents/versions/DOC-HTTP-A/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    reviewed = client.post(
        "/documents/versions/DOC-HTTP-A/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    assert reviewed.status_code == 200, reviewed.text
    approved = client.post(
        "/documents/versions/DOC-HTTP-A/1/workflow/approval/accept",
        headers=_mutation_headers(tokens["approver"], reviewed),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"]["status"] == "APPROVED"
    assert approved.json()["state"]["last_actor_user_id"] == "approver"


def test_flow_review_reject_returns_in_progress(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-HTTP-B")
    edited = client.post(
        "/documents/versions/DOC-HTTP-B/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    rejected = client.post(
        "/documents/versions/DOC-HTTP-B/1/workflow/review/reject",
        headers=_mutation_headers(tokens["reviewer"], edited),
        json={"template_text": "reject"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"]["status"] == "IN_PROGRESS"


def test_flow_approval_reject(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-HTTP-AR")
    edited = client.post(
        "/documents/versions/DOC-HTTP-AR/1/workflow/editing-complete",
        headers=_mutation_headers(tokens["editor"], tokens["state_response"]),
    )
    assert edited.status_code == 200, edited.text
    reviewed = client.post(
        "/documents/versions/DOC-HTTP-AR/1/workflow/review/accept",
        headers=_mutation_headers(tokens["reviewer"], edited),
    )
    assert reviewed.status_code == 200, reviewed.text
    rejected = client.post(
        "/documents/versions/DOC-HTTP-AR/1/workflow/approval/reject",
        headers=_mutation_headers(tokens["approver"], reviewed),
        json={"template_text": "reject-approval"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["state"]["status"] == "IN_PROGRESS"
    assert rejected.json()["state"]["last_actor_user_id"] == "approver"


def test_flow_abort(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-HTTP-C")
    aborted = client.post(
        "/documents/versions/DOC-HTTP-C/1/workflow/abort",
        headers=_mutation_headers(tokens["admin"], tokens["state_response"]),
    )
    assert aborted.status_code == 200, aborted.text
    assert aborted.json()["state"]["status"] == "PLANNED"


def test_duplicate_create_returns_409_without_resetting_etag(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": "DOC-DUP-HTTP",
            "version": 1,
            "title": "Original",
            "workflow_profile_id": "http_flow_profile",
        },
    )
    assert created.status_code == 200, created.text
    duplicate = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={
            "document_id": "DOC-DUP-HTTP",
            "version": 1,
            "title": "Reset",
            "workflow_profile_id": "http_flow_profile",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    detail = duplicate.json()["detail"]
    assert detail["error"] == "document_conflict"
    assert detail["current_etag"] == created.json()["etag"]
    assert detail["current_state"]["title"] == "Original"
    assert detail["current_state"]["status"] == "PLANNED"
    current = client.get("/documents/versions/DOC-DUP-HTTP/1", headers=_auth(admin))
    assert current.status_code == 200, current.text
    assert current.json()["etag"] == created.json()["etag"]
    assert current.json()["state"]["title"] == "Original"


def test_duplicate_create_after_workflow_start_returns_409_and_keeps_in_progress(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-DUP-STARTED-HTTP")
    started = tokens["state_response"]
    duplicate = client.post(
        "/documents/versions/create",
        headers=_auth(tokens["admin"]),
        json={
            "document_id": "DOC-DUP-STARTED-HTTP",
            "version": 1,
            "title": "rewind",
            "workflow_profile_id": "http_flow_profile",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    detail = duplicate.json()["detail"]
    assert detail["error"] == "document_conflict"
    assert detail["current_etag"] == started.json()["etag"]
    assert detail["current_state"]["status"] == started.json()["state"]["status"]
    current = client.get("/documents/versions/DOC-DUP-STARTED-HTTP/1", headers=_auth(tokens["admin"]))
    assert current.status_code == 200, current.text
    assert current.json()["etag"] == started.json()["etag"]
    assert current.json()["state"]["status"] == started.json()["state"]["status"]
    assert current.json()["state"]["status"] != "PLANNED"


def test_actor_tampering_ignored_for_mutations(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-TAMPER", "version": 1, "workflow_profile_id": "http_flow_profile"},
    )
    assigned = client.post(
        "/documents/versions/DOC-TAMPER/1/workflow/assign-roles",
        headers=_mutation_headers(admin, created),
        json={
            "editors": ["editor"],
            "reviewers": ["reviewer"],
            "approvers": ["approver"],
            "actor_user_id": "observer",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["state"]["last_actor_user_id"] == "admin"
    assert assigned.json()["state"]["last_actor_user_id"] != "observer"


def test_two_clients_and_restart_readback(tmp_path: Path) -> None:
    """Same-process session isolation + restart readback.

    Two Starlette TestClients share one backend container/process. This proves
    distinct Bearer sessions see the same backend-owned state; it is not a
    multi-process concurrency or lock-stress test.
    """
    container, users = _build_documents_backend_container(tmp_path)
    client_a = TestClient(create_app(container))
    client_b = TestClient(create_app(container))
    tokens = _create_assign_start(client_a, users, doc_id="DOC-HTTP-R")
    read_before = client_b.get("/documents/versions/DOC-HTTP-R/1", headers=_auth(tokens["reviewer"]))
    assert read_before.status_code == 200, read_before.text
    restarted_container, _users = _build_documents_backend_container(tmp_path)
    restarted = TestClient(create_app(restarted_container))
    reviewer = _login(restarted, "reviewer", "reviewerpass01")
    read_after = restarted.get("/documents/versions/DOC-HTTP-R/1", headers=_auth(reviewer))
    assert read_after.status_code == 200, read_after.text
    assert read_after.json()["state"]["document_id"] == "DOC-HTTP-R"


def test_import_pdf_rejects_invalid_content_type(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    create = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-PDF", "version": 1},
    )
    assert create.status_code == 200, create.text
    bad = client.post(
        "/documents/versions/DOC-PDF/1/import-pdf",
        headers={**_mutation_headers(admin, create), "Content-Type": "text/plain"},
        content=b"not-pdf",
    )
    assert bad.status_code == 400
    assert bad.json()["detail"]["error"] == "invalid_content_type"


def test_profile_mutation_available_over_http(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    qmb = _login(client, "qmb", "qmbpass001")
    response = client.post(
        "/documents/workflow-profiles/definitions",
        headers=_auth(qmb),
        json={
            "payload": {
                "profile_code": "http_mutation_check",
                "label": "Mutation Check",
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
                ],
            },
            "change_reason": "http-api-test",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["profile_code"] == "http_mutation_check"


def test_wire_backend_documents_registers_documents_sqlite_owner(tmp_path: Path, monkeypatch) -> None:
    container = RuntimeContainer()
    events = EventBus()
    docs_db = tmp_path / "storage" / "documents" / "documents.db"
    docs_db.parent.mkdir(parents=True, exist_ok=True)
    prepare_test_database("documents", docs_db)
    container.register_port("logger", LoggerService(tmp_path / "platform.log"))
    container.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    container.register_port("event_bus", events)
    container.register_port("settings_service", build_settings_service_for_tests(tmp_path))
    container.register_port("app_home", tmp_path)
    container.register_port("resource_root", ROOT)
    container.register_port(
        DATABASE_PREFLIGHT_STATUSES_PORT,
        MappingProxyType(
            {
                "documents": DatabaseStatus(
                    database_id="documents",
                    path=str(docs_db),
                    state="adoptable_v1",
                    current_version=1,
                    target_version=2,
                    pending_versions=(2,),
                    integrity="ok",
                    detail=None,
                )
            }
        ),
    )
    container.register_port("signature_api", _FakeSignatureApi())
    reg_api = RegistryProjectionApi(RegistryService(registry_repository(tmp_path / "registry.db")))
    container.register_port("registry_projection_api", reg_api)
    users = user_repository(tmp_path / "users.db")
    users.ensure_initial_admin("admin", "adminpass01", role="Admin", must_change_password=False)
    container.register_port(
        "usermanagement_service",
        UserManagementService(
            event_bus=events,
            repository=users,
            session_repository=InMemorySessionRepository(),
        ),
    )
    monkeypatch.setattr("qm_platform.runtime.lifecycle.ensure_required_capabilities", lambda *_args, **_kwargs: None)
    wire_backend_documents(container)
    assert container.has_port("documents_service")
    assert docs_db.exists()


def test_import_pdf_roundtrip(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-PDF-OK", "version": 1},
    )
    assert created.status_code == 200, created.text
    imported = client.post(
        "/documents/versions/DOC-PDF-OK/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["state"]["document_id"] == "DOC-PDF-OK"


def test_import_pdf_and_docx_consume_etag_and_reject_replay(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created_pdf = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-IMP-CAS-PDF", "version": 1},
    )
    assert created_pdf.status_code == 200, created_pdf.text
    prior_pdf = created_pdf.json()["etag"]
    imported_pdf = client.post(
        "/documents/versions/DOC-IMP-CAS-PDF/1/import-pdf",
        headers={**_mutation_headers(admin, created_pdf), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported_pdf.status_code == 200, imported_pdf.text
    assert imported_pdf.json()["etag"] != prior_pdf
    replay_pdf = client.post(
        "/documents/versions/DOC-IMP-CAS-PDF/1/import-pdf",
        headers={**_mutation_headers(admin, created_pdf), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert replay_pdf.status_code == 409, replay_pdf.text
    assert replay_pdf.json()["detail"]["current_etag"] == imported_pdf.json()["etag"]

    created_docx = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-IMP-CAS-DOCX", "version": 1},
    )
    assert created_docx.status_code == 200, created_docx.text
    prior_docx = created_docx.json()["etag"]
    imported_docx = client.post(
        "/documents/versions/DOC-IMP-CAS-DOCX/1/import-docx",
        headers={
            **_mutation_headers(admin, created_docx),
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        content=b"PK\x03\x04docx-stub",
    )
    assert imported_docx.status_code == 200, imported_docx.text
    assert imported_docx.json()["etag"] != prior_docx
    replay_docx = client.post(
        "/documents/versions/DOC-IMP-CAS-DOCX/1/import-docx",
        headers={
            **_mutation_headers(admin, created_docx),
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        content=b"PK\x03\x04docx-stub",
    )
    assert replay_docx.status_code == 409, replay_docx.text
    assert replay_docx.json()["detail"]["current_etag"] == imported_docx.json()["etag"]


def test_unusual_document_id_remains_fachlich_and_omits_storage_paths(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    weird_id = "DOC-WEIRD..ID"
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": weird_id, "version": 1, "title": weird_id},
    )
    assert created.status_code == 200, created.text
    assert created.json()["state"]["document_id"] == weird_id
    imported = client.post(
        f"/documents/versions/{weird_id}/1/import-pdf",
        headers={**_mutation_headers(admin, created), "Content-Type": "application/pdf"},
        content=_minimal_pdf_bytes(),
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["state"]["document_id"] == weird_id
    listed = client.get(f"/documents/versions/{weird_id}/1/artifacts", headers=_auth(admin))
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload
    serialized = str(payload).lower()
    assert "storage_key" not in serialized
    assert "scratch" not in serialized
    assert ":\\" not in str(payload)
    assert "/objects/" not in serialized
    scratch_root = tmp_path / "scratch" / "imports"
    leftover = list(scratch_root.glob("*")) if scratch_root.exists() else []
    assert leftover == []
    stored_files = [path for path in tmp_path.rglob("*.pdf") if path.is_file()]
    assert stored_files
    for path in stored_files:
        assert "WEIRD" not in path.as_posix()
        assert ".." not in path.as_posix()


def test_new_document_id_with_slash_is_rejected(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")

    response = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC/NEW", "version": 1},
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["error"] == "documents_workflow"


def test_pool_list_by_status(tmp_path: Path) -> None:
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    _create_assign_start(client, users, doc_id="DOC-POOL-1")
    admin = _login(client, "admin", "adminpass01")
    response = client.get("/documents/pool/by-status/IN_PROGRESS", headers=_auth(admin))
    assert response.status_code == 200, response.text
    rows = response.json()
    assert any(row["document_id"] == "DOC-POOL-1" and row["status"] == "IN_PROGRESS" for row in rows)


def test_version_read_after_restart(tmp_path: Path) -> None:
    """Restart readback of the same backend-owned documents.db (same-process TestClients)."""
    container, users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    tokens = _create_assign_start(client, users, doc_id="DOC-RESTART-1")
    before = client.get("/documents/versions/DOC-RESTART-1/1", headers=_auth(tokens["reviewer"]))
    assert before.status_code == 200, before.text
    restarted_container, _users = _build_documents_backend_container(tmp_path)
    restarted = TestClient(create_app(restarted_container))
    reviewer = _login(restarted, "reviewer", "reviewerpass01")
    after = restarted.get("/documents/versions/DOC-RESTART-1/1", headers=_auth(reviewer))
    assert after.status_code == 200, after.text
    assert after.json()["state"]["status"] == "IN_PROGRESS"


def test_header_read(tmp_path: Path) -> None:
    container, _users = _build_documents_backend_container(tmp_path)
    client = TestClient(create_app(container))
    admin = _login(client, "admin", "adminpass01")
    created = client.post(
        "/documents/versions/create",
        headers=_auth(admin),
        json={"document_id": "DOC-HEADER", "version": 1, "workflow_profile_id": "http_flow_profile"},
    )
    assert created.status_code == 200, created.text
    response = client.get("/documents/headers/DOC-HEADER", headers=_auth(admin))
    assert response.status_code == 200, response.text
    assert response.json()["document_id"] == "DOC-HEADER"
    assert response.json()["workflow_profile_id"] == "http_flow_profile"


def test_http_workflow_port_exposes_p4_p9_methods() -> None:
    from interfaces.clients.documents_http_ports import HttpDocumentsCommentsApi, HttpDocumentsWorkflowApi

    assert hasattr(HttpDocumentsWorkflowApi(), "list_change_requests")
    assert hasattr(HttpDocumentsCommentsApi(), "list_workflow_comments")


def test_http_read_port_routes_through_documents_client() -> None:
    from unittest.mock import MagicMock, patch

    from interfaces.clients.documents_http_ports import HttpDocumentsReadApi

    client = MagicMock()
    client.open_released_document.return_value = object()
    client.confirm_released_document_read.return_value = object()
    client.get_read_receipt.return_value = None
    client.start_tracked_pdf_read.return_value = object()
    client.record_page_dwell.return_value = object()
    client.get_pdf_read_progress.return_value = object()
    client.finalize_tracked_pdf_read.return_value = None
    read_api = HttpDocumentsReadApi()

    with patch(
        "interfaces.clients.documents_http_ports.DocumentsHttpClient.for_runtime",
        return_value=client,
    ):
        assert read_api.open_released_document_for_training("client-user", "DOC-1", 1) is client.open_released_document.return_value
        assert read_api.confirm_released_document_read("client-user", "DOC-1", 1, source="x") is client.confirm_released_document_read.return_value
        assert read_api.get_read_receipt("client-user", "DOC-1", 1) is None
        assert read_api.start_tracked_pdf_read(
            "client-user",
            "DOC-1",
            1,
            artifact_id="art",
            total_pages=2,
            source="TRAINING_READ",
        ) is client.start_tracked_pdf_read.return_value
        assert read_api.record_page_dwell("sess", page_number=1, dwell_seconds=5) is client.record_page_dwell.return_value
        assert read_api.get_pdf_read_progress("sess") is client.get_pdf_read_progress.return_value
        assert read_api.finalize_tracked_pdf_read("sess", source="TRAINING_READ") is None

    client.open_released_document.assert_called_once_with("DOC-1", 1)
    client.confirm_released_document_read.assert_called_once_with("DOC-1", 1, source="x")
    client.get_read_receipt.assert_called_once_with("DOC-1", 1)
    client.start_tracked_pdf_read.assert_called_once_with(
        "DOC-1",
        1,
        artifact_id="art",
        total_pages=2,
        source="TRAINING_READ",
        min_seconds_per_page=10,
    )
