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
from qm_platform.licensing.license_service import LicenseService
from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.log_query_service import LogQueryService
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.paths import resolve_home_path, resource_root, runtime_home
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


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
    desired_modules = set(runtime_bootstrap.core_license_tags())

    if license_file.exists():
        existing = json.loads(license_file.read_text(encoding="utf-8"))
        modules = set(existing.get("enabled_modules", []))
        if desired_modules.issubset(modules):
            return
        existing["enabled_modules"] = sorted(modules | desired_modules)
        message = LicenseVerifier.canonical_payload_bytes(existing)
        existing["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
        license_file.write_text(json.dumps(existing, indent=2, ensure_ascii=True), encoding="utf-8")
        return

    payload = {
        "license_id": "DEV-LICENSE-001",
        "issued_to": "Local Development",
        "customer_id": "DEV",
        "plan": "dev",
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "enabled_modules": sorted(desired_modules),
        "device_binding": {"mode": "optional"},
        "constraints": {},
        "key_id": "dev-key",
    }
    message = LicenseVerifier.canonical_payload_bytes(payload)
    payload["signature"] = base64.b64encode(private_key.sign(message)).decode("ascii")
    license_file.parent.mkdir(parents=True, exist_ok=True)
    license_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def build_container() -> RuntimeContainer:
    container = RuntimeContainer()
    app_home = runtime_home()
    resources = resource_root()
    logger = LoggerService(resolve_home_path(app_home, "storage/platform/logs/platform.log"))
    audit = AuditLogger(resolve_home_path(app_home, "storage/platform/logs/audit.log"))
    events = EventBus()
    settings = SettingsService(SettingsRegistry(), SettingsStore(resolve_home_path(app_home, "storage/platform/settings.json")))

    keyring = PublicKeyring()
    license_file = resolve_home_path(app_home, "license/license.json")
    license_mode = os.environ.get("QMTOOL_LICENSE_MODE", "dev").strip().lower()
    if license_mode in ("dev", "auto"):
        _ensure_dev_license(license_file, keyring)
    else:
        dev_public_key = resolve_home_path(app_home, "storage/platform/license/dev_ed25519_public.pem")
        if dev_public_key.exists():
            keyring.add_key("dev-key", dev_public_key.read_text(encoding="utf-8"))
    license_service = LicenseService(
        license_file=license_file,
        verifier=LicenseVerifier(keyring),
        policy=LicensePolicy(),
    )
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
    container.register_port("event_bus", events)
    container.register_port("settings_service", settings)
    container.register_port("license_service", license_service)
    container.register_port("license_guard", license_guard)
    container.register_port("app_home", app_home)
    container.register_port("resource_root", resources)
    return container

