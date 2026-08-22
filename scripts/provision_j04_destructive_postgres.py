"""One-time / repeat local provisioning for J04 Slot-2 destructive PostgreSQL tests.

Creates the isolated test admin, database, cluster marker, and appends gitignored
``.env`` keys. Never writes ``QMTOOL_PG_TEST_RESET``.

Superuser access (pick one):
  - ``--superuser-dsn postgresql://postgres:...@127.0.0.1:5432/postgres``
  - env ``J04_PG_PROVISION_SUPERUSER_DSN`` (same; never commit)
  - ``--local-trust-bootstrap`` on Windows localhost only (temporary pg_hba trust)

Product code must not import this module.
"""
from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import psycopg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.postgres_destructive_guard import (  # noqa: E402
    EXPECTED_CLUSTER_MARKER,
    EXPECTED_DATABASE,
    TEST_EXPECTED_DATABASE_ENV,
    TEST_EXPECTED_MAJOR_ENV,
    TEST_ADMIN_DSN_ENV,
)

ENV_PATH = ROOT / ".env"
MARKER_SQL = ROOT / "tests" / "postgres" / "init" / "001_test_cluster_marker.sql"
TEST_ADMIN = "qmtool_j04_test_admin"
LEGACY_DB = "qmtool_destructive_test"
FORBIDDEN_HOSTS = frozenset({"192.168.0.4"})


class ProvisionError(RuntimeError):
    """Non-zero exit for operator-visible provisioning failures."""


def _password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "J04" + "".join(secrets.choice(alphabet) for _ in range(28))


def _parse_host_port(dsn: str) -> tuple[str, str]:
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    host = str(info.get("host") or "127.0.0.1").strip().lower()
    if host in {"localhost", "::1"}:
        host = "127.0.0.1"
    port = str(info.get("port") or "5432").strip() or "5432"
    return host, port


def _assert_local_disposable_target(host: str, port: str) -> None:
    if host in FORBIDDEN_HOSTS:
        raise ProvisionError(f"refusing provisioning on lab host {host}")
    if host not in {"127.0.0.1", "localhost"}:
        raise ProvisionError(
            "local provisioning is limited to 127.0.0.1/localhost disposable clusters"
        )
    if port != "5432":
        raise ProvisionError(
            "local default-cluster provisioning expects port 5432; "
            "use --superuser-dsn for custom endpoints"
        )


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


def _append_env(keys: dict[str, str]) -> list[str]:
    text = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.is_file() else ""
    existing = set()
    for raw in text.splitlines():
        if raw.strip() and not raw.strip().startswith("#") and "=" in raw:
            existing.add(raw.split("=", 1)[0].strip())
    added: list[str] = []
    lines: list[str] = []
    if text and not text.endswith("\n"):
        lines.append("")
    for key, value in keys.items():
        if key in existing:
            print(f"env: skip existing {key}")
            continue
        added.append(key)
        lines.append(f"{key}={value}")
    if not added:
        return added
    block = "\n".join(
        [
            "",
            "# J04-M0 Slot-2 destructive test cluster (local, gitignored; no RESET)",
            *lines,
            "",
        ]
    )
    ENV_PATH.write_text(text + block, encoding="utf-8")
    print("env: appended " + ", ".join(added))
    return added


def _terminate_db(conn: psycopg.Connection, name: str) -> None:
    conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = %s AND pid <> pg_backend_pid()
        """,
        (name,),
    )
    conn.execute(
        psycopg.sql.SQL("DROP DATABASE IF EXISTS {}").format(psycopg.sql.Identifier(name))
    )


def _provision_cluster(super_dsn: str, *, expected_major: int) -> str:
    host, port = _parse_host_port(super_dsn)
    _assert_local_disposable_target(host, port)
    password = _password()
    marker_sql = MARKER_SQL.read_text(encoding="utf-8")

    with psycopg.connect(super_dsn, autocommit=True) as conn:
        version_num = int(conn.execute("SHOW server_version_num").fetchone()[0])
        major = version_num // 10000
        if major < 16:
            raise ProvisionError(f"PostgreSQL major {major} is below minimum 16")
        print(f"cluster: host={host} port={port} major={major}")

        exists = conn.execute(
            "SELECT 1 FROM pg_roles WHERE rolname = %s", (TEST_ADMIN,)
        ).fetchone()
        if exists:
            conn.execute(
                psycopg.sql.SQL(
                    "ALTER ROLE {} WITH LOGIN SUPERUSER CREATEDB CREATEROLE PASSWORD {}"
                ).format(
                    psycopg.sql.Identifier(TEST_ADMIN),
                    psycopg.sql.Literal(password),
                )
            )
            print(f"admin: updated role {TEST_ADMIN}")
        else:
            conn.execute(
                psycopg.sql.SQL(
                    "CREATE ROLE {} LOGIN SUPERUSER CREATEDB CREATEROLE PASSWORD {}"
                ).format(
                    psycopg.sql.Identifier(TEST_ADMIN),
                    psycopg.sql.Literal(password),
                )
            )
            print(f"admin: created role {TEST_ADMIN}")

        for name in (LEGACY_DB, EXPECTED_DATABASE):
            _terminate_db(conn, name)
            print(f"database: dropped-if-existed {name}")

        conn.execute(
            psycopg.sql.SQL("CREATE DATABASE {} OWNER {}").format(
                psycopg.sql.Identifier(EXPECTED_DATABASE),
                psycopg.sql.Identifier(TEST_ADMIN),
            )
        )
        print(f"database: created {EXPECTED_DATABASE}")

    admin_dsn = (
        f"postgresql://{quote_plus(TEST_ADMIN)}:{quote_plus(password)}"
        f"@{host}:{port}/{EXPECTED_DATABASE}"
    )
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(marker_sql)
        marker = admin.execute(
            """
            SELECT marker_value
            FROM public.qmtool_j04_test_cluster_marker
            WHERE marker_key = 'cluster_id'
            """
        ).fetchone()[0]
        if str(marker) != EXPECTED_CLUSTER_MARKER:
            raise ProvisionError("cluster marker verification failed")
        print(f"marker: ok {EXPECTED_CLUSTER_MARKER}")

    _append_env(
        {
            TEST_ADMIN_DSN_ENV: admin_dsn,
            TEST_EXPECTED_DATABASE_ENV: EXPECTED_DATABASE,
            TEST_EXPECTED_MAJOR_ENV: str(expected_major),
        }
    )
    if "QMTOOL_PG_TEST_RESET" in ENV_PATH.read_text(encoding="utf-8"):
        raise ProvisionError(".env must not contain QMTOOL_PG_TEST_RESET")
    print("provision: ok")
    return admin_dsn


def _local_trust_bootstrap(expected_major: int) -> None:
    if sys.platform != "win32":
        raise ProvisionError("--local-trust-bootstrap is Windows localhost only")
    pgdata = Path(r"C:\Program Files\PostgreSQL\18\data")
    hba = pgdata / "pg_hba.conf"
    if not hba.is_file():
        raise ProvisionError(f"pg_hba.conf not found at {hba}")
    backup = pgdata / "pg_hba.conf.j04_provision_bak"
    trust = (
        "# J04 temporary local trust — removed after provision\n"
        "host    all             postgres        127.0.0.1/32            trust\n"
        "host    all             postgres        ::1/128                 trust\n\n"
    )
    original = hba.read_text(encoding="utf-8")
    backup.write_text(original, encoding="utf-8")
    try:
        hba.write_text(trust + original, encoding="utf-8")
        time.sleep(0.3)
        super_dsn = "host=127.0.0.1 port=5432 dbname=postgres user=postgres"
        admin_dsn = _provision_cluster(super_dsn, expected_major=expected_major)
    finally:
        hba.write_text(original, encoding="utf-8")
        backup.unlink(missing_ok=True)
        try:
            with psycopg.connect(admin_dsn, autocommit=True) as conn:
                conn.execute("SELECT pg_reload_conf()")
        except Exception:
            pass
    print("pg_hba: restored")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision local J04 Slot-2 destructive PostgreSQL test cluster."
    )
    parser.add_argument(
        "--superuser-dsn",
        default=os.environ.get("J04_PG_PROVISION_SUPERUSER_DSN", "").strip(),
        help="PostgreSQL superuser DSN for localhost disposable cluster",
    )
    parser.add_argument(
        "--expected-major",
        type=int,
        default=int(os.environ.get(TEST_EXPECTED_MAJOR_ENV, "18") or "18"),
        help="Value written to QMTOOL_PG_TEST_EXPECTED_MAJOR (default 18)",
    )
    parser.add_argument(
        "--local-trust-bootstrap",
        action="store_true",
        help="Windows-only: temporary pg_hba trust for local postgres superuser",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.expected_major < 16:
        print("error: expected major must be >= 16", file=sys.stderr)
        return 2
    try:
        if args.local_trust_bootstrap:
            _local_trust_bootstrap(expected_major=args.expected_major)
        elif args.superuser_dsn:
            _provision_cluster(args.superuser_dsn, expected_major=args.expected_major)
        else:
            print(
                "error: provide --superuser-dsn, J04_PG_PROVISION_SUPERUSER_DSN, "
                "or --local-trust-bootstrap",
                file=sys.stderr,
            )
            return 2
    except ProvisionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error:
        print("error: PostgreSQL connection or SQL failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
