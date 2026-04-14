from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .contracts import AuthenticatedUser
from .password_crypto import hash_password
from .repository import UserRepository


class SQLiteUserRepository(UserRepository):
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get_by_username(self, username: str) -> tuple[str, str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, username, password, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        return str(row["user_id"]), str(row["password"]), str(row["role"])

    def list_users(self) -> list[AuthenticatedUser]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    user_id,
                    username,
                    role,
                    display_name,
                    email,
                    department,
                    scope,
                    organization_unit,
                    is_active
                FROM users
                ORDER BY username ASC
                """
            ).fetchall()
        return [
            AuthenticatedUser(
                user_id=str(row["user_id"]),
                username=str(row["username"]),
                role=str(row["role"]),
                display_name=row["display_name"],
                email=row["email"],
                department=row["department"],
                scope=row["scope"],
                organization_unit=row["organization_unit"],
                is_active=bool(int(row["is_active"])),
            )
            for row in rows
        ]

    def get_user(self, username: str) -> AuthenticatedUser | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    user_id,
                    username,
                    role,
                    display_name,
                    email,
                    department,
                    scope,
                    organization_unit,
                    is_active
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if row is None:
            return None
        return AuthenticatedUser(
            user_id=str(row["user_id"]),
            username=str(row["username"]),
            role=str(row["role"]),
            display_name=row["display_name"],
            email=row["email"],
            department=row["department"],
            scope=row["scope"],
            organization_unit=row["organization_unit"],
            is_active=bool(int(row["is_active"])),
        )

    def create_user(self, username: str, password: str, role: str) -> AuthenticatedUser:
        now = datetime.now(timezone.utc).isoformat()
        user = AuthenticatedUser(user_id=username, username=username, role=role)
        password_hash = hash_password(password)
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO users (
                        user_id, username, password, role, display_name, email, department, scope, organization_unit, is_active, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user.user_id, username, password_hash, role, username, None, None, None, None, 1, now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("user already exists") from exc
        return user

    def change_password(self, username: str, new_password: str) -> None:
        password_hash = hash_password(new_password)
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET password = ?, updated_at = ?
                WHERE username = ?
                """,
                (password_hash, datetime.now(timezone.utc).isoformat(), username),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise KeyError(f"unknown user: {username}")

    def update_user_profile(self, username: str, *, display_name: str | None, email: str | None) -> AuthenticatedUser:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET display_name = ?, email = ?, updated_at = ?
                WHERE username = ?
                """,
                (display_name, email, datetime.now(timezone.utc).isoformat(), username),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise KeyError(f"unknown user: {username}")
        user = self.get_user(username)
        if user is None:
            raise KeyError(f"unknown user: {username}")
        return user

    def update_user_admin_fields(
        self,
        username: str,
        *,
        department: str | None,
        scope: str | None,
        organization_unit: str | None,
        role: str | None,
        is_active: bool | None,
    ) -> AuthenticatedUser:
        current = self.get_user(username)
        if current is None:
            raise KeyError(f"unknown user: {username}")
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET department = ?, scope = ?, organization_unit = ?, role = ?, is_active = ?, updated_at = ?
                WHERE username = ?
                """,
                (
                    department if department is not None else current.department,
                    scope if scope is not None else current.scope,
                    organization_unit if organization_unit is not None else current.organization_unit,
                    role if role is not None else current.role,
                    int(is_active if is_active is not None else current.is_active),
                    datetime.now(timezone.utc).isoformat(),
                    username,
                ),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise KeyError(f"unknown user: {username}")
        updated = self.get_user(username)
        if updated is None:
            raise KeyError(f"unknown user: {username}")
        return updated

    def ensure_seed_users(self, users: list[tuple[str, str, str]]) -> None:
        with self._connect() as conn:
            for username, password, role in users:
                existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
                if existing:
                    continue
                now = datetime.now(timezone.utc).isoformat()
                password_hash = hash_password(password)
                conn.execute(
                    """
                    INSERT INTO users (
                        user_id, username, password, role, display_name, email, department, scope, organization_unit, is_active, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (username, username, password_hash, role, username, None, None, None, None, 1, now, now),
                )
            conn.commit()

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            for statement in (
                "ALTER TABLE users ADD COLUMN display_name TEXT",
                "ALTER TABLE users ADD COLUMN email TEXT",
                "ALTER TABLE users ADD COLUMN department TEXT",
                "ALTER TABLE users ADD COLUMN scope TEXT",
                "ALTER TABLE users ADD COLUMN organization_unit TEXT",
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
            ):
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError:
                    pass
            # Migration: keep stable principal IDs aligned with usernames
            # so workflow assignments can use predictable identifiers.
            conn.execute("UPDATE users SET user_id = username WHERE user_id != username")
            conn.execute("UPDATE users SET display_name = username WHERE display_name IS NULL OR display_name = ''")
            conn.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
