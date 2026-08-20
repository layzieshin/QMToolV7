"""Live PostgreSQL repository tests for AP-028 M4."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

from modules.usermanagement import postgres_schema as pgs
from modules.usermanagement.contracts import AuthenticatedUser, SessionRecord
from modules.usermanagement.password_crypto import is_password_hash, verify_password
from modules.usermanagement.postgres_connection import PostgresRepositoryError
from modules.usermanagement.postgres_session_repository import PostgresSessionRepository
from modules.usermanagement.postgres_user_repository import PostgresUserRepository
from modules.usermanagement.module import register_usermanagement_ports
from modules.usermanagement.service import UserManagementService
from qm_platform.runtime.container import RuntimeContainer

from tests.postgres_live_support import LivePostgresEnv

pytestmark = pytest.mark.postgres


def _utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def repositories(
    live_postgres_env: LivePostgresEnv,
) -> tuple[str, str, str, PostgresUserRepository, PostgresSessionRepository]:
    admin_dsn = live_postgres_env.admin_dsn
    migrator_dsn = live_postgres_env.migrator_dsn
    runtime_dsn = live_postgres_env.runtime_dsn
    pgs.migrate_usermanagement_schema(migrator_dsn)
    user_repository = PostgresUserRepository(runtime_dsn)
    session_repository = PostgresSessionRepository(runtime_dsn)
    yield admin_dsn, migrator_dsn, runtime_dsn, user_repository, session_repository


def _new_user(repository: PostgresUserRepository, username: str = "alice") -> AuthenticatedUser:
    return repository.create_user(
        username,
        "initial-password",
        "User",
        first_name="Alice",
        last_name="Example",
        email="alice@example.invalid",
    )


def _new_session(user: AuthenticatedUser, token_hash: str = "hash-1") -> SessionRecord:
    moment = _utc()
    return SessionRecord(
        session_id=str(uuid.uuid4()),
        token_hash=token_hash,
        user_id=user.user_id,
        created_at=moment,
        last_seen_at=moment,
        expires_at=moment + timedelta(hours=1),
        client_type="test",
    )


def test_user_repository_maps_crud_and_hashes_passwords(repositories) -> None:
    _admin_dsn, _migrator_dsn, _runtime_dsn, repository, _sessions = repositories
    created = _new_user(repository)

    assert uuid.UUID(created.user_id)
    assert created.display_name == "Alice, Example"
    record = repository.get_by_username("ALICE")
    assert record is not None
    assert record[0] == created.user_id
    assert is_password_hash(record[1])
    assert verify_password(record[1], "initial-password")
    assert repository.get_user("alice") == created

    updated_profile = repository.update_user_profile(
        "alice",
        first_name="Alicia",
        last_name="Example",
        email="alicia@example.invalid",
    )
    assert updated_profile.display_name == "Alicia, Example"
    updated_admin = repository.update_user_admin_fields(
        "alice",
        department="QA",
        scope="global",
        organization_unit="HQ",
        role="QMB",
        is_active=True,
        is_qmb=True,
    )
    assert updated_admin.role == "QMB"
    assert updated_admin.is_qmb is True
    assert updated_admin.department == "QA"

    repository.change_password("alice", "new-password")
    changed = repository.get_by_username("alice")
    assert changed is not None
    assert verify_password(changed[1], "new-password")
    assert repository.list_users()[0].username == "alice"


def test_user_repository_maps_conflicts_and_seed_operations(repositories) -> None:
    _admin_dsn, _migrator_dsn, _runtime_dsn, repository, _sessions = repositories
    _new_user(repository)
    with pytest.raises(ValueError, match="user already exists"):
        repository.create_user("ALICE", "other", "User")
    with pytest.raises(KeyError, match="unknown user"):
        repository.change_password("missing", "new-password")

    repository.ensure_seed_users([("seed", "seed-password", "User")])
    repository.ensure_seed_users([("seed", "different", "User")])
    seed = repository.get_by_username("seed")
    assert seed is not None and verify_password(seed[1], "seed-password")

    repository.ensure_initial_admin("admin", "admin-password")
    repository.ensure_initial_admin("admin", "different-password")
    admin = repository.get_user("admin")
    assert admin is not None and admin.must_change_password is True


def test_repository_rejects_non_runtime_connections(repositories) -> None:
    _admin_dsn, migrator_dsn, _runtime_dsn, _repository, _sessions = repositories
    with pytest.raises(PostgresRepositoryError, match="qmtool_runtime"):
        PostgresUserRepository(migrator_dsn).list_users()


def test_session_repository_lifecycle_and_hash_only(repositories) -> None:
    _admin_dsn, _migrator_dsn, _runtime_dsn, users, sessions = repositories
    user = _new_user(users)
    record = _new_session(user, "opaque-hash")
    sessions.add(record)

    loaded = sessions.get_by_token_hash("opaque-hash")
    assert loaded == record
    assert sessions.get_by_session_id(record.session_id) == record
    assert sessions.list_for_user(user.user_id) == [record]

    touched = sessions.touch(record.session_id, record.last_seen_at + timedelta(minutes=1))
    assert touched is not None
    assert touched.last_seen_at > record.last_seen_at
    revoked = sessions.revoke(record.session_id, touched.last_seen_at + timedelta(minutes=1))
    assert revoked is not None and revoked.revoked_at is not None
    assert sessions.touch(record.session_id, revoked.last_seen_at + timedelta(minutes=1)) == revoked

    with psycopg.connect(_runtime_dsn) as runtime:
        row = runtime.execute(
            "SELECT token_hash FROM usermanagement.sessions WHERE session_id = %s::uuid",
            (record.session_id,),
        ).fetchone()
    assert row is not None and row[0] == "opaque-hash"


def test_session_repository_fk_and_revoke_all(repositories) -> None:
    _admin_dsn, _migrator_dsn, _runtime_dsn, _users, sessions = repositories
    missing_user = str(uuid.uuid4())
    with pytest.raises(ValueError, match="session user does not exist"):
        sessions.add(
            SessionRecord(
                session_id=str(uuid.uuid4()),
                token_hash="missing-user-hash",
                user_id=missing_user,
                created_at=_utc(),
                last_seen_at=_utc(),
                expires_at=_utc() + timedelta(hours=1),
                client_type="test",
            )
        )

    user = _new_user(_users)
    first = _new_session(user, "revoke-all-1")
    second = _new_session(user, "revoke-all-2")
    sessions.add(first)
    sessions.add(second)
    revoked = sessions.revoke_all_for_user(user.user_id, _utc())
    assert {session.session_id for session in revoked} == {first.session_id, second.session_id}
    assert all(session.revoked_at is not None for session in sessions.list_for_user(user.user_id))


def test_opaque_session_ops_use_postgres_repositories(repositories) -> None:
    _admin_dsn, _migrator_dsn, _runtime_dsn, users, sessions = repositories
    user = _new_user(users)
    service = UserManagementService(
        repository=users,
        session_repository=sessions,
        session_file=None,
    )
    issued = service.create_session(user, client_type="backend", now=_utc())
    context = service.resolve_session(
        issued.raw_token,
        request_id="request-1",
        now=_utc() + timedelta(minutes=1),
    )
    assert context.is_confirmed is True
    assert context.user_id == user.user_id
    assert context.global_roles == frozenset({"USER"})
    assert service.revoke_session(raw_token=issued.raw_token, now=_utc()) is not None


def test_module_composition_uses_postgres_only_when_dsn_port_is_explicit(
    repositories
) -> None:
    _admin_dsn, _migrator_dsn, runtime_dsn, _users, _sessions = repositories

    class _Settings:
        def get_module_settings(self, _module_id):
            return {"seed_mode": "hardened", "dev_mode": False}

    container = RuntimeContainer()
    container.register_port("app_home", Path.cwd())
    container.register_port("settings_service", _Settings())
    container.register_port("event_bus", object())
    container.register_port("usermanagement_postgres_dsn", runtime_dsn)

    register_usermanagement_ports(container)
    service = container.get_port("usermanagement_service")

    assert isinstance(service.repository, PostgresUserRepository)
    assert isinstance(service.session_repository, PostgresSessionRepository)
    assert service.session_file is None


def test_touch_and_revoke_race_never_resurrects_session(repositories) -> None:
    _admin_dsn, _migrator_dsn, _runtime_dsn, users, sessions = repositories
    user = _new_user(users)
    record = _new_session(user, "race-hash")
    sessions.add(record)
    touch_repo = PostgresSessionRepository(_runtime_dsn)
    revoke_repo = PostgresSessionRepository(_runtime_dsn)

    with ThreadPoolExecutor(max_workers=2) as executor:
        touched = executor.submit(
            touch_repo.touch,
            record.session_id,
            record.last_seen_at + timedelta(minutes=1),
        )
        revoked = executor.submit(
            revoke_repo.revoke,
            record.session_id,
            record.last_seen_at + timedelta(minutes=2),
        )
        touched.result()
        revoked.result()

    final = sessions.get_by_session_id(record.session_id)
    assert final is not None and final.revoked_at is not None
