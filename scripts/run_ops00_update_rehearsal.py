"""Guarded Slot-2 update rehearsal abort for OPS00-D."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg

from qm_platform.blob.backup_orchestrator import RESTORE_DB_PREFIX, BackupOrchestratorError
from qm_platform.runtime.maintenance import MaintenanceError, abort_update_rehearsal
from qm_platform.runtime.paths import resolve_home_path, runtime_home
from tests.postgres_destructive_guard import (
    DestructivePostgresGuardError,
    RESET_OPT_IN_VALUE,
    TEST_RESET_ENV,
    preflight_isolated_postgres_target,
    require_approved_admin_dsn,
)

_ENV_PATH = ROOT / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def _suffix() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _drop_restore_database(database_name: str, *, admin_dsn: str) -> None:
    if not database_name.startswith(RESTORE_DB_PREFIX):
        raise DestructivePostgresGuardError("restore database name missing required prefix")
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (database_name,),
        )
        admin.execute(
            psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(
                psycopg.sql.Identifier(database_name)
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OPS00 guarded Slot-2 update rehearsal abort")
    parser.add_argument("--backup-dir", required=True, help="Sealed backup set directory")
    parser.add_argument(
        "--target-database",
        help=f"Restore database name (default: {RESTORE_DB_PREFIX}<suffix>)",
    )
    args = parser.parse_args(argv)

    _load_dotenv(_ENV_PATH)
    os.environ.pop(TEST_RESET_ENV, None)
    try:
        approved = preflight_isolated_postgres_target()
    except DestructivePostgresGuardError as exc:
        print(f"preflight: {exc}", file=sys.stderr)
        return 2

    print(
        "preflight: ok "
        f"database={approved.database} major={approved.major_version} "
        f"port={approved.port} marker={approved.cluster_marker}"
    )

    os.environ[TEST_RESET_ENV] = RESET_OPT_IN_VALUE
    admin_dsn = None
    target_database = args.target_database or f"{RESTORE_DB_PREFIX}{_suffix()}"
    backup_dir = Path(args.backup_dir)
    if not backup_dir.is_absolute():
        backup_dir = resolve_home_path(runtime_home(), str(backup_dir))

    home = runtime_home()
    destination_blob_root = resolve_home_path(
        home, "storage/platform/blobs-update-rehearsal-restore"
    )

    exit_code = 0
    result = None
    try:
        admin_dsn = require_approved_admin_dsn()
        result = abort_update_rehearsal(
            backup_dir=backup_dir,
            target_admin_dsn=admin_dsn,
            target_database=target_database,
            destination_blob_root=destination_blob_root,
            app_home=home,
        )
    except (BackupOrchestratorError, MaintenanceError, DestructivePostgresGuardError) as exc:
        print(str(exc), file=sys.stderr)
        exit_code = 1
    finally:
        try:
            if admin_dsn is not None:
                _drop_restore_database(target_database, admin_dsn=admin_dsn)
        except DestructivePostgresGuardError as exc:
            print(f"cleanup: {exc}", file=sys.stderr)
            if exit_code == 0:
                exit_code = 3
        os.environ.pop(TEST_RESET_ENV, None)

    if exit_code != 0 or result is None:
        return exit_code

    print(
        json.dumps(
            {
                "backup_id": result.backup_id,
                "target_database": result.target_database,
                "restored_release_fingerprint": result.restored_release_fingerprint,
                "restored_blob_count": result.restored_blob_count,
                "verified_artifact_count": result.verified_artifact_count,
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
