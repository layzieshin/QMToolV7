from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.settings_store import SettingsStore


class SettingsGovernanceEnforcementTest(unittest.TestCase):
    def test_governance_critical_requires_acknowledge_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = SettingsService(SettingsRegistry(), SettingsStore(root / "settings.json"))
            service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)

            with self.assertRaises(ValueError):
                service.set_module_settings("signature", {"require_password": False, "default_mode": "visual"})

            service.set_module_settings(
                "signature",
                {"require_password": False, "default_mode": "visual"},
                acknowledge_governance_change=True,
            )
            persisted = service.get_module_settings("signature")
            self.assertEqual(persisted["require_password"], False)


if __name__ == "__main__":
    unittest.main()
