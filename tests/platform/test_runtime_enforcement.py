from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.health import build_health_report
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.sdk.module_contract import ModuleContract, SettingsContribution
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


def _noop(_: object) -> None:
    return None


class _LicenseAllowAll:
    def is_module_allowed(self, _: str) -> bool:
        return True


class _LicenseDenyAll:
    def is_module_allowed(self, _: str) -> bool:
        return False


def _contract(
    module_id: str,
    *,
    register=_noop,
    start=_noop,
    stop=_noop,
    provided_ports: list[str] | None = None,
    settings_contribution: SettingsContribution | None = None,
    license_tag: str | None = None,
) -> ModuleContract:
    return ModuleContract(
        module_id=module_id,
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=[],
        provided_ports=provided_ports or [],
        required_capabilities=[],
        provided_capabilities=[],
        settings_contribution=settings_contribution,
        license_tag=license_tag,
        register=register,
        start=start,
        stop=stop,
    )


class RuntimeEnforcementTest(unittest.TestCase):
    def test_settings_contribution_registered_from_contract(self) -> None:
        container = RuntimeContainer()
        with tempfile.TemporaryDirectory() as tmp:
            container.register_port("settings_service", SettingsService(SettingsRegistry(), SettingsStore(Path(tmp) / "s.json")))
            lifecycle = LifecycleManager(container)
            contribution = SettingsContribution(
                module_id="m_settings",
                schema_version=1,
                schema={"type": "object"},
                defaults={"enabled": True},
                scope="module_global",
                migrations=[],
            )
            lifecycle.register(_contract("m_settings", settings_contribution=contribution))
            svc: SettingsService = container.get_port("settings_service")
            self.assertIsNotNone(svc.registry.get("m_settings"))

    def test_provided_ports_enforced_after_start(self) -> None:
        container = RuntimeContainer()
        lifecycle = LifecycleManager(container)
        lifecycle.register(_contract("m_no_port", provided_ports=["missing_port"]))
        with self.assertRaises(RuntimeError):
            lifecycle.start()

    def test_license_tag_enforced(self) -> None:
        container = RuntimeContainer()
        container.register_port("license_service", _LicenseDenyAll())
        lifecycle = LifecycleManager(container)
        lifecycle.register(_contract("m_licensed", license_tag="m_licensed"))
        with self.assertRaises(RuntimeError):
            lifecycle.start()

    def test_license_tag_allows_start(self) -> None:
        container = RuntimeContainer()
        container.register_port("license_service", _LicenseAllowAll())
        lifecycle = LifecycleManager(container)
        lifecycle.register(_contract("m_licensed", license_tag="m_licensed"))
        lifecycle.start()

    def test_health_report_includes_failed_modules(self) -> None:
        container = RuntimeContainer()
        lifecycle = LifecycleManager(container)
        lifecycle.register(_contract("m_fail", start=lambda _: (_ for _ in ()).throw(RuntimeError("boom"))))
        with self.assertRaises(RuntimeError):
            lifecycle.start()
        report = build_health_report(lifecycle)
        self.assertIn("m_fail", report.failed_modules)


if __name__ == "__main__":
    unittest.main()

