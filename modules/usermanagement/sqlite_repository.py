from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .contracts import AuthenticatedUser
from .password_crypto import hash_password
from .repository import UserRepository


def _row_must_change(row: sqlite3.Row) -> bool:
    try:
        return bool(int(row["must_change_password"]))
    except (KeyError, IndexError, TypeError, ValueError):
        return False


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
                    first_name,
                    last_name,
                    display_name,
                    email,
                    department,
                    scope,
                    organization_unit,
                    is_active,
                    is_qmb,
                    must_change_password
                FROM users
                ORDER BY username ASC
                """
            ).fetchall()
        return [
            AuthenticatedUser(
                user_id=str(row["user_id"]),
                username=str(row["username"]),
                role=str(row["role"]),
                first_name=row["first_name"],
                last_name=row["last_name"],
                display_name=row["display_name"],
                email=row["email"],
                department=row["department"],
                scope=row["scope"],
                organization_unit=row["organization_unit"],
                is_active=bool(int(row["is_active"])),
                is_qmb=bool(int(row["is_qmb"])),
                must_change_password=_row_must_change(row),
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
                    first_name,
                    last_name,
                    display_name,
                    email,
                    department,
                    scope,
                    organization_unit,
                    is_active,
                    is_qmb,
                    must_change_password
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
            first_name=row["first_name"],
            last_name=row["last_name"],
            display_name=row["display_name"],
            email=row["email"],
            department=row["department"],
            scope=row["scope"],
            organization_unit=row["organization_unit"],
            is_active=bool(int(row["is_active"])),
            is_qmb=bool(int(row["is_qmb"])),
            must_change_password=_row_must_change(row),
        )

    def create_user(
        self,
        username: str,
        password: str,
        role: str,
        *,
        is_active: bool = True,
        is_qmb: bool = False,
        must_change_password: bool = False,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> AuthenticatedUser:
        now = datetime.now(timezone.utc).isoformat()
        resolved_first = (first_name or "").strip() or username
        resolved_last = (last_name or "").strip() or None
        name_parts = [part for part in (resolved_first, resolved_last) if part is not None]
        resolved_display = ", ".join(name_parts) if name_parts else username
        user = AuthenticatedUser(
            user_id=username,
            username=username,
            role=role,
            first_name=resolved_first,
            last_name=resolved_last,
            display_name=resolved_display,
            email=(email or "").strip() or None,
            is_active=bool(is_active),
            is_qmb=bool(is_qmb),
            must_change_password=bool(must_change_password),
        )
        password_hash = hash_password(password)
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO users (
                        user_id, username, password, role, first_name, last_name, display_name, email, department, scope, organization_unit, is_active, is_qmb, must_change_password, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user.user_id,
                        username,
                        password_hash,
                        role,
                        user.first_name,
                        user.last_name,
                        user.display_name,
                        user.email,
                        None,
                        None,
                        None,
                        int(user.is_active),
                        int(user.is_qmb),
                        int(user.must_change_password),
                        now,
                        now,
                    ),
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
                SET password = ?, updated_at = ?, must_change_password = 0
                WHERE username = ?
                """,
                (password_hash, datetime.now(timezone.utc).isoformat(), username),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise KeyError(f"unknown user: {username}")

    def update_user_profile(
        self,
        username: str,
        *,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
        display_name: str | None = None,
    ) -> AuthenticatedUser:
        resolved_first = (first_name or "").strip() or None
        resolved_last = (last_name or "").strip() or None
        if resolved_first is None and resolved_last is None and display_name:
            resolved_first, resolved_last = self._split_display_name(display_name)
        name_parts = [part for part in (resolved_first, resolved_last) if part is not None]
        resolved_display = ", ".join(name_parts) if name_parts else None
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET first_name = ?, last_name = ?, display_name = ?, email = ?, updated_at = ?
                WHERE username = ?
                """,
                (resolved_first, resolved_last, resolved_display, email, datetime.now(timezone.utc).isoformat(), username),
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
        is_qmb: bool | None,
    ) -> AuthenticatedUser:
        current = self.get_user(username)
        if current is None:
            raise KeyError(f"unknown user: {username}")
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE users
                SET department = ?, scope = ?, organization_unit = ?, role = ?, is_active = ?, is_qmb = ?, updated_at = ?
                WHERE username = ?
                """,
                (
                    department if department is not None else current.department,
                    scope if scope is not None else current.scope,
                    organization_unit if organization_unit is not None else current.organization_unit,
                    role if role is not None else current.role,
                    int(bool(is_active if is_active is not None else current.is_active)),
                    int(bool(is_qmb if is_qmb is not None else current.is_qmb)),
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
                        user_id, username, password, role, first_name, last_name, display_name, email, department, scope, organization_unit, is_active, is_qmb, must_change_password, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (username, username, password_hash, role, username, None, username, None, None, None, None, 1, 0, 0, now, now),
                )
            conn.commit()

    def ensure_initial_admin(
        self,
        username: str,
        password: str,
        *,
        role: str = "Admin",
        must_change_password: bool = True,
    ) -> None:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        with self._connect() as conn:
            existing = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                return
            now = datetime.now(timezone.utc).isoformat()
            password_hash = hash_password(password)
            conn.execute(
                """
                INSERT INTO users (
                    user_id, username, password, role, first_name, last_name, display_name, email, department, scope, organization_unit, is_active, is_qmb, must_change_password, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    username,
                    password_hash,
                    role,
                    username,
                    None,
                    username,
                    None,
                    None,
                    None,
                    None,
                    1,
                    0,
                    int(bool(must_change_password)),
                    now,
                    now,
                ),
            )
            conn.commit()

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            for statement in (
                "ALTER TABLE users ADD COLUMN display_name TEXT",
                "ALTER TABLE users ADD COLUMN first_name TEXT",
                "ALTER TABLE users ADD COLUMN last_name TEXT",
                "ALTER TABLE users ADD COLUMN email TEXT",
                "ALTER TABLE users ADD COLUMN department TEXT",
                "ALTER TABLE users ADD COLUMN scope TEXT",
                "ALTER TABLE users ADD COLUMN organization_unit TEXT",
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
                "ALTER TABLE users ADD COLUMN is_qmb INTEGER NOT NULL DEFAULT 0",
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0",
            ):
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError:
                    pass
            conn.execute("UPDATE users SET user_id = username WHERE user_id IS NULL OR user_id = ''")
            conn.execute("UPDATE users SET display_name = username WHERE display_name IS NULL OR display_name = ''")
            rows = conn.execute("SELECT username, display_name, first_name, last_name FROM users").fetchall()
            for row in rows:
                first = row["first_name"]
                last = row["last_name"]
                if (first and str(first).strip()) or (last and str(last).strip()):
                    continue
                f_name, l_name = self._split_display_name(str(row["display_name"] or row["username"]))
                conn.execute(
                    "UPDATE users SET first_name = ?, last_name = ?, display_name = ? WHERE username = ?",
                    (
                        f_name,
                        l_name,
                        ", ".join([part for part in (f_name, l_name) if part is not None]) or row["username"],
                        row["username"],
                    ),
                )
            conn.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
            conn.execute("UPDATE users SET is_qmb = 0 WHERE is_qmb IS NULL")
            conn.execute("UPDATE users SET must_change_password = 0 WHERE must_change_password IS NULL")
            conn.commit()

    @staticmethod
    def _split_display_name(value: str) -> tuple[str | None, str | None]:
        raw = (value or "").strip()
        if not raw:
            return (None, None)
        if "," in raw:
            first, last = [part.strip() for part in raw.split(",", 1)]
            return (first or None, last or None)
        parts = raw.split()
        if len(parts) == 1:
            return (parts[0], None)
        return (parts[0], " ".join(parts[1:]) or None)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
