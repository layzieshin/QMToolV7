from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from interfaces.cli.bootstrap import build_container
from qm_platform.runtime import bootstrap as runtime_bootstrap


def _run(home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["QMTOOL_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-m", "interfaces.cli.main", "database", *args],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def test_database_status_dry_run_migrate_and_backups(tmp_path: Path) -> None:
    status_before = _run(tmp_path, "status")
    assert status_before.returncode == 8
    before_payload = json.loads(status_before.stdout)
    assert before_payload["ok"] is False
    assert {item["state"] for item in before_payload["databases"]} == {"missing"}

    dry_run = _run(tmp_path, "migrate", "--dry-run")
    assert dry_run.returncode == 0, dry_run.stderr + dry_run.stdout
    assert json.loads(dry_run.stdout)["dry_run"] is True
    assert not list((tmp_path / "storage").rglob("*.db"))

    migrate = _run(tmp_path, "migrate")
    assert migrate.returncode == 0, migrate.stderr + migrate.stdout
    migrate_payload = json.loads(migrate.stdout)
    assert migrate_payload["ok"] is True
    assert migrate_payload["backup_id"]

    status_after = _run(tmp_path, "status")
    assert status_after.returncode == 0, status_after.stderr + status_after.stdout
    after_payload = json.loads(status_after.stdout)
    assert after_payload["ok"] is True
    assert len(after_payload["databases"]) == 6
    assert {item["database_id"] for item in after_payload["databases"]} == {
        "incidents",
        "platform_settings",
        "registry",
        "signature",
        "training",
        "users",
    }
    assert all(item["state"] == "current" for item in after_payload["databases"])

    backups = _run(tmp_path, "backups")
    assert backups.returncode == 0, backups.stderr + backups.stdout
    backup_payload = json.loads(backups.stdout)
    assert backup_payload["ok"] is True
    assert any(
        item["backup_id"] == migrate_payload["backup_id"]
        for item in backup_payload["backups"]
    )


def test_database_restore_command_restores_complete_set(
    tmp_path: Path,
    monkeypatch,
) -> None:
    assert _run(tmp_path, "migrate").returncode == 0
    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    container = build_container()
    lifecycle = runtime_bootstrap.prepare_core_modules(container)
    service, specs = runtime_bootstrap.configure_database_evolution(
        container,
        lifecycle,
    )
    backup = service.create_backup(specs=specs, reason="cli_restore_test")
    users = next(spec for spec in specs if spec.database_id == "users")
    with closing(sqlite3.connect(users.path)) as conn:
        conn.execute(
            """
            INSERT INTO users (
                user_id, username, password, role, created_at, updated_at
            ) VALUES ('restore-user', 'restore-user', 'hash', 'User',
                      datetime('now'), datetime('now'))
            """
        )
        conn.commit()

    restore = _run(
        tmp_path,
        "restore",
        "--backup-id",
        backup.backup_id,
    )

    assert restore.returncode == 0, restore.stderr + restore.stdout
    assert json.loads(restore.stdout)["ok"] is True
    with closing(sqlite3.connect(users.path)) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM users WHERE user_id = 'restore-user'"
        ).fetchone()[0] == 0
    assert _run(tmp_path, "status").returncode == 0
