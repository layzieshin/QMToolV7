"""Git-backed tests for the signature PostgreSQL migration gate."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import signature_postgres_migration_gate as gate


MIGRATIONS_REL = Path("modules/signature/postgres/migrations")
PROVISION_REL = Path("modules/signature/postgres/provision_signature_schema.sql")


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
        "CREATE SCHEMA signature AUTHORIZATION qmtool_migrator;\n"
        "-- qmtool_migrator qmtool_runtime\n",
    )
    _write_packaging(root, ("0001_initial.sql",))
    _git(root, "init")
    _git(root, "config", "user.name", "PG01 Gate Test")
    _git(root, "config", "user.email", "pg01-gate@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "add", "--", ".")
    _git(root, "commit", "-m", "baseline")
    return root


def test_mutated_base_migration_is_rejected(scratch_repo: Path) -> None:
    _write(scratch_repo / MIGRATIONS_REL / "0001_initial.sql", "SELECT 2;\n")

    result = gate.evaluate_signature_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result["ok"] is False
    assert result["checks"]["existing_pg_migrations_immutable"] is False


def test_correctly_appended_migration_is_accepted(scratch_repo: Path) -> None:
    _write(scratch_repo / MIGRATIONS_REL / "0002_grant_history_select.sql", "SELECT 2;\n")
    _write_packaging(
        scratch_repo,
        ("0001_initial.sql", "0002_grant_history_select.sql"),
    )

    result = gate.evaluate_signature_postgres_migration_gate(base_ref="HEAD", root=scratch_repo)

    assert result["ok"] is True
    assert result["checks"]["pg_migrations_append_only"] is True
