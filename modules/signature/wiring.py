"""Port wiring for the signature module (SRP split B5)."""
from __future__ import annotations

from qm_platform.persistence.path_resolver import resolve_bootstrap_absolute_path

from .api import SignatureApi
from .secure_store import EncryptedSignatureBlobStore
from .service import SignatureServiceV2
from .sqlite_repository import SQLiteSignatureRepository


def register_signature_ports(container) -> None:
    settings_service = container.get_port("settings_service")
    usermanagement = container.get_port("usermanagement_service")
    app_home = container.get_port("app_home")
    templates_db = resolve_bootstrap_absolute_path(app_home, "signature", "templates_db_path")
    assets_root = resolve_bootstrap_absolute_path(app_home, "signature", "assets_root")
    key_path = resolve_bootstrap_absolute_path(app_home, "signature", "master_key_path")
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
