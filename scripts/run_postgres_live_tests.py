"""Run isolated PostgreSQL live tests after a read-only Slot-2 preflight.

Loads gitignored `.env` for Slot-2 DSN. Does not persist
`QMTOOL_PG_TEST_RESET`; the destructive opt-in is injected only into the
pytest child process after preflight succeeds.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.postgres_destructive_guard import (  # noqa: E402
    RESET_OPT_IN_VALUE,
    TEST_RESET_ENV,
    DestructivePostgresGuardError,
    preflight_isolated_postgres_target,
)
from tests.postgres_live_support import (  # noqa: E402
    RESTORE_DB_PREFIX,
    drop_restore_database,
    require_approved_admin_dsn,
)

_ENV_PATH = ROOT / ".env"

DEFAULT_LIVE_TARGETS = [
    "tests/modules/usermanagement/test_postgres_schema_live.py",
    "tests/modules/usermanagement/test_postgres_repositories_live.py",
    "tests/modules/usermanagement/test_m7_audit_evidence_live.py",
    "tests/backend/test_auth_api_postgres_live.py",
    "tests/backend/test_m6_postgres_live.py",
    "tests/modules/usermanagement/test_m8_cutover_prep.py",
]


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


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env[TEST_RESET_ENV] = RESET_OPT_IN_VALUE
    env["QMTOOL_PG_REQUIRED"] = "1"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(ROOT), existing) if part
    )
    pg16 = Path(r"C:\Program Files\PostgreSQL\16\bin")
    pg18 = Path(r"C:\Program Files\PostgreSQL\18\bin")
    extra = pg18 if pg18.is_dir() else pg16
    if extra.is_dir():
        env["PATH"] = str(extra) + os.pathsep + env.get("PATH", "")
    return env


def _cleanup_restore_databases() -> None:
    approved = require_approved_admin_dsn()
    import psycopg

    with psycopg.connect(approved) as conn:
        rows = conn.execute(
            """
            SELECT datname
            FROM pg_database
            WHERE datname LIKE %s
            """,
            (RESTORE_DB_PREFIX + "%",),
        ).fetchall()
    for (name,) in rows:
        drop_restore_database(str(name), admin_dsn=approved)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
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
    targets = args if args else DEFAULT_LIVE_TARGETS
    command = [
        sys.executable,
        "-m",
        "pytest",
        *targets,
        "-m",
        "postgres",
        "-q",
    ]
    result = subprocess.run(command, cwd=ROOT, env=_child_env(), check=False)
    try:
        os.environ[TEST_RESET_ENV] = RESET_OPT_IN_VALUE
        _cleanup_restore_databases()
    except DestructivePostgresGuardError as exc:
        print(f"cleanup: {exc}", file=sys.stderr)
        if result.returncode == 0:
            return 3
    finally:
        os.environ.pop(TEST_RESET_ENV, None)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
