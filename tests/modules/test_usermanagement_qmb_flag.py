from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.usermanagement.role_policies import is_effective_qmb
from modules.usermanagement.service import UserManagementService
from modules.usermanagement.sqlite_repository import SQLiteUserRepository


class UserManagementQmbFlagTest(unittest.TestCase):
    def test_set_user_qmb_updates_effective_qmb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = SQLiteUserRepository(
                db_path=Path(tmp) / "users.db",
                schema_path=Path("modules/usermanagement/schema.sql"),
            )
            service = UserManagementService(repository=repo)
            service.create_user("alpha", "pw", "User")
            before = next(u for u in service.list_users() if u.username == "alpha")
            self.assertFalse(is_effective_qmb(before))
            updated = service.set_user_qmb("alpha", True)
            self.assertTrue(updated.is_qmb)
            after = next(u for u in service.list_users() if u.username == "alpha")
            self.assertTrue(is_effective_qmb(after))


if __name__ == "__main__":
    unittest.main()

