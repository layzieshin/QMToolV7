from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.usermanagement.sqlite_repository import SQLiteUserRepository


class MustChangePasswordTest(unittest.TestCase):
    def test_change_password_clears_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "users.db"
            schema = Path(__file__).resolve().parents[3] / "modules" / "usermanagement" / "schema.sql"
            repo = SQLiteUserRepository(db_path=db, schema_path=schema)
            repo.ensure_initial_admin("admin", "admin", role="Admin", must_change_password=True)
            u = repo.get_user("admin")
            assert u is not None
            self.assertTrue(u.must_change_password)
            repo.change_password("admin", "new-strong-password")
            u2 = repo.get_user("admin")
            assert u2 is not None
            self.assertFalse(u2.must_change_password)


if __name__ == "__main__":
    unittest.main()
