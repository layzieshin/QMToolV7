"""Architecture gates for J04-M0 documents HTTP transport."""
from __future__ import annotations

from pathlib import Path

from interfaces.clients.documents_http_ports import register_documents_http_ports
from modules.documents.wiring import DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT, register_documents_ports
from qm_platform.runtime.container import RuntimeContainer

ROOT = Path(__file__).resolve().parents[2]


def _client_container() -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("documents_client_ports_registrar", register_documents_http_ports)
    return container


def test_interfaces_do_not_import_sqlite_documents_repository() -> None:
    offenders: list[str] = []
    for path in (ROOT / "interfaces").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "SQLiteDocumentsRepository" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_documents_wiring_does_not_import_interfaces() -> None:
    text = (ROOT / "modules/documents/wiring.py").read_text(encoding="utf-8")
    assert "interfaces." not in text
    assert "interfaces/" not in text


def test_documents_http_ports_module_exists() -> None:
    path = ROOT / "interfaces/clients/documents_http_ports.py"
    assert path.is_file()


def test_artifacts_http_client_has_no_local_storage_paths() -> None:
    text = (ROOT / "interfaces/clients/documents_http_ports.py").read_text(encoding="utf-8")
    assert "Path.cwd()" not in text
    assert "HttpDocumentsArtifactsApi" in text
    assert "storage_key" not in text or 'storage_key=""' in (
        ROOT / "interfaces/clients/documents_http.py"
    ).read_text(encoding="utf-8")
    assert "_FailClosedArtifactsApi" not in text
    assert "_FailClosedCommentsApi" not in text


def test_documents_route_bodies_do_not_accept_client_actor_user_id() -> None:
    content = (ROOT / "src/backend/documents_routes.py").read_text(encoding="utf-8")
    in_body = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("class ") and "Body(" in stripped:
            in_body = True
            continue
        if in_body and stripped.startswith("class ") and "Body(" not in stripped:
            in_body = False
        if in_body and stripped.startswith("actor_user_id"):
            raise AssertionError("documents route Body must not accept actor_user_id from clients")


def test_pyqt_runtime_binds_session_token_provider_not_env() -> None:
    host = (ROOT / "interfaces/pyqt/runtime/host.py").read_text(encoding="utf-8")
    assert "bind_pyqt_session_token_provider" in host
    assert "create_backend_session_api" in host
    assert "backend_session_api" in host
    assert "BackendIdentityAdapter" in host
    assert "bind_signature_session_token_provider" in host
    assert "clear_signature_session_token_provider" in host
    assert "QMTOOL_SESSION_TOKEN" not in host

    coordinator = (ROOT / "interfaces/pyqt/shell/session_coordinator.py").read_text(encoding="utf-8")
    assert "backend_session" in coordinator
    assert "uses_backend_session" in coordinator

    documents_http = (ROOT / "interfaces/clients/documents_http.py").read_text(encoding="utf-8")
    assert "_reject_env_token" in documents_http
    assert "bind_pyqt_session_token_provider" in documents_http

    signature_http = (ROOT / "interfaces/clients/signature_http.py").read_text(encoding="utf-8")
    assert "_reject_env_token" in signature_http
    assert "bind_pyqt_session_token_provider" in signature_http


def test_pyqt_backend_identity_has_no_shadow_login() -> None:
    identity = (ROOT / "interfaces/clients/backend_identity.py").read_text(encoding="utf-8")
    assert "BackendIdentityAdapter" in identity
    assert "/users/directory" in identity
    assert "lokales Login" in identity
    # Must not call local UM login to fabricate a session.
    assert "usermanagement_service.login" not in identity
    assert "_local.login" not in identity

    main_window = (ROOT / "interfaces/pyqt/shell/main_window.py").read_text(encoding="utf-8")
    assert "QTimer.singleShot(0, lambda: self._prompt_login(required=True))" in main_window
    assert "user_facing_auth_message" in main_window
    assert "allow_local_register=not self._session.uses_backend_session" in main_window
    assert "force_logged_out()" in main_window


def test_product_env_var_does_not_enable_local_documents_sqlite(monkeypatch) -> None:
    """QMTOOL_DOCUMENTS_LOCAL_WIRING must not be a free product switch."""
    monkeypatch.setenv("QMTOOL_DOCUMENTS_LOCAL_WIRING", "1")
    container = _client_container()
    register_documents_ports(container)
    assert not container.has_port("documents_service")
    assert "HttpDocuments" in type(container.get_port("documents_pool_api")).__name__


def test_client_wiring_without_owner_never_registers_sqlite_repository(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_DOCUMENTS_LOCAL_WIRING", raising=False)
    container = _client_container()
    register_documents_ports(container)
    assert not container.has_port("documents_service")
    pool = container.get_port("documents_pool_api")
    assert type(pool).__name__ == "HttpDocumentsPoolApi"


def test_inprocess_sqlite_requires_explicit_container_opt_in(tmp_path: Path, monkeypatch) -> None:
    from types import MappingProxyType

    from modules.documents.wiring import _register_documents_sqlite_ports
    from qm_platform.events.event_bus import EventBus
    from qm_platform.logging.audit_logger import AuditLogger
    from qm_platform.logging.logger_service import LoggerService
    from qm_platform.persistence.database_evolution import DATABASE_PREFLIGHT_STATUSES_PORT, DatabaseStatus
    from qm_platform.settings.testing import build_settings_service_for_tests
    from tests.database_helpers import prepare_test_database, registry_repository
    from modules.registry.projection_api import RegistryProjectionApi
    from modules.registry.service import RegistryService

    monkeypatch.delenv("QMTOOL_DOCUMENTS_LOCAL_WIRING", raising=False)
    docs_db = tmp_path / "storage" / "documents" / "documents.db"
    docs_db.parent.mkdir(parents=True, exist_ok=True)
    prepare_test_database("documents", docs_db)

    denied = _client_container()
    register_documents_ports(denied)
    assert not denied.has_port("documents_service")

    allowed = RuntimeContainer()
    allowed.register_port("logger", LoggerService(tmp_path / "platform.log"))
    allowed.register_port("audit_logger", AuditLogger(tmp_path / "audit.log"))
    allowed.register_port("event_bus", EventBus())
    allowed.register_port("settings_service", build_settings_service_for_tests(tmp_path))
    allowed.register_port("app_home", tmp_path)
    allowed.register_port("resource_root", ROOT)
    allowed.register_port("signature_api", object())
    allowed.register_port(
        "registry_projection_api",
        RegistryProjectionApi(RegistryService(registry_repository(tmp_path / "registry.db"))),
    )
    allowed.register_port(
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
                )
            }
        ),
    )
    allowed.register_port(DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT, True)
    register_documents_ports(allowed)
    assert allowed.has_port("documents_service")
