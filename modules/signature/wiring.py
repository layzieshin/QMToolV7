"""Port wiring for the signature module (SRP split B5)."""
from __future__ import annotations

from qm_platform.persistence.path_resolver import resolve_bootstrap_absolute_path

from .api import SignatureApi
from .postgres_repository import PostgresSignatureRepository
from .secure_store import EncryptedSignatureBlobStore
from .service import SignatureServiceV2
from .sqlite_repository import SQLiteSignatureRepository

# Explicit in-process opt-in for tests/dev harnesses. Never a free product env var.
def _should_register_sqlite(container) -> bool:
    if container.has_port("signature_runtime_owner"):
        if container.get_port("signature_runtime_owner") == "backend":
            return True
    if container.has_port("signature_allow_inprocess_sqlite"):
        return bool(container.get_port("signature_allow_inprocess_sqlite"))
    # Backend client profile never opens local signature SQLite.
    if container.has_port("client_runtime_profile"):
        profile = str(container.get_port("client_runtime_profile") or "").strip().lower()
        if profile == "backend":
            return False
        if profile == "legacy":
            return True
    # Default without profile: keep prior desktop behavior for legacy/test paths.
    return True


def register_signature_ports(container) -> None:
    if _should_register_sqlite(container):
        captured = (
            container.get_port("signature_postgres_dsn")
            if container.has_port("signature_postgres_dsn")
            else None
        )
        if captured is not None and bool(str(captured).strip()):
            _register_signature_postgres_ports(container, str(captured))
        else:
            _register_signature_sqlite_ports(container)
        return
    if not container.has_port("signature_client_ports_registrar"):
        raise RuntimeError(
            "signature client ports registrar missing; "
            "composition root must register signature_client_ports_registrar "
            "before activating the signature client module"
        )
    if container.has_port("signature_client_ports_registrar"):
        registrar = container.get_port("signature_client_ports_registrar")
    else:
        raise RuntimeError("signature client ports registrar missing")
    if not callable(registrar):
        raise RuntimeError("signature_client_ports_registrar must be callable")
    registrar(container)


def _register_signature_postgres_ports(container, postgres_dsn: str) -> None:
    _register_signature_backend_ports(container, postgres=True, postgres_dsn=postgres_dsn)


def _register_signature_sqlite_ports(container) -> None:
    _register_signature_backend_ports(container, postgres=False)


def _register_signature_backend_ports(container, *, postgres: bool, postgres_dsn: str | None = None) -> None:
    settings_service = container.get_port("settings_service")
    usermanagement = container.get_port("usermanagement_service")
    app_home = container.get_port("app_home")
    assets_root = resolve_bootstrap_absolute_path(app_home, "signature", "assets_root")
    key_path = resolve_bootstrap_absolute_path(app_home, "signature", "master_key_path")
    if postgres:
        repository = PostgresSignatureRepository(postgres_dsn)
    else:
        templates_db = resolve_bootstrap_absolute_path(app_home, "signature", "templates_db_path")
        repository = SQLiteSignatureRepository(db_path=templates_db)
    secure_store = EncryptedSignatureBlobStore(root=assets_root, key_file=key_path)
    service = SignatureServiceV2(
        settings_service=settings_service,
        logger=container.get_port("logger"),
        audit_logger=container.get_port("audit_logger"),
        password_verifier=lambda username, password: usermanagement.authenticate(username, password) is not None,
        event_bus=container.get_port("event_bus"),
        crypto_signer=None,
        repository=repository,
        secure_store=secure_store,
    )
    container.register_port("signature_service", service)
    container.register_port("signature_api", SignatureApi(service))
