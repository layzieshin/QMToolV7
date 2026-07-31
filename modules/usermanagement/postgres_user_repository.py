"""PostgreSQL UserRepository implementation for AP-028 M4."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from .contracts import AuthenticatedUser
from .password_crypto import hash_password
from .postgres_connection import runtime_connection
from .repository import UserRepository


_USER_COLUMNS = """
    user_id::text AS user_id,
    username,
    password_hash,
    role,
    first_name,
    last_name,
    display_name,
    email,
    department,
    scope,
    organization_unit,
    is_active,
    deactivated_at,
    is_qmb,
    must_change_password,
    created_at,
    updated_at
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _user_from_row(row: dict[str, object]) -> AuthenticatedUser:
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
        is_active=bool(row["is_active"]),
        is_qmb=bool(row["is_qmb"]),
        must_change_password=bool(row["must_change_password"]),
    )


def _display_values(
    first_name: str | None,
    last_name: str | None,
    display_name: str | None,
) -> tuple[str | None, str | None, str | None]:
    resolved_first = (first_name or "").strip() or None
    resolved_last = (last_name or "").strip() or None
    if resolved_first is None and resolved_last is None and display_name:
        parts = [part.strip() for part in display_name.split(",", 1)]
        resolved_first = parts[0] or None
        resolved_last = parts[1] if len(parts) > 1 and parts[1] else None
    name_parts = [part for part in (resolved_first, resolved_last) if part is not None]
    resolved_display = ", ".join(name_parts) if name_parts else None
    return resolved_first, resolved_last, resolved_display


class PostgresUserRepository(UserRepository):
    """User persistence through the M3 runtime privilege contract."""

    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)

    def get_by_username(self, username: str) -> tuple[str, str, str] | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                f"""
                SELECT user_id::text AS user_id, password_hash, role
                FROM usermanagement.users
                WHERE lower(username) = lower(%s)
                """,
                (username,),
            ).fetchone()
        if row is None:
            return None
        return str(row["user_id"]), str(row["password_hash"]), str(row["role"])

    def get_user(self, username: str) -> AuthenticatedUser | None:
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                f"""
                SELECT {_USER_COLUMNS}
                FROM usermanagement.users
                WHERE lower(username) = lower(%s)
                """,
                (username,),
            ).fetchone()
        return None if row is None else _user_from_row(row)

    def list_users(self) -> list[AuthenticatedUser]:
        with runtime_connection(self._dsn) as conn:
            rows = conn.execute(
                f"""
                SELECT {_USER_COLUMNS}
                FROM usermanagement.users
                ORDER BY lower(username), user_id
                """
            ).fetchall()
        return [_user_from_row(row) for row in rows]

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
        resolved_first, resolved_last, resolved_display = _display_values(
            first_name, last_name, None
        )
        resolved_first = resolved_first or username
        resolved_display = resolved_display or username
        now = _utc_now()
        try:
            with runtime_connection(self._dsn) as conn:
                row = conn.execute(
                    f"""
                    INSERT INTO usermanagement.users (
                        user_id, username, password_hash, role, first_name, last_name,
                        display_name, email, is_active, deactivated_at, is_qmb,
                        must_change_password, created_at, updated_at
                    )
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s)
                    RETURNING {_USER_COLUMNS}
                    """,
                    (
                        str(uuid4()),
                        username,
                        hash_password(password),
                        role,
                        resolved_first,
                        resolved_last,
                        resolved_display,
                        (email or "").strip() or None,
                        bool(is_active),
                        bool(is_qmb),
                        bool(must_change_password),
                        now,
                        now,
                    ),
                ).fetchone()
        except UniqueViolation as exc:
            raise ValueError("user already exists") from exc
        except (CheckViolation, ForeignKeyViolation) as exc:
            raise ValueError("user violates PostgreSQL constraints") from exc
        if row is None:
            raise RuntimeError("PostgreSQL user insert returned no row")
        return _user_from_row(row)

    def change_password(self, username: str, new_password: str) -> None:
        try:
            with runtime_connection(self._dsn) as conn:
                row = conn.execute(
                    """
                    UPDATE usermanagement.users
                    SET password_hash = %s, must_change_password = false, updated_at = %s
                    WHERE lower(username) = lower(%s)
                    RETURNING user_id
                    """,
                    (hash_password(new_password), _utc_now(), username),
                ).fetchone()
        except (CheckViolation, ForeignKeyViolation) as exc:
            raise ValueError("user violates PostgreSQL constraints") from exc
        if row is None:
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
        resolved_first, resolved_last, resolved_display = _display_values(
            first_name, last_name, display_name
        )
        with runtime_connection(self._dsn) as conn:
            row = conn.execute(
                f"""
                UPDATE usermanagement.users
                SET first_name = %s, last_name = %s, display_name = %s,
                    email = %s, updated_at = %s
                WHERE lower(username) = lower(%s)
                RETURNING {_USER_COLUMNS}
                """,
                (
                    resolved_first,
                    resolved_last,
                    resolved_display,
                    (email or "").strip() or None,
                    _utc_now(),
                    username,
                ),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown user: {username}")
        return _user_from_row(row)

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
        with runtime_connection(self._dsn) as conn:
            current = conn.execute(
                f"""
                SELECT {_USER_COLUMNS}
                FROM usermanagement.users
                WHERE lower(username) = lower(%s)
                FOR UPDATE
                """,
                (username,),
            ).fetchone()
            if current is None:
                raise KeyError(f"unknown user: {username}")
            next_active = bool(current["is_active"] if is_active is None else is_active)
            row = conn.execute(
                f"""
                UPDATE usermanagement.users
                SET department = %s,
                    scope = %s,
                    organization_unit = %s,
                    role = %s,
                    is_active = %s,
                    deactivated_at = CASE WHEN %s THEN NULL ELSE deactivated_at END,
                    is_qmb = %s,
                    updated_at = %s
                WHERE user_id = %s::uuid
                RETURNING {_USER_COLUMNS}
                """,
                (
                    department if department is not None else current["department"],
                    scope if scope is not None else current["scope"],
                    organization_unit
                    if organization_unit is not None
                    else current["organization_unit"],
                    role if role is not None else current["role"],
                    next_active,
                    next_active,
                    bool(current["is_qmb"] if is_qmb is None else is_qmb),
                    _utc_now(),
                    current["user_id"],
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("PostgreSQL user update returned no row")
        return _user_from_row(row)

    def ensure_seed_users(self, users: list[tuple[str, str, str]]) -> None:
        with runtime_connection(self._dsn) as conn:
            for username, password, role in users:
                now = _utc_now()
                first_name, _last_name, display_name = _display_values(
                    username, None, None
                )
                first_name = first_name or username
                display_name = display_name or username
                try:
                    conn.execute(
                        """
                        INSERT INTO usermanagement.users (
                            user_id, username, password_hash, role, first_name,
                            display_name, is_active, is_qmb, must_change_password,
                            created_at, updated_at
                        )
                        VALUES (%s::uuid, %s, %s, %s, %s, %s, true, false, false, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            str(uuid4()),
                            username,
                            hash_password(password),
                            role,
                            first_name,
                            display_name,
                            now,
                            now,
                        ),
                    )
                except (CheckViolation, ForeignKeyViolation) as exc:
                    raise ValueError("seed user violates PostgreSQL constraints") from exc

    def ensure_initial_admin(
        self,
        username: str,
        password: str,
        *,
        role: str = "Admin",
        must_change_password: bool = True,
    ) -> None:
        if self.get_user(username) is not None:
            return
        self.create_user(
            username,
            password,
            role,
            is_active=True,
            is_qmb=False,
            must_change_password=must_change_password,
        )
