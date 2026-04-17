from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.usermanagement.service import UserManagementService
from modules.usermanagement.sqlite_repository import SQLiteUserRepository


class UserManagementSelfRegisterTest(unittest.TestCase):
    def test_self_register_creates_inactive_plain_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SQLiteUserRepository(
                db_path=Path(tmp) / "users.db",
                schema_path=Path("modules/usermanagement/schema.sql"),
            )
            service = UserManagementService(repository=repo)
            created = service.self_register(
                "new_user",
                "secret",
                first_name="New",
                last_name="User",
                email="new@example.org",
            )
            self.assertEqual("User", created.role)
            self.assertFalse(created.is_active)
            self.assertFalse(created.is_qmb)
            self.assertIsNone(service.authenticate("new_user", "secret"))


if __name__ == "__main__":
    unittest.main()

