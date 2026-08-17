from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from qm_platform.events.event_bus import EventBus
from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_guard import LicenseGuard
from qm_platform.licensing.license_policy import LicensePolicy
from qm_platform.licensing.license_schema import SCHEMA_VERSION
from qm_platform.licensing.license_service import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMachineMismatchError,
    LicenseMissingError,
    LicenseService,
    LicenseTypeError,
)
from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.licensing.machine_id import get_machine_id
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.backup_reminder import BackupReminderService
from qm_platform.logging.log_backup_service import LogBackupService
from qm_platform.logging.log_query_service import LogQueryService
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.paths import resolve_home_path, resource_root, runtime_home
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService


def _prod_public_key_path(resources: Path) -> Path:
    return resources / "qm_platform" / "licensing" / "keys" / "prod_ed25519_public.pem"


def _register_public_keys(keyring: PublicKeyring, *, license_mode: str, app_home: Path, resources: Path) -> None:
    bundled_prod = _prod_public_key_path(resources)
    if bundled_prod.exists():
        keyring.add_key("prod-key", bundled_prod.read_text(encoding="utf-8"))
    legacy_prod = resolve_home_path(app_home, "storage/platform/license/prod_ed25519_public.pem")
    if legacy_prod.exists() and not keyring.has_key("prod-key"):
        keyring.add_key("prod-key", legacy_prod.read_text(encoding="utf-8"))
    if license_mode in ("dev", "auto"):
        dev_public_key = resolve_home_path(app_home, "storage/platform/license/dev_ed25519_public.pem")
        if dev_public_key.exists():
            keyring.add_key("dev-key", dev_public_key.read_text(encoding="utf-8"))


def _sign_dev_payload(payload: dict, private_key) -> dict:
    signed = dict(payload)
    message = LicenseVerifier.canonical_payload_bytes(signed)
    signed["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
    return signed


def _dev_license_payload(*, enabled_modules: list[str], machine_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "license_id": "DEV-LICENSE-001",
        "license_type": "full",
        "issued_to": "Local Development",
        "customer_id": "DEV",
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": None,
        "enabled_modules": sorted(enabled_modules),
        "machine_id": machine_id,
        "key_id": "dev-key",
    }


def _ensure_dev_license(license_file: Path, keyring: PublicKeyring) -> None:
    app_home = license_file.parent.parent
    key_dir = app_home / "storage/platform/license"
    key_dir.mkdir(parents=True, exist_ok=True)
    private_key_file = key_dir / "dev_ed25519_private.pem"
    public_key_file = key_dir / "dev_ed25519_public.pem"

    if not private_key_file.exists() or not public_key_file.exists():
        private_key = Ed25519PrivateKey.generate()
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        private_key_file.write_bytes(private_bytes)
        public_key_file.write_bytes(public_bytes)

    public_pem = public_key_file.read_text(encoding="utf-8")
    keyring.add_key("dev-key", public_pem)

    private_key = serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)
    desired_modules = sorted(runtime_bootstrap.core_license_tags())
    machine_id = get_machine_id()

    if license_file.exists():
        existing = json.loads(license_file.read_text(encoding="utf-8"))
        needs_rewrite = (
            int(existing.get("schema_version", 0)) != SCHEMA_VERSION
            or existing.get("machine_id") != machine_id
            or set(existing.get("enabled_modules", [])) != set(desired_modules)
        )
        if not needs_rewrite:
            return
        payload = _dev_license_payload(enabled_modules=desired_modules, machine_id=machine_id)
    else:
        payload = _dev_license_payload(enabled_modules=desired_modules, machine_id=machine_id)

    signed = _sign_dev_payload(payload, private_key)
    license_file.parent.mkdir(parents=True, exist_ok=True)
    license_file.write_text(json.dumps(signed, indent=2, ensure_ascii=True), encoding="utf-8")


def build_container(*, client_runtime_profile: str = "legacy") -> RuntimeContainer:
    container = RuntimeContainer()
    app_home = runtime_home()
    resources = resource_root()
    logger = LoggerService(resolve_home_path(app_home, "storage/platform/logs/platform.log"))
    audit = AuditLogger(resolve_home_path(app_home, "storage/platform/logs/audit.log"))
    events = EventBus()
    settings = SettingsService(SettingsRegistry())

    keyring = PublicKeyring()
    license_file = resolve_home_path(app_home, "license/license.json")
    license_mode = os.environ.get("QMTOOL_LICENSE_MODE", "dev").strip().lower()
    if license_mode in ("dev", "auto"):
        _ensure_dev_license(license_file, keyring)
    _register_public_keys(keyring, license_mode=license_mode, app_home=app_home, resources=resources)

    license_service = LicenseService(
        license_file=license_file,
        verifier=LicenseVerifier(keyring),
        policy=LicensePolicy(local_machine_id=get_machine_id()),
    )
    if license_mode not in ("dev", "auto"):
        try:
            license_service.validate()
        except (
            LicenseMissingError,
            LicenseInvalidError,
            LicenseExpiredError,
            LicenseTypeError,
            LicenseMachineMismatchError,
        ) as exc:
            logger.warning("platform", f"license not valid at startup (app continues): {exc}")
    license_guard = LicenseGuard(license_service)

    container.register_port("logger", logger)
    container.register_port("audit_logger", audit)
    container.register_port(
        "log_query_service",
        LogQueryService(
            platform_log_file=resolve_home_path(app_home, "storage/platform/logs/platform.log"),
            audit_log_file=resolve_home_path(app_home, "storage/platform/logs/audit.log"),
        ),
    )
    backup_service = LogBackupService(
        platform_log_file=resolve_home_path(app_home, "storage/platform/logs/platform.log"),
        audit_log_file=resolve_home_path(app_home, "storage/platform/logs/audit.log"),
        backup_dir=resolve_home_path(app_home, "storage/platform/backups/logs"),
        state_file=resolve_home_path(app_home, "storage/platform/backups/logs/_state.json"),
        audit_logger=audit,
    )
    # Backup reminder threshold is settings-dependent; attach after DB settings cutover
    # via register_core_modules / activate. Default 30 until then.
    container.register_port("log_backup_service", backup_service)
    container.register_port(
        "backup_reminder_service",
        BackupReminderService(backup_service, threshold_days=30),
    )
    container.register_port("event_bus", events)
    container.register_port("settings_service", settings)
    container.register_port("license_service", license_service)
    container.register_port("license_guard", license_guard)
    container.register_port("app_home", app_home)
    container.register_port("resource_root", resources)
    # J04-M0: shipped active client profile is backend (HTTP Documents/Signature).
    from qm_platform.runtime.client_runtime_profile import CLIENT_RUNTIME_PROFILE_PORT, normalize_client_runtime_profile

    container.register_port(CLIENT_RUNTIME_PROFILE_PORT, normalize_client_runtime_profile(client_runtime_profile))
    # J04-M0-P1: inject HTTP documents/signature ports without modules→interfaces import.
    from interfaces.clients.documents_http_ports import register_documents_http_ports
    from interfaces.clients.signature_http_ports import register_signature_http_ports

    container.register_port("documents_client_ports_registrar", register_documents_http_ports)
    container.register_port("signature_client_ports_registrar", register_signature_http_ports)
    return container
