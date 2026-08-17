"""Unit tests for the destructive PostgreSQL guard (no live cluster required)."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from tests.postgres_destructive_guard import (
    EXPECTED_CLUSTER_MARKER,
    EXPECTED_DATABASE,
    RESET_OPT_IN_VALUE,
    DestructivePostgresGuardError,
    require_approved_admin_dsn,
    require_destructive_postgres_target,
)
from tests.postgres_live_support import (
    cleanup_live_environment,
    drop_restore_database,
    guarded_drop_usermanagement_schema,
    prepare_live_environment,
    prepare_restore_database,
)


def _valid_test_dsn() -> str:
    return f"postgresql://qmtool_j04_test_admin:secret@127.0.0.1:55432/{EXPECTED_DATABASE}"


def _arm_valid(monkeypatch) -> None:
    monkeypatch.setenv("QMTOOL_PG_TEST_ADMIN_DSN", _valid_test_dsn())
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    monkeypatch.setenv(
        "QMTOOL_PG_DSN",
        "postgresql://app:runtime-secret@127.0.0.1:5432/qmtool_app",
    )


def test_missing_test_dsn_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("QMTOOL_PG_TEST_ADMIN_DSN", raising=False)
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    with pytest.raises(DestructivePostgresGuardError, match="QMTOOL_PG_TEST_ADMIN_DSN"):
        require_destructive_postgres_target(connect=False)


def test_missing_reset_opt_in_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("QMTOOL_PG_TEST_ADMIN_DSN", _valid_test_dsn())
    monkeypatch.delenv("QMTOOL_PG_TEST_RESET", raising=False)
    with pytest.raises(DestructivePostgresGuardError, match="QMTOOL_PG_TEST_RESET"):
        require_destructive_postgres_target(connect=False)


def test_runtime_dsn_as_test_target_is_rejected(monkeypatch) -> None:
    dsn = _valid_test_dsn()
    monkeypatch.setenv("QMTOOL_PG_TEST_ADMIN_DSN", dsn)
    monkeypatch.setenv("QMTOOL_PG_DSN", dsn)
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    with pytest.raises(DestructivePostgresGuardError, match="must not equal QMTOOL_PG_DSN"):
        require_destructive_postgres_target(connect=False)


def test_forbidden_runtime_database_name_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv(
        "QMTOOL_PG_TEST_ADMIN_DSN",
        "postgresql://qmtool_j04_test_admin:secret@127.0.0.1:55432/qmtool_app",
    )
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    with pytest.raises(DestructivePostgresGuardError, match="forbidden|isolated test database"):
        require_destructive_postgres_target(connect=False)


def test_same_runtime_endpoint_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv(
        "QMTOOL_PG_TEST_ADMIN_DSN",
        f"postgresql://qmtool_j04_test_admin:secret@127.0.0.1:5432/{EXPECTED_DATABASE}",
    )
    monkeypatch.setenv(
        "QMTOOL_PG_DSN",
        "postgresql://app:runtime-secret@localhost:5432/other_db",
    )
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    with pytest.raises(DestructivePostgresGuardError, match="endpoint matches"):
        require_destructive_postgres_target(connect=False)


def test_same_endpoint_with_isolated_test_runtime_dsn_is_allowed(monkeypatch) -> None:
    """Live fixtures temporarily set QMTOOL_PG_DSN to the test-cluster runtime login."""
    monkeypatch.setenv("QMTOOL_PG_TEST_ADMIN_DSN", _valid_test_dsn())
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    monkeypatch.setenv(
        "QMTOOL_PG_DSN",
        f"postgresql://qmtool_j04_rt_login:other@127.0.0.1:55432/{EXPECTED_DATABASE}",
    )
    approved = require_destructive_postgres_target(connect=False)
    assert approved.database == EXPECTED_DATABASE


def test_wrong_expected_database_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setenv("QMTOOL_PG_TEST_EXPECTED_DATABASE", "wrong_db")
    with pytest.raises(DestructivePostgresGuardError, match="EXPECTED_DATABASE"):
        require_destructive_postgres_target(connect=False)


def test_valid_identity_without_connect_is_approved(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    approved = require_destructive_postgres_target(connect=False)
    assert approved.database == EXPECTED_DATABASE
    assert "secret" not in repr(approved)
    assert "runtime-secret" not in repr(approved)


def test_error_messages_do_not_leak_password(monkeypatch) -> None:
    monkeypatch.setenv(
        "QMTOOL_PG_TEST_ADMIN_DSN",
        "postgresql://qmtool_j04_test_admin:SuperSecretPass@127.0.0.1:55432/qmtool_app",
    )
    monkeypatch.setenv("QMTOOL_PG_TEST_RESET", RESET_OPT_IN_VALUE)
    with pytest.raises(DestructivePostgresGuardError) as captured:
        require_destructive_postgres_target(connect=False)
    assert "SuperSecretPass" not in str(captured.value)
    assert "SuperSecretPass" not in repr(captured.value)


def _mock_connect(
    rows: dict[str, object],
    *,
    capture_dsn: list[str] | None = None,
):
    conn = MagicMock()

    def execute(query, params=None):  # noqa: ANN001
        text = " ".join(str(query).split()).lower()
        result = MagicMock()
        if "select current_database()" in text:
            result.fetchone.return_value = (rows["database"],)
        elif "server_version_num" in text:
            result.fetchone.return_value = (rows["version_num"],)
        elif "qmtool_j04_test_cluster_marker" in text:
            result.fetchone.return_value = rows["marker"]
        elif "rolsuper" in text and "rolcreaterole" in text:
            result.fetchone.return_value = rows.get(
                "role_flags",
                (True, True, True),
            )
        elif "pg_get_userbyid" in text or "datdba" in text:
            result.fetchone.return_value = rows.get("is_owner", (True,))
        elif "pg_roles" in text:
            result.fetchone.return_value = (1,)
        else:
            result.fetchone.return_value = (1,)
        return result

    conn.execute.side_effect = execute
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = None

    @contextmanager
    def _cm(dsn=None, *args, **kwargs):  # noqa: ANN001
        if capture_dsn is not None and dsn is not None:
            capture_dsn.append(str(dsn))
        yield conn

    return _cm


def test_wrong_pg_version_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "150004",
                "marker": (EXPECTED_CLUSTER_MARKER,),
            }
        ),
    )
    with pytest.raises(DestructivePostgresGuardError, match="major version must be 16"):
        require_destructive_postgres_target(connect=True)


def test_missing_cluster_marker_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": None,
            }
        ),
    )
    with pytest.raises(DestructivePostgresGuardError, match="cluster marker"):
        require_destructive_postgres_target(connect=True)


def test_wrong_cluster_marker_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": ("wrong-marker",),
            }
        ),
    )
    with pytest.raises(DestructivePostgresGuardError, match="cluster marker"):
        require_destructive_postgres_target(connect=True)


def test_missing_createrole_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
                "role_flags": (False, False, True),
                "is_owner": (True,),
            }
        ),
    )
    with pytest.raises(DestructivePostgresGuardError, match="CREATEROLE"):
        require_destructive_postgres_target(connect=True)


def test_missing_createdb_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
                "role_flags": (False, True, False),
                "is_owner": (True,),
            }
        ),
    )
    with pytest.raises(DestructivePostgresGuardError, match="CREATEDB"):
        require_destructive_postgres_target(connect=True)


def test_non_owner_non_superuser_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
                "role_flags": (False, True, True),
                "is_owner": (False,),
            }
        ),
    )
    with pytest.raises(DestructivePostgresGuardError, match="own the isolated test database"):
        require_destructive_postgres_target(connect=True)


def test_valid_live_identity_is_approved(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
                "role_flags": (False, True, True),
                "is_owner": (True,),
            }
        ),
    )
    approved = require_destructive_postgres_target(connect=True)
    assert approved.major_version == 16
    assert approved.cluster_marker == EXPECTED_CLUSTER_MARKER
    assert approved.database == EXPECTED_DATABASE


def test_superuser_without_ownership_flag_is_approved(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
                "role_flags": (True, False, False),
                "is_owner": (False,),
            }
        ),
    )
    approved = require_destructive_postgres_target(connect=True)
    assert approved.major_version == 16


def test_mismatched_candidate_admin_dsn_is_rejected(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
            }
        ),
    )
    foreign = f"postgresql://qmtool_j04_test_admin:secret@10.0.0.9:55432/{EXPECTED_DATABASE}"
    with pytest.raises(DestructivePostgresGuardError, match="does not match the guard-approved"):
        require_approved_admin_dsn(candidate=foreign)


def test_destructive_helpers_reject_foreign_cluster_dsn(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
            }
        ),
    )
    foreign = f"postgresql://qmtool_j04_test_admin:secret@10.0.0.9:55432/{EXPECTED_DATABASE}"
    with pytest.raises(DestructivePostgresGuardError, match="does not match the guard-approved"):
        cleanup_live_environment(admin_dsn=foreign)
    with pytest.raises(DestructivePostgresGuardError, match="does not match the guard-approved"):
        drop_restore_database("qmtool_um_restore_drill", admin_dsn=foreign)
    with pytest.raises(DestructivePostgresGuardError, match="does not match the guard-approved"):
        prepare_restore_database(
            "qmtool_um_restore_drill",
            migrator_password="x",
            admin_dsn=foreign,
        )
    with pytest.raises(DestructivePostgresGuardError, match="does not match the guard-approved"):
        guarded_drop_usermanagement_schema(admin_dsn=foreign)
    with pytest.raises(DestructivePostgresGuardError, match="does not match the guard-approved"):
        prepare_live_environment(admin_dsn=foreign)


def test_destructive_helper_connects_only_with_approved_dsn(monkeypatch) -> None:
    _arm_valid(monkeypatch)
    approved = _valid_test_dsn()
    captured: list[str] = []
    monkeypatch.setattr(
        "tests.postgres_destructive_guard.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
            },
            capture_dsn=captured,
        ),
    )
    monkeypatch.setattr(
        "tests.postgres_live_support.psycopg.connect",
        _mock_connect(
            {
                "database": EXPECTED_DATABASE,
                "version_num": "160001",
                "marker": (EXPECTED_CLUSTER_MARKER,),
            },
            capture_dsn=captured,
        ),
    )
    # Same identity, different password spelling — must still connect with env DSN.
    candidate = (
        f"postgresql://qmtool_j04_test_admin:other-secret@127.0.0.1:55432/{EXPECTED_DATABASE}"
    )
    cleanup_live_environment(admin_dsn=candidate)
    assert approved in captured
    assert all("other-secret" not in dsn for dsn in captured)
