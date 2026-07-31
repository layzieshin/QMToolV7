from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from modules.incident_management.module import create_incident_management_module_contract
from qm_platform.events.event_bus import EventBus
from qm_platform.licensing.keyring import PublicKeyring
from qm_platform.licensing.license_guard import LicenseGuard
from qm_platform.licensing.license_policy import LicensePolicy
from qm_platform.licensing.license_service import LicenseService, ModuleNotLicensedError
from qm_platform.licensing.license_verifier import LicenseVerifier
from qm_platform.licensing.licensed_proxy import LicensedPortProxy
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore
from tests.modules.incident_management_test_support import (
    _FakeUser,
    _FakeUserManagement,
    _install_fake_usermanagement,
    switch_incident_user,
)
from tests.platform.test_license_service import TEST_MACHINE, _build_signed_payload


class _IncidentStub:
    def ping(self) -> str:
        return "ok"


def _license_stack(
    private_key: Ed25519PrivateKey,
    *,
    license_file: Path | None = None,
    enabled_modules: list[str] | None = None,
) -> tuple[LicenseService, LicenseGuard]:
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    keyring = PublicKeyring()
    keyring.add_key("test-key", public_pem.decode("utf-8"))
    service = LicenseService(
        license_file=license_file or Path("missing.json"),
        verifier=LicenseVerifier(keyring),
        policy=LicensePolicy(local_machine_id=TEST_MACHINE),
    )
    if enabled_modules is not None and license_file is None:
        payload = _build_signed_payload(private_key, enabled_modules=enabled_modules)
        service = LicenseService(
            license_file=Path("unused.json"),
            verifier=LicenseVerifier(keyring),
            policy=LicensePolicy(local_machine_id=TEST_MACHINE),
            _payload=payload,
        )
    return service, LicenseGuard(service)


def _build_licensed_incident_container(
    license_service: LicenseService,
    license_guard: LicenseGuard,
    *,
    strict_start: bool = True,
) -> tuple[RuntimeContainer, LifecycleManager]:
    root = Path(tempfile.mkdtemp())
    container = RuntimeContainer()
    container.register_port("logger", LoggerService(root / "logs.jsonl"))
    container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
    container.register_port("event_bus", EventBus())
    container.register_port(
        "settings_service",
        SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json")),
    )
    container.register_port("license_service", license_service)
    container.register_port("license_guard", license_guard)
    container.register_port("app_home", root)
    container.register_port("resource_root", root)
    container.register_port("usermanagement_service", _FakeUserManagement(_FakeUser("u1", "User")))
    lifecycle = LifecycleManager(container)
    lifecycle.prepare(create_incident_management_module_contract())
    runtime_bootstrap.activate_core_modules(container, lifecycle)
    lifecycle.start(strict=strict_start)
    if container.has_port("incident_management_api"):
        _install_fake_usermanagement(container, _FakeUser("u1", "User"))
    return container, lifecycle


class IncidentManagementLicenseEnforcementTest(unittest.TestCase):
    def test_proxy_blocks_without_license(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        _, guard = _license_stack(private_key)
        proxy = LicensedPortProxy(_IncidentStub(), guard, "incident_management")
        with self.assertRaises(ModuleNotLicensedError):
            proxy.ping()

    def test_proxy_allows_with_valid_license(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        payload = _build_signed_payload(
            private_key,
            enabled_modules=["incident_management"],
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        keyring = PublicKeyring()
        keyring.add_key("test-key", public_pem.decode("utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            license_file = Path(tmp) / "license.json"
            license_file.write_text(json.dumps(payload), encoding="utf-8")
            service = LicenseService(
                license_file=license_file,
                verifier=LicenseVerifier(keyring),
                policy=LicensePolicy(local_machine_id=TEST_MACHINE),
            )
            guard = LicenseGuard(service)
            proxy = LicensedPortProxy(_IncidentStub(), guard, "incident_management")
            self.assertEqual(proxy.ping(), "ok")

    def test_module_start_blocked_without_license(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        license_service, license_guard = _license_stack(
            private_key,
            enabled_modules=["training"],
        )
        container, lifecycle = _build_licensed_incident_container(
            license_service,
            license_guard,
            strict_start=False,
        )
        self.assertIn("incident_management", lifecycle.failed_modules())
        self.assertFalse(container.has_port("incident_management_service"))
        if container.has_port("incident_management_api"):
            api = container.get_port("incident_management_api")
            switch_incident_user(container, _FakeUser("u1", "User"))
            with self.assertRaises(ModuleNotLicensedError):
                api.list_my_incidents()

    def test_container_api_allowed_with_license(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        license_service, license_guard = _license_stack(
            private_key,
            enabled_modules=["incident_management"],
        )
        container, _lifecycle = _build_licensed_incident_container(license_service, license_guard)
        self.assertTrue(container.has_port("incident_management_api"))
        self.assertFalse(container.has_port("incident_management_service"))
        switch_incident_user(container, _FakeUser("u1", "User"))
        api = container.get_port("incident_management_api")
        self.assertEqual(api.list_my_incidents(), [])


if __name__ == "__main__":
    unittest.main()
