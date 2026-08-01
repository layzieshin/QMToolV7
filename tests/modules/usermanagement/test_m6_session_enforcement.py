"""AP-028 M6: session enforcement service/repository tests."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from modules.usermanagement.errors import LastActiveAdminError, RevokedSessionError, UserExistsError
from modules.usermanagement.memory_session_repository import InMemorySessionRepository
from modules.usermanagement.service import UserManagementService
from qm_platform.persistence.database_evolution import (
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)
from tests.database_helpers import user_repository


def _service(tmp_path: Path) -> UserManagementService:
    repo = user_repository(tmp_path / "users.db")
    repo.ensure_initial_admin("admin", "adminpass12", role="Admin", must_change_password=False)
    repo.create_user("bob", "bobsecret12", "User", must_change_password=False)
    return UserManagementService(
        repository=repo,
        session_repository=InMemorySessionRepository(),
    )


def test_change_own_password_revokes_other_sessions(tmp_path: Path) -> None:
    service = _service(tmp_path)
    admin = service.authenticate("admin", "adminpass12")
    assert admin is not None
    keep = service.create_session(admin, client_type="a")
    other = service.create_session(admin, client_type="b")
    ctx = service.resolve_session(keep.raw_token, request_id="r1")
    service.change_own_password(ctx, "adminpass99")
    assert service.resolve_session(keep.raw_token, request_id="r2").username == "admin"

    with pytest.raises(RevokedSessionError):
        service.resolve_session(other.raw_token, request_id="r3")


def test_logout_all_revokes_current_session(tmp_path: Path) -> None:
    service = _service(tmp_path)
    bob = service.authenticate("bob", "bobsecret12")
    assert bob is not None
    first = service.create_session(bob, client_type="a")
    second = service.create_session(bob, client_type="b")
    ctx = service.resolve_session(first.raw_token, request_id="r1")
    service.revoke_all_own_sessions(ctx)
    with pytest.raises(RevokedSessionError):
        service.resolve_session(first.raw_token, request_id="r2")
    with pytest.raises(RevokedSessionError):
        service.resolve_session(second.raw_token, request_id="r3")


def test_deactivate_sets_timestamp_and_revokes_sessions(tmp_path: Path) -> None:
    service = _service(tmp_path)
    bob = service.authenticate("bob", "bobsecret12")
    assert bob is not None
    issued = service.create_session(bob, client_type="a")
    updated = service.set_user_active("bob", False)
    assert updated.is_active is False
    with sqlite3.connect(tmp_path / "users.db") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT deactivated_at, is_active FROM users WHERE username = ?", ("bob",)).fetchone()
    assert int(row["is_active"]) == 0
    assert row["deactivated_at"]
    from modules.usermanagement.errors import InactiveUserError

    with pytest.raises((RevokedSessionError, InactiveUserError)):
        service.resolve_session(issued.raw_token, request_id="r")
    reactivated = service.set_user_active("bob", True)
    assert reactivated.is_active is True
    with sqlite3.connect(tmp_path / "users.db") as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT deactivated_at FROM users WHERE username = ?", ("bob",)).fetchone()
    assert row["deactivated_at"] is None
    with pytest.raises(RevokedSessionError):
        service.resolve_session(issued.raw_token, request_id="r2")


def test_role_change_without_revoke_updates_next_resolve(tmp_path: Path) -> None:
    service = _service(tmp_path)
    bob = service.authenticate("bob", "bobsecret12")
    assert bob is not None
    issued = service.create_session(bob, client_type="a")
    before = service.resolve_session(issued.raw_token, request_id="r1")
    assert before.is_qmb is False
    service.update_user_admin_fields(
        "bob",
        department=None,
        scope=None,
        organization_unit=None,
        role=None,
        is_active=None,
        is_qmb=True,
    )
    after = service.resolve_session(issued.raw_token, request_id="r2")
    assert after.is_qmb is True
    assert after.session_id == before.session_id


def test_last_active_admin_cannot_be_demoted_or_deactivated(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(LastActiveAdminError):
        service.set_user_active("admin", False)
    admin = service.authenticate("admin", "adminpass12")
    assert admin is not None
    ctx = service.resolve_session(
        service.create_session(admin, client_type="a").raw_token,
        request_id="r",
    )
    with pytest.raises(LastActiveAdminError):
        service.update_user_access_as_admin(ctx, "admin", role="User")


def test_second_admin_allows_demotion(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_user("admin2", "admin2pass1", "Admin", must_change_password=False)
    admin = service.authenticate("admin", "adminpass12")
    assert admin is not None
    ctx = service.resolve_session(
        service.create_session(admin, client_type="a").raw_token,
        request_id="r",
    )
    updated = service.update_user_access_as_admin(ctx, "admin", role="User")
    assert updated.role == "User"


def test_sqlite_v1_to_v2_migration_preserves_users(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    service = DatabaseEvolutionService(
        app_home=tmp_path,
        backup_root=tmp_path / ".database-backups",
    )
    service.migrate(
        (
            DatabaseSpec(
                database_id="users",
                path=db_path,
                migrations=(
                    MigrationStep(
                        version=1,
                        name="initial",
                        sql_path=Path("modules/usermanagement/migrations/0001_initial.sql").resolve(),
                    ),
                ),
            ),
        ),
        reason="test_v1",
    )
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (
                user_id, username, password, role, is_active, is_qmb,
                must_change_password, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, 0, 0, ?, ?)
            """,
            ("u1", "legacy", "hash", "User", now, now),
        )
        conn.commit()
    service.migrate(
        (
            DatabaseSpec(
                database_id="users",
                path=db_path,
                migrations=(
                    MigrationStep(
                        version=1,
                        name="initial",
                        sql_path=Path("modules/usermanagement/migrations/0001_initial.sql").resolve(),
                    ),
                    MigrationStep(
                        version=2,
                        name="deactivated_at",
                        sql_path=Path(
                            "modules/usermanagement/migrations/0002_deactivated_at.sql"
                        ).resolve(),
                    ),
                ),
            ),
        ),
        reason="test_v2",
    )
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT username, deactivated_at FROM users WHERE username = ?",
            ("legacy",),
        ).fetchone()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    assert row["username"] == "legacy"
    assert row["deactivated_at"] is None
    assert "deactivated_at" in cols


def test_create_user_duplicate_raises(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(UserExistsError):
        service.create_user("bob", "anotherpass", "User")
