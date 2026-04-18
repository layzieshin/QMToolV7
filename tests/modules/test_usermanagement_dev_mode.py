from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qm_platform.runtime.container import RuntimeContainer

from modules.usermanagement.module import register_usermanagement_ports


class _SettingsServiceStub:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def get_module_settings(self, module_id: str) -> dict[str, object]:
        if module_id != "usermanagement":
            return {}
        return dict(self._payload)


class _EventBusStub:
    def publish(self, _: object) -> None:
        return None


class UserManagementDevModeTest(unittest.TestCase):
    def test_admin_only_seeds_initial_admin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            container = RuntimeContainer()
            container.register_port("app_home", Path(tmp))
            container.register_port(
                "settings_service",
                _SettingsServiceStub(
                    {
                        "users_db_path": "storage/platform/users.db",
                        "seed_mode": "admin_only",
                        "dev_mode": False,
                    }
                ),
            )
            container.register_port("event_bus", _EventBusStub())
            register_usermanagement_ports(container)
            service = container.get_port("usermanagement_service")
            self.assertIsNotNone(service.authenticate("admin", "admin"))

    def test_legacy_defaults_with_dev_mode_seeds_initial_admin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            container = RuntimeContainer()
            container.register_port("app_home", Path(tmp))
            container.register_port(
                "settings_service",
                _SettingsServiceStub(
                    {
                        "users_db_path": "storage/platform/users.db",
                        "seed_mode": "legacy_defaults",
                        "dev_mode": True,
                    }
                ),
            )
            container.register_port("event_bus", _EventBusStub())
            register_usermanagement_ports(container)
            service = container.get_port("usermanagement_service")
            self.assertIsNotNone(service.authenticate("admin", "admin"))
            users = {u.username for u in service.list_users()}
            self.assertEqual(users, {"admin"})

    def test_legacy_defaults_without_dev_mode_disables_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            container = RuntimeContainer()
            container.register_port("app_home", Path(tmp))
            container.register_port(
                "settings_service",
                _SettingsServiceStub(
                    {
                        "users_db_path": "storage/platform/users.db",
                        "seed_mode": "legacy_defaults",
                        "dev_mode": False,
                    }
                ),
            )
            container.register_port("event_bus", _EventBusStub())
            register_usermanagement_ports(container)
            service = container.get_port("usermanagement_service")
            self.assertIsNone(service.authenticate("admin", "admin"))


if __name__ == "__main__":
    unittest.main()
