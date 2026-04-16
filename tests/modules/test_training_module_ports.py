from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.documents.module import create_documents_module_contract
from modules.registry.module import create_registry_module_contract
from modules.signature.module import create_signature_module_contract
from modules.training.module import create_training_module_contract
from modules.usermanagement.module import create_usermanagement_module_contract
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.runtime.lifecycle import LifecycleManager
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


class _LicenseAllowAll:
    def is_module_allowed(self, _: str) -> bool:
        return True


class TrainingModulePortsTest(unittest.TestCase):
    def test_training_ports_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            container = RuntimeContainer()
            container.register_port("logger", LoggerService(root / "logs.jsonl"))
            container.register_port("audit_logger", AuditLogger(root / "audit.jsonl"))
            container.register_port("event_bus", EventBus())
            container.register_port("settings_service", SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json")))
            container.register_port("license_service", _LicenseAllowAll())
            container.register_port("app_home", root)
            container.register_port("resource_root", root)
            lifecycle = LifecycleManager(container)
            lifecycle.register(create_usermanagement_module_contract())
            lifecycle.register(create_signature_module_contract())
            lifecycle.register(create_registry_module_contract())
            lifecycle.register(create_documents_module_contract())
            lifecycle.register(create_training_module_contract())
            lifecycle.start()
            self.assertTrue(container.has_port("training_api"))
            self.assertTrue(container.has_port("training_admin_api"))


if __name__ == "__main__":
    unittest.main()
