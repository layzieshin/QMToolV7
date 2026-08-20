from __future__ import annotations

from qm_platform.settings.testing import build_settings_service_for_tests
import tempfile
import unittest
from pathlib import Path

from modules.documents.module import create_documents_module_contract
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService


class _LicenseAllowAll:
    def is_module_allowed(self, _: str) -> bool:
        return True


class DocumentsModulePortsTest(unittest.TestCase):
    def test_documents_registers_pool_and_workflow_ports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            container = RuntimeContainer()
            container.register_port("logger", LoggerService(root / "logs.jsonl"))
            container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
            container.register_port("event_bus", EventBus())
            container.register_port(
                "settings_service",
                build_settings_service_for_tests(root),
            )
            container.register_port("license_service", _LicenseAllowAll())
            container.register_port("app_home", root)
            container.register_port("signature_api", object())
            container.register_port("registry_projection_api", object())
            # Explicit in-process opt-in (not a free product env var).
            container.register_port("documents_runtime_owner", "backend")

            lifecycle = LifecycleManager(container)
            lifecycle.prepare(create_documents_module_contract())
            runtime_bootstrap.activate_core_modules(container, lifecycle)
            lifecycle.start()

            self.assertTrue(container.has_port("documents_service"))
            self.assertTrue(container.has_port("documents_pool_api"))
            self.assertTrue(container.has_port("documents_artifacts_api"))
            self.assertTrue(container.has_port("documents_workflow_api"))


if __name__ == "__main__":
    unittest.main()

