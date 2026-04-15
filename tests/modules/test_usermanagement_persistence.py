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

    def test_update_user_profile_persists_first_and_last_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = SQLiteUserRepository(
                db_path=root / "users.db",
                schema_path=Path("modules/usermanagement/schema.sql"),
            )
            service = UserManagementService(repository=repo)
            service.create_user("anna", "pw1", "User")

            updated = service.update_user_profile(
                "anna",
                first_name="Anna",
                last_name="Muster",
                email="anna@example.org",
            )

            self.assertEqual("Anna", updated.first_name)
            self.assertEqual("Muster", updated.last_name)
            self.assertEqual("Anna, Muster", updated.display_name)
            self.assertEqual("anna@example.org", updated.email)

            loaded = repo.get_user("anna")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual("Anna", loaded.first_name)
            self.assertEqual("Muster", loaded.last_name)

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

    def test_legacy_display_name_formats_are_backfilled_to_first_last_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "users.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password TEXT NOT NULL,
                        role TEXT NOT NULL,
                        display_name TEXT,
                        email TEXT,
                        department TEXT,
                        scope TEXT,
                        organization_unit TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, password, role, display_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("u1", "anna", "pw", "User", "Anna, Muster"),
                )
                conn.execute(
                    """
                    INSERT INTO users (user_id, username, password, role, display_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("u2", "max", "pw", "User", "Max Mustermann"),
                )
                conn.commit()

            repo = SQLiteUserRepository(
                db_path=db_path,
                schema_path=Path("modules/usermanagement/schema.sql"),
            )

            anna = repo.get_user("anna")
            self.assertIsNotNone(anna)
            assert anna is not None
            self.assertEqual("Anna", anna.first_name)
            self.assertEqual("Muster", anna.last_name)

            max_user = repo.get_user("max")
            self.assertIsNotNone(max_user)
            assert max_user is not None
            self.assertEqual("Max", max_user.first_name)
            self.assertEqual("Mustermann", max_user.last_name)


if __name__ == "__main__":
    unittest.main()
