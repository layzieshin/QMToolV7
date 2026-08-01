"""AP-028 M8 controlled pg_dump/pg_restore drill. Internal only."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg

from . import postgres_schema as pgs

DRILL_EVIDENCE_SCHEMA_VERSION = 3
RESTORE_DATABASE_PREFIX = "qmtool_um_restore_drill"


@dataclass(frozen=True)
class DatabaseIdentity:
    database_name: str
    identity_digest: str


@dataclass(frozen=True)
class DrillSourceExpectation:
    identity_digest: str
    migration_tip: int
    schema_fingerprint: str


@dataclass
class DrillResult:
    ok: bool
    evidence_path: str | None
    blocker_codes: tuple[str, ...] = ()
    section: dict[str, Any] = field(default_factory=dict)


def run_postgres_backup_restore_drill(
    *,
    source_migrator_dsn: str,
    restore_target_dsn: str,
    expected_source: DrillSourceExpectation,
    work_dir: Path | str,
) -> DrillResult:
    """Restore a Usermanagement dump into a distinct, empty drill database."""
    section: dict[str, Any] = {
        "ok": False,
        "issues": [],
        "schema_version": DRILL_EVIDENCE_SCHEMA_VERSION,
    }
    blockers: list[str] = []
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    run_suffix = uuid4().hex[:12]
    evidence_path = work / f"pg-backup-restore-drill-{run_suffix}.json"
    dump_path = work / f"um-cutover-prep-{run_suffix}.dump"

    source = str(source_migrator_dsn or "").strip()
    target = str(restore_target_dsn or "").strip()
    if not source or not target:
        blockers.append("drill_params_missing")
        section["issues"].append("drill_params_missing")
        return _finish(False, evidence_path, blockers, section, write=False)

    try:
        source_identity = _inspect_database(source, require_empty=False)
        target_identity = _inspect_database(target, require_empty=False)
    except DrillPreflightError as exc:
        blockers.append(exc.code)
        section["issues"].append(exc.code)
        return _finish(False, evidence_path, blockers, section, write=True)
    except Exception as exc:  # noqa: BLE001
        blockers.append("drill_database_preflight_failed")
        section["issues"].append(
            f"drill_database_preflight_failed:{type(exc).__name__}"
        )
        return _finish(False, evidence_path, blockers, section, write=True)

    section.update(
        {
            "source_database": source_identity.database_name,
            "source_identity_digest": source_identity.identity_digest,
            "validation_database": target_identity.database_name,
            "target_identity_digest": target_identity.identity_digest,
        }
    )
    if source_identity.identity_digest == target_identity.identity_digest:
        blockers.append("drill_source_equals_target")
        section["issues"].append("drill_source_equals_target")
        return _finish(False, evidence_path, blockers, section, write=True)
    if not target_identity.database_name.startswith(RESTORE_DATABASE_PREFIX):
        blockers.append("drill_target_name_invalid")
        section["issues"].append("drill_target_name_invalid")
        return _finish(False, evidence_path, blockers, section, write=True)
    if source_identity.identity_digest != expected_source.identity_digest:
        blockers.append("drill_source_identity_mismatch")
        section["issues"].append("drill_source_identity_mismatch")
        return _finish(False, evidence_path, blockers, section, write=True)
    try:
        _assert_restore_target_empty(target, target_identity)
    except DrillPreflightError as exc:
        blockers.append(exc.code)
        section["issues"].append(exc.code)
        return _finish(False, evidence_path, blockers, section, write=True)

    try:
        source_tip, source_fp = _source_schema_state(source)
    except DrillPreflightError as exc:
        blockers.append(exc.code)
        section["issues"].append(exc.code)
        return _finish(False, evidence_path, blockers, section, write=True)
    except pgs.PostgresSchemaError as exc:
        blockers.append("drill_source_migrator_role_required")
        section["issues"].append(f"drill_source_migrator_role_required:{exc}")
        return _finish(False, evidence_path, blockers, section, write=True)
    except Exception as exc:  # noqa: BLE001
        blockers.append("drill_source_failed")
        section["issues"].append(f"drill_source_failed:{type(exc).__name__}")
        return _finish(False, evidence_path, blockers, section, write=True)

    section["source_tip_version"] = source_tip
    section["source_fingerprint"] = source_fp
    if (
        source_tip != expected_source.migration_tip
        or source_fp != expected_source.schema_fingerprint
    ):
        blockers.append("drill_source_readiness_mismatch")
        section["issues"].append("drill_source_readiness_mismatch")
        return _finish(False, evidence_path, blockers, section, write=True)

    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        blockers.append("drill_tools_missing")
        section["issues"].append("drill_tools_missing")
        return _finish(False, evidence_path, blockers, section, write=True)

    source_arg, source_env = _subprocess_connection(source)
    target_arg, target_env = _subprocess_connection(target)
    dump_proc = subprocess.run(
        [
            pg_dump,
            "--format=custom",
            f"--schema={pgs.SCHEMA_NAME}",
            f"--file={dump_path}",
            f"--role={pgs.MIGRATOR_ROLE}",
            "--dbname",
            source_arg,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=source_env,
    )
    section["pg_dump_exit_code"] = int(dump_proc.returncode)
    if dump_proc.returncode != 0 or not dump_path.is_file():
        dump_path.unlink(missing_ok=True)
        blockers.append("drill_pg_dump_failed")
        section["issues"].append("drill_pg_dump_failed")
        return _finish(False, evidence_path, blockers, section, write=True)

    section["dump_sha256"] = hashlib.sha256(dump_path.read_bytes()).hexdigest()
    section["dump_path"] = str(dump_path)
    restore_proc = subprocess.run(
        [
            pg_restore,
            "--no-owner",
            "--no-acl",
            f"--role={pgs.MIGRATOR_ROLE}",
            f"--dbname={target_arg}",
            str(dump_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=target_env,
    )
    section["pg_restore_exit_code"] = int(restore_proc.returncode)
    if restore_proc.returncode != 0:
        blockers.append("drill_pg_restore_failed")
        section["issues"].append("drill_pg_restore_failed")
        return _finish(False, evidence_path, blockers, section, write=True)

    try:
        verified_identity = _inspect_database(target, require_empty=False)
        if verified_identity.identity_digest != target_identity.identity_digest:
            raise DrillPreflightError("drill_target_identity_changed")
        target_tip, target_fp = _source_schema_state(target)
        section["target_fingerprint"] = target_fp
        section["target_tip_version"] = target_tip
        if target_tip != source_tip:
            raise DrillPreflightError("drill_restore_tip_mismatch")
        if target_fp != source_fp:
            raise DrillPreflightError("drill_restore_fingerprint_mismatch")
    except DrillPreflightError as exc:
        blockers.append(exc.code)
        section["issues"].append(exc.code)
        return _finish(False, evidence_path, blockers, section, write=True)
    except pgs.PostgresSchemaError as exc:
        blockers.append("drill_restore_migrator_role_required")
        section["issues"].append(f"drill_restore_migrator_role_required:{exc}")
        return _finish(False, evidence_path, blockers, section, write=True)
    except Exception as exc:  # noqa: BLE001
        blockers.append("drill_restore_verify_failed")
        section["issues"].append(f"drill_restore_verify_failed:{type(exc).__name__}")
        return _finish(False, evidence_path, blockers, section, write=True)

    section["ok"] = True
    section["validated_at"] = datetime.now(timezone.utc).isoformat()
    section["tool"] = "pg_dump/pg_restore"
    return _finish(True, evidence_path, blockers, section, write=True)


class DrillPreflightError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _inspect_database(dsn: str, *, require_empty: bool) -> DatabaseIdentity:
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        pgs._activate_migrator_role(conn)  # noqa: SLF001
        identity = database_identity_for_connection(conn)
        if require_empty and _database_has_user_objects(conn):
            raise DrillPreflightError("drill_target_not_empty")
        return identity


def database_identity_for_connection(conn: psycopg.Connection) -> DatabaseIdentity:
    row = conn.execute(
        """
        SELECT control.system_identifier::text,
               database.oid::text,
               current_database()
        FROM pg_control_system() AS control
        JOIN pg_database AS database
          ON database.datname = current_database()
        """
    ).fetchone()
    if row is None:
        raise DrillPreflightError("drill_database_identity_missing")
    identity_digest = hashlib.sha256(f"{row[0]}:{row[1]}".encode("utf-8")).hexdigest()
    return DatabaseIdentity(
        database_name=str(row[2]),
        identity_digest=identity_digest,
    )


def _assert_restore_target_empty(dsn: str, expected: DatabaseIdentity) -> None:
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        pgs._activate_migrator_role(conn)  # noqa: SLF001
        current = database_identity_for_connection(conn)
        if current.identity_digest != expected.identity_digest:
            raise DrillPreflightError("drill_target_identity_changed")
        if _database_has_user_objects(conn):
            raise DrillPreflightError("drill_target_not_empty")


def _database_has_user_objects(conn: psycopg.Connection) -> bool:
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_namespace namespace
            WHERE namespace.nspname NOT IN ('pg_catalog', 'information_schema', 'public')
              AND namespace.nspname NOT LIKE 'pg_toast%'
              AND namespace.nspname NOT LIKE 'pg_temp_%'
        ) OR EXISTS (
            SELECT 1
            FROM pg_class relation
            JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
            WHERE namespace.nspname = 'public'
              AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
        ) OR EXISTS (
            SELECT 1
            FROM pg_proc function
            JOIN pg_namespace namespace ON namespace.oid = function.pronamespace
            WHERE namespace.nspname = 'public'
        ) OR EXISTS (
            SELECT 1
            FROM pg_type type
            JOIN pg_namespace namespace ON namespace.oid = type.typnamespace
            WHERE namespace.nspname = 'public'
              AND type.typtype IN ('c', 'd', 'e', 'm', 'r')
        )
        """
    ).fetchone()
    return bool(row and row[0])


def _source_schema_state(dsn: str) -> tuple[int, str]:
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        pgs._activate_migrator_role(conn)  # noqa: SLF001
        if not pgs._history_table_exists(conn):  # noqa: SLF001
            raise DrillPreflightError("drill_source_history_missing")
        applied = pgs._fetch_applied(conn)  # noqa: SLF001
        if not applied:
            raise DrillPreflightError("drill_source_not_migrated")
        pgs._validate_history_prefix(applied, pgs.discover_migrations())  # noqa: SLF001
        fingerprint = pgs._compute_schema_fingerprint(conn)  # noqa: SLF001
        if fingerprint != applied[-1].schema_fingerprint:
            raise DrillPreflightError("drill_source_fingerprint_drift")
        return int(applied[-1].version), str(fingerprint)


def _subprocess_connection(dsn: str) -> tuple[str, dict[str, str]]:
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    password = params.pop("password", None)
    ssl_password = params.pop("sslpassword", None)
    safe_dsn = psycopg.conninfo.make_conninfo(**params)
    child_env = os.environ.copy()
    if password is not None:
        child_env["PGPASSWORD"] = str(password)
    if ssl_password is not None:
        child_env["PGSSLPASSWORD"] = str(ssl_password)
    return safe_dsn, child_env


def _finish(
    ok: bool,
    evidence_path: Path,
    blockers: list[str],
    section: dict[str, Any],
    *,
    write: bool,
) -> DrillResult:
    section["ok"] = ok
    if not write:
        return DrillResult(
            ok=ok,
            evidence_path=None,
            blocker_codes=tuple(sorted(set(blockers))),
            section=section,
        )
    payload = {
        "schema_version": DRILL_EVIDENCE_SCHEMA_VERSION,
        "ok": ok,
        "tool": "pg_dump/pg_restore",
        "validated_at": section.get("validated_at")
        or datetime.now(timezone.utc).isoformat(),
        "source_database": section.get("source_database"),
        "source_identity_digest": section.get("source_identity_digest"),
        "validation_database": section.get("validation_database"),
        "target_identity_digest": section.get("target_identity_digest"),
        "pg_dump_exit_code": section.get("pg_dump_exit_code"),
        "pg_restore_exit_code": section.get("pg_restore_exit_code"),
        "dump_sha256": section.get("dump_sha256"),
        "source_fingerprint": section.get("source_fingerprint"),
        "target_fingerprint": section.get("target_fingerprint"),
        "source_tip_version": section.get("source_tip_version"),
        "target_tip_version": section.get("target_tip_version"),
        "issues": list(section.get("issues") or []),
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    lowered = serialized.casefold()
    for needle in ("password=", "pwd=", "$2a$", "$2b$", "raw_token"):
        if needle in lowered:
            raise RuntimeError("drill evidence would leak secret material")
    evidence_path.write_text(serialized + "\n", encoding="utf-8")
    section["evidence_path"] = str(evidence_path)
    return DrillResult(
        ok=ok,
        evidence_path=str(evidence_path),
        blocker_codes=tuple(sorted(set(blockers))),
        section=section,
    )
