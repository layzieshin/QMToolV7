"""Git-backed tests for the Usermanagement PostgreSQL migration gate."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import postgres_migration_gate as gate


MIGRATIONS_REL = Path("modules/usermanagement/postgres/migrations")
PROVISION_REL = Path("modules/usermanagement/postgres/provision_roles.sql")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )


def _write_packaging(root: Path, migrations: tuple[str, ...]) -> None:
    data = [
        (f"{MIGRATIONS_REL.as_posix()}/{name}", MIGRATIONS_REL.as_posix())
        for name in migrations
    ]
    data.append((PROVISION_REL.as_posix(), PROVISION_REL.parent.as_posix()))
    _write(
        root / gate.PACKAGING_BUILD_REL,
        "_COLLECT_ALL: list[str] = ['psycopg', 'psycopg_binary']\n"
        f"_BUNDLE_DATA: list[tuple[str, str]] = {data!r}\n",
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _write(root / MIGRATIONS_REL / "0001_initial.sql", "SELECT 1;\n")
    _write(
        root / PROVISION_REL,
        "CREATE ROLE qmtool_migrator NOLOGIN;\n"
        "CREATE ROLE qmtool_runtime NOLOGIN;\n",
    )
    _write_packaging(root, ("0001_initial.sql",))
    _git(root, "init")
    _git(root, "config", "user.name", "M3.1 Gate Test")
    _git(root, "config", "user.email", "m3-1-gate@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", "--", ".")
    _git(root, "commit", "-m", "baseline")
    return root


def test_invalid_base_ref_fails_closed(scratch_repo: Path) -> None:
    result = gate.evaluate_postgres_migration_gate(
        base_ref="not-a-real-ref",
        root=scratch_repo,
    )

    assert result["ok"] is False
    checks = result["checks"]
    assert checks["base_ref_valid"] is False
    assert checks["base_listing_ok"] is False
    assert checks["no_deleted_migrations"] is False
    assert checks["existing_pg_migrations_immutable"] is False
    assert checks["pg_migrations_append_only"] is False


def test_base_listing_error_fails_closed(
    scratch_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_run = gate.subprocess.run

    def fail_ls_tree(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        if isinstance(command, list) and command[:2] == ["git", "ls-tree"]:
            return subprocess.CompletedProcess(command, 128, "", "forced ls-tree failure")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(gate.subprocess, "run", fail_ls_tree)
    result = gate.evaluate_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result["ok"] is False
    assert result["checks"]["base_ref_valid"] is True
    assert result["checks"]["base_listing_ok"] is False


def test_deleted_base_migration_is_rejected(scratch_repo: Path) -> None:
    (scratch_repo / MIGRATIONS_REL / "0001_initial.sql").unlink()

    result = gate.evaluate_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result["ok"] is False
    assert result["checks"]["no_deleted_migrations"] is False
    assert result["diagnostics"]["deleted_migrations"] == [
        f"{MIGRATIONS_REL.as_posix()}/0001_initial.sql"
    ]


def test_mutated_base_migration_is_rejected(scratch_repo: Path) -> None:
    _write(scratch_repo / MIGRATIONS_REL / "0001_initial.sql", "SELECT 2;\n")

    result = gate.evaluate_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result["ok"] is False
    assert result["checks"]["existing_pg_migrations_immutable"] is False


def test_non_append_version_is_rejected_even_when_chain_is_invalid(
    scratch_repo: Path,
) -> None:
    _write(scratch_repo / MIGRATIONS_REL / "0000_prepended.sql", "SELECT 0;\n")
    _write_packaging(
        scratch_repo,
        ("0000_prepended.sql", "0001_initial.sql"),
    )

    result = gate.evaluate_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result["ok"] is False
    assert result["checks"]["migration_chain_valid"] is False
    assert result["checks"]["pg_migrations_append_only"] is False


def test_correctly_appended_migration_is_accepted(scratch_repo: Path) -> None:
    _write(scratch_repo / MIGRATIONS_REL / "0002_add_note.sql", "SELECT 2;\n")
    _write_packaging(
        scratch_repo,
        ("0001_initial.sql", "0002_add_note.sql"),
    )

    result = gate.evaluate_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result == {
        "ok": True,
        "checks": {
            "migration_chain_valid": True,
            "pg_migrations_outside_sqlite_discovery": True,
            "provision_roles_present": True,
            "provision_has_no_passwords": True,
            "provision_roles_are_nologin": True,
            "base_ref_valid": True,
            "base_listing_ok": True,
            "no_deleted_migrations": True,
            "existing_pg_migrations_immutable": True,
            "pg_migrations_append_only": True,
            "pg_artifacts_are_bundled": True,
            "psycopg_collected_in_bundle": True,
        },
        "diagnostics": {},
    }
