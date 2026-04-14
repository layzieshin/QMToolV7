from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from modules.usermanagement.password_crypto import is_password_hash
from modules.usermanagement.service import UserManagementService
from modules.usermanagement.sqlite_repository import SQLiteUserRepository


class UserManagementPersistenceTest(unittest.TestCase):
    def test_sqlite_repository_seeds_and_authenticates_users(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SQLiteUserRepository(
                db_path=root / "users.db",
                schema_path=Path("modules/usermanagement/schema.sql"),
            )
            repo.ensure_seed_users([("admin", "admin", "Admin")])
            service = UserManagementService(repository=repo)

            user = service.authenticate("admin", "admin")
            self.assertIsNotNone(user)
            assert user is not None
            self.assertEqual(user.username, "admin")
            self.assertEqual(user.role, "Admin")
            stored = repo.get_by_username("admin")
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertTrue(is_password_hash(stored[1]))

    def test_service_can_create_list_and_change_password_with_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SQLiteUserRepository(
                db_path=root / "users.db",
                schema_path=Path("modules/usermanagement/schema.sql"),
            )
            service = UserManagementService(repository=repo)
            created = service.create_user("alpha", "pw1", "User")
            self.assertEqual(created.username, "alpha")

            listed = service.list_users()
            self.assertTrue(any(row.username == "alpha" and row.role == "User" for row in listed))

            service.change_password("alpha", "pw2")
            self.assertIsNone(service.authenticate("alpha", "pw1"))
            self.assertIsNotNone(service.authenticate("alpha", "pw2"))

    def test_legacy_plaintext_password_is_upgraded_to_hash_after_successful_login(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "users.db"
            repo = SQLiteUserRepository(
                db_path=db_path,
                schema_path=Path("modules/usermanagement/schema.sql"),
            )
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, password, role, created_at, updated_at)
                    VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("legacy", "legacy", "legacy-pw", "User"),
                )
                conn.commit()
            service = UserManagementService(repository=repo)
            self.assertIsNotNone(service.authenticate("legacy", "legacy-pw"))
            upgraded = repo.get_by_username("legacy")
            self.assertIsNotNone(upgraded)
            assert upgraded is not None
            self.assertTrue(is_password_hash(upgraded[1]))


if __name__ == "__main__":
    unittest.main()
