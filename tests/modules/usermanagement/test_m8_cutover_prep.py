"""AP-028 M8 cutover prep tests (no productive cutover)."""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import shutil
import sqlite3
from contextlib import nullcontext
from pathlib import Path

import psycopg
import pytest

from modules.usermanagement import api as um_api
from modules.usermanagement import postgres_schema as pgs
from modules.usermanagement.cutover_drill import (
    DrillSourceExpectation,
    _subprocess_connection,
    database_identity_for_connection,
    run_postgres_backup_restore_drill,
)
from modules.usermanagement.cutover_prep import (
    STATUS_BLOCKED,
    STATUS_INVALID_SOURCE,
    STATUS_READY_FOR_REMAPPING,
    catalog_coverage_gaps,
    prepare_postgres_cutover,
)
from modules.usermanagement.cutover_reference_catalog import MODULE_DATABASES
from modules.usermanagement.password_crypto import hash_password
from qm_platform.persistence.database_evolution import DatabaseEvolutionService
from qm_platform.runtime.container import RuntimeContainer
from tests.database_helpers import prepare_test_database, user_repository
from tests.postgres_destructive_guard import DestructivePostgresGuardError
from tests.postgres_live_support import (
    RESTORE_DB,
    WRONG_RESTORE_DB,
    LivePostgresEnv,
    cleanup_live_environment,
    drop_restore_database,
    os_environ_required,
    prepare_live_environment,
    prepare_restore_database,
)

RESTORE_DB_NAME = RESTORE_DB
WRONG_RESTORE_DB_NAME = WRONG_RESTORE_DB


@pytest.fixture(autouse=True)
def _portable_sqlite_fixture_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    """M8 fixtures test schemas, not AP-027 OS-specific file-lock semantics."""
    monkeypatch.setattr(
        DatabaseEvolutionService,
        "_migration_lock",
        lambda self: nullcontext(),
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hashed_users_db(tmp_path: Path) -> Path:
    users_db = tmp_path / "users.db"
    repo = user_repository(users_db)
    repo.ensure_initial_admin("admin", "adminpass12", role="Admin", must_change_password=False)
    with sqlite3.connect(users_db) as conn:
        conn.execute(
            "UPDATE users SET password = ? WHERE username = 'admin'",
            (hash_password("adminpass12"),),
        )
        conn.commit()
    return users_db


def _empty_cross(tmp_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for module in MODULE_DATABASES:
        db_path = tmp_path / f"{module.database_id}.db"
        prepare_test_database(module.database_id, db_path)
        paths[module.module_id] = db_path
    return paths


def _dsn_with_db(dsn: str, dbname: str) -> str:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    info["dbname"] = dbname
    return psycopg.conninfo.make_conninfo(**info)


def _prepare_or_skip() -> LivePostgresEnv:
    try:
        return prepare_live_environment()
    except DestructivePostgresGuardError as exc:
        if os_environ_required():
            pytest.fail(str(exc))
        pytest.skip(str(exc))


def _drop_restore_db(admin_dsn: str, database_name: str = RESTORE_DB_NAME) -> None:
    drop_restore_database(database_name, admin_dsn=admin_dsn)


def _prepare_restore_db(
    env: LivePostgresEnv,
    database_name: str = RESTORE_DB_NAME,
) -> str:
    return prepare_restore_database(
        database_name,
        migrator_password=env.migrator_password,
        admin_dsn=env.admin_dsn,
    )


def _require_pg_tools() -> None:
    if shutil.which("pg_dump") and shutil.which("pg_restore"):
        return
    if os.environ.get("QMTOOL_PG_REQUIRED", "").strip() == "1":
        pytest.fail("pg_dump/pg_restore required when QMTOOL_PG_REQUIRED=1")
    pytest.skip("pg_dump/pg_restore not available")


def _source_expectation(dsn: str) -> DrillSourceExpectation:
    with psycopg.connect(dsn) as conn:
        pgs._activate_migrator_role(conn)  # noqa: SLF001
        identity = database_identity_for_connection(conn)
        applied = pgs._fetch_applied(conn)  # noqa: SLF001
        fingerprint = pgs._compute_schema_fingerprint(conn)  # noqa: SLF001
    return DrillSourceExpectation(
        identity_digest=identity.identity_digest,
        migration_tip=int(applied[-1].version),
        schema_fingerprint=fingerprint,
    )


def test_catalog_matches_quermodule_migration_schemas() -> None:
    gaps = catalog_coverage_gaps()
    assert gaps["missing_from_catalog"] == []
    assert gaps["missing_from_schema"] == []


def test_api_exports_prepare_postgres_cutover_and_never_cutover_ready() -> None:
    assert "prepare_postgres_cutover" in um_api.__all__
    assert "run_postgres_backup_restore_drill" not in um_api.__all__
    assert "default_cross_module_db_paths" not in um_api.__all__
    assert "CutoverPrepResult" in um_api.__all__
    assert callable(um_api.prepare_postgres_cutover)
    assert "drill_source_dsn" not in inspect.signature(
        um_api.prepare_postgres_cutover
    ).parameters
    text = Path("modules/usermanagement/cutover_prep.py").read_text(encoding="utf-8")
    assert "STATUS_CUTOVER_READY" not in text
    assert "STATUS_READY_FOR_REMAPPING" in text


def test_sqlite_source_remains_byte_equal_and_blocks_plaintext(tmp_path: Path) -> None:
    users_db = tmp_path / "users.db"
    repo = user_repository(users_db)
    repo.ensure_initial_admin("admin", "adminpass12", role="Admin", must_change_password=False)
    with sqlite3.connect(users_db) as conn:
        conn.execute(
            "INSERT INTO users(user_id, username, password, role, is_active, is_qmb, "
            "must_change_password, created_at, updated_at) "
            "VALUES ('bob', 'bob', 'plaintext', 'User', 1, 0, 0, 't', 't')"
        )
        conn.commit()
    before = _digest(users_db)
    cross = _empty_cross(tmp_path)
    result = prepare_postgres_cutover(
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert _digest(users_db) == before
    assert result.status == STATUS_BLOCKED
    assert "sqlite_unhashed_password" in result.blocker_codes
    report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    blob = json.dumps(report)
    assert "adminpass12" not in blob
    assert "$2a$" not in blob
    assert "$2b$" not in blob
    assert "password_hash" not in blob.casefold()
    assert report["sqlite_users"]["unhashed_password_count"] >= 1


def test_missing_users_db_is_invalid_source(tmp_path: Path) -> None:
    result = prepare_postgres_cutover(
        sqlite_users_path=tmp_path / "missing.db",
        cross_module_db_paths={m.module_id: tmp_path / f"{m.module_id}.db" for m in MODULE_DATABASES},
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert result.status == STATUS_INVALID_SOURCE
    assert "sqlite_users_missing" in result.blocker_codes


def test_missing_cross_module_db_blocks(tmp_path: Path) -> None:
    users_db = _hashed_users_db(tmp_path)
    cross = _empty_cross(tmp_path)
    missing = cross["documents"]
    missing.unlink()
    result = prepare_postgres_cutover(
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert result.status == STATUS_BLOCKED
    assert "cross_module_db_missing:documents" in result.blocker_codes


def test_handwritten_drill_json_is_not_acceptance(tmp_path: Path) -> None:
    users_db = _hashed_users_db(tmp_path)
    cross = _empty_cross(tmp_path)
    fake = tmp_path / "fake-drill.json"
    fake.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "ok": True,
                "tool": "pg_dump/pg_restore",
                "validation_database": "qmtool_um_restore_drill",
            }
        ),
        encoding="utf-8",
    )
    result = prepare_postgres_cutover(
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
        drill_restore_dsn="",
    )
    assert result.status == STATUS_BLOCKED
    assert "drill_params_missing" in result.blocker_codes
    assert result.status != STATUS_READY_FOR_REMAPPING


def test_corrupt_sqlite_source_is_invalid(tmp_path: Path) -> None:
    users_db = tmp_path / "users.db"
    users_db.write_bytes(b"not-a-sqlite-database" + os.urandom(64))
    cross = _empty_cross(tmp_path)
    result = prepare_postgres_cutover(
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert result.status == STATUS_INVALID_SOURCE
    assert any(
        code in result.blocker_codes
        for code in ("sqlite_integrity_failed", "sqlite_users_unreadable", "sqlite_users_invalid")
    )


def test_migration_checksum_mismatch_is_invalid(tmp_path: Path) -> None:
    users_db = _hashed_users_db(tmp_path)
    with sqlite3.connect(users_db) as conn:
        conn.execute(
            "UPDATE _qm_schema_migrations SET checksum = ? WHERE version = 1",
            ("0" * 64,),
        )
        conn.commit()
    cross = _empty_cross(tmp_path)
    result = prepare_postgres_cutover(
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert result.status == STATUS_INVALID_SOURCE
    assert "sqlite_migration_checksum_mismatch" in result.blocker_codes


def test_nonempty_cross_module_refs_block(tmp_path: Path) -> None:
    users_db = _hashed_users_db(tmp_path)
    cross = _empty_cross(tmp_path)
    training = cross["training"]
    with sqlite3.connect(training) as conn:
        conn.execute(
            "INSERT INTO training_user_tags(user_id, tag) VALUES ('admin', 'ops')"
        )
        conn.commit()
    result = prepare_postgres_cutover(
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert result.status == STATUS_BLOCKED
    assert "cross_module_refs_nonempty" in result.blocker_codes
    assert any(code.startswith("cross_module_refs_present:training") for code in result.blocker_codes)


@pytest.mark.postgres
def test_postgres_wrong_role_blocks_readiness(tmp_path: Path) -> None:
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    runtime_dsn = env.runtime_dsn
    try:
        from modules.usermanagement import postgres_schema as pgs

        pgs.migrate_usermanagement_schema(migrator_dsn)
        users_db = _hashed_users_db(tmp_path)
        cross = _empty_cross(tmp_path)
        result = prepare_postgres_cutover(
            sqlite_users_path=users_db,
            cross_module_db_paths=cross,
            postgres_migrator_dsn=runtime_dsn,
            report_dir=tmp_path / "reports",
            drill_restore_dsn="",
        )
        assert result.status == STATUS_BLOCKED
        assert "postgres_migrator_role_required" in result.blocker_codes
    finally:
        cleanup_live_environment(admin_dsn=admin_dsn)


@pytest.mark.postgres
def test_postgres_readiness_and_ready_for_remapping(tmp_path: Path) -> None:
    _require_pg_tools()
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    try:
        from modules.usermanagement import postgres_schema as pgs

        pgs.migrate_usermanagement_schema(migrator_dsn)
        restore_dsn = _prepare_restore_db(env)
        users_db = _hashed_users_db(tmp_path)
        cross = _empty_cross(tmp_path)
        result = prepare_postgres_cutover(
            sqlite_users_path=users_db,
            cross_module_db_paths=cross,
            postgres_migrator_dsn=migrator_dsn,
            report_dir=tmp_path / "reports",
            drill_restore_dsn=restore_dsn,
            drill_work_dir=tmp_path / "drill",
        )
        assert result.status == STATUS_READY_FOR_REMAPPING, result.blocker_codes
        assert result.blocker_codes == ()
        report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
        assert report["status"] == STATUS_READY_FOR_REMAPPING
        assert report["postgres_readiness"]["ready"] is True
        assert report["postgres_readiness"]["read_only"] is True
        assert report["postgres_readiness"]["migrator_role_active"] is True
        assert report["backup_restore_drill"]["ok"] is True
        assert report["backup_restore_drill"].get("dump_sha256")
        assert report["status"] != "cutover_ready"
    finally:
        _drop_restore_db(admin_dsn)
        cleanup_live_environment(admin_dsn=admin_dsn)


def test_api_wrapper_matches_internal(tmp_path: Path) -> None:
    users_db = tmp_path / "users.db"
    user_repository(users_db)
    cross = _empty_cross(tmp_path)
    container = RuntimeContainer()
    result = um_api.prepare_postgres_cutover(
        container,
        sqlite_users_path=users_db,
        cross_module_db_paths=cross,
        postgres_migrator_dsn="",
        report_dir=tmp_path / "reports",
    )
    assert result.status in {STATUS_BLOCKED, STATUS_INVALID_SOURCE, STATUS_READY_FOR_REMAPPING}
    assert result.status != "cutover_ready"
    assert "drill_params_missing" in result.blocker_codes


def test_subprocess_connection_removes_password_from_arguments() -> None:
    safe_dsn, child_env = _subprocess_connection(
        "host=localhost port=5432 dbname=qmtool user=migrator password=top-secret"
    )
    assert "top-secret" not in safe_dsn
    assert "password" not in psycopg.conninfo.conninfo_to_dict(safe_dsn)
    assert child_env["PGPASSWORD"] == "top-secret"


def test_drill_source_contains_no_clean_restore_option() -> None:
    source = Path("modules/usermanagement/cutover_drill.py").read_text(encoding="utf-8")
    assert '"--clean"' not in source


@pytest.mark.parametrize(
    ("status", "expected_exit"),
    [
        (STATUS_READY_FOR_REMAPPING, 0),
        (STATUS_BLOCKED, 1),
        (STATUS_INVALID_SOURCE, 1),
    ],
)
def test_cli_exit_codes(monkeypatch: pytest.MonkeyPatch, status: str, expected_exit: int) -> None:
    from scripts import prepare_postgres_cutover as cli

    monkeypatch.setattr(
        cli.um_api,
        "prepare_postgres_cutover",
        lambda *args, **kwargs: um_api.CutoverPrepResult(
            status=status,
            report_path="build/report.json",
            blocker_codes=() if status == STATUS_READY_FOR_REMAPPING else ("blocked",),
        ),
    )
    exit_code = cli.main(
        [
            "--sqlite-users", "users.db",
            "--documents-db", "documents.db",
            "--training-db", "training.db",
            "--incident-management-db", "incidents.db",
            "--signature-db", "signature.db",
            "--postgres-migrator-dsn", "dbname=source",
            "--drill-restore-dsn", "dbname=target",
            "--report-dir", "build",
        ]
    )
    assert exit_code == expected_exit


def test_cli_technical_failure_redacts_exception_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from scripts import prepare_postgres_cutover as cli

    def fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("password=top-secret")

    monkeypatch.setattr(cli.um_api, "prepare_postgres_cutover", fail)
    exit_code = cli.main(
        [
            "--sqlite-users", "users.db",
            "--documents-db", "documents.db",
            "--training-db", "training.db",
            "--incident-management-db", "incidents.db",
            "--signature-db", "signature.db",
            "--postgres-migrator-dsn", "password=top-secret dbname=source",
            "--drill-restore-dsn", "password=top-secret dbname=target",
            "--report-dir", "build",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "top-secret" not in captured.err


@pytest.mark.postgres
def test_same_database_with_different_dsn_blocks_before_restore(tmp_path: Path) -> None:
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    try:
        pgs.migrate_usermanagement_schema(migrator_dsn)
        alias_params = psycopg.conninfo.conninfo_to_dict(migrator_dsn)
        alias_params["application_name"] = "m8-same-database-alias"
        alias_dsn = psycopg.conninfo.make_conninfo(**alias_params)
        result = run_postgres_backup_restore_drill(
            source_migrator_dsn=migrator_dsn,
            restore_target_dsn=alias_dsn,
            expected_source=_source_expectation(migrator_dsn),
            work_dir=tmp_path / "drill",
        )
        assert result.ok is False
        assert "drill_source_equals_target" in result.blocker_codes
        assert "pg_restore_exit_code" not in result.section
    finally:
        cleanup_live_environment(admin_dsn=admin_dsn)


@pytest.mark.postgres
def test_nonempty_restore_target_blocks_without_mutation(tmp_path: Path) -> None:
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    try:
        pgs.migrate_usermanagement_schema(migrator_dsn)
        restore_dsn = _prepare_restore_db(env)
        with psycopg.connect(_dsn_with_db(admin_dsn, RESTORE_DB_NAME), autocommit=True) as admin:
            admin.execute("CREATE TABLE public.keep_me(value integer)")
        result = run_postgres_backup_restore_drill(
            source_migrator_dsn=migrator_dsn,
            restore_target_dsn=restore_dsn,
            expected_source=_source_expectation(migrator_dsn),
            work_dir=tmp_path / "drill",
        )
        assert result.ok is False
        assert "drill_target_not_empty" in result.blocker_codes
        assert "pg_restore_exit_code" not in result.section
        with psycopg.connect(_dsn_with_db(admin_dsn, RESTORE_DB_NAME)) as admin:
            assert admin.execute("SELECT to_regclass('public.keep_me')").fetchone()[0]
    finally:
        _drop_restore_db(admin_dsn)
        cleanup_live_environment(admin_dsn=admin_dsn)


@pytest.mark.postgres
def test_wrong_restore_target_name_blocks_before_restore(tmp_path: Path) -> None:
    env = _prepare_or_skip()
    admin_dsn = env.admin_dsn
    migrator_dsn = env.migrator_dsn
    try:
        pgs.migrate_usermanagement_schema(migrator_dsn)
        restore_dsn = _prepare_restore_db(env, WRONG_RESTORE_DB_NAME)
        result = run_postgres_backup_restore_drill(
            source_migrator_dsn=migrator_dsn,
            restore_target_dsn=restore_dsn,
            expected_source=_source_expectation(migrator_dsn),
            work_dir=tmp_path / "drill",
        )
        assert result.ok is False
        assert "drill_target_name_invalid" in result.blocker_codes
        assert "pg_restore_exit_code" not in result.section
    finally:
        _drop_restore_db(admin_dsn, WRONG_RESTORE_DB_NAME)
        cleanup_live_environment(admin_dsn=admin_dsn)
