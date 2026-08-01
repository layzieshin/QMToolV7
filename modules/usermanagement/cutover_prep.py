"""AP-028 M8 cutover preparation (read-only inventar / validation). Internal only."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

import psycopg

from qm_platform.persistence.database_evolution import MigrationStep

from . import postgres_schema as pgs
from .cutover_drill import (
    DrillSourceExpectation,
    database_identity_for_connection,
    run_postgres_backup_restore_drill,
)
from .cutover_reference_catalog import (
    DISCOVERABLE_IDENTITY_COLUMNS,
    IDENTITY_COLUMNS,
    MODULE_DATABASES,
    IdentityColumnRef,
    catalog_keys,
    module_database_by_id,
)
from .module import USERMANAGEMENT_DATABASE_CONTRIBUTION
from .password_crypto import is_password_hash

STATUS_INVALID_SOURCE = "invalid_source"
STATUS_BLOCKED = "blocked"
STATUS_READY_FOR_REMAPPING = "ready_for_remapping"
ALLOWED_STATUSES = frozenset(
    {STATUS_INVALID_SOURCE, STATUS_BLOCKED, STATUS_READY_FOR_REMAPPING}
)

REPORT_SCHEMA_VERSION = 1

_VALID_ROLES = frozenset({"Admin", "QMB", "User"})
_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class CutoverPrepResult:
    status: str
    report_path: str
    blocker_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid cutover prep status: {self.status}")
        if self.status == STATUS_READY_FOR_REMAPPING and self.blocker_codes:
            raise ValueError("ready_for_remapping must not carry blocker_codes")


@dataclass
class _PrepState:
    blockers: list[str] = field(default_factory=list)
    sqlite_section: dict[str, Any] = field(default_factory=dict)
    cross_module_section: dict[str, Any] = field(default_factory=dict)
    postgres_section: dict[str, Any] = field(default_factory=dict)
    drill_section: dict[str, Any] = field(default_factory=dict)
    source_invalid: bool = False


def prepare_postgres_cutover(
    *,
    sqlite_users_path: Path | str,
    cross_module_db_paths: Mapping[str, Path | str],
    postgres_migrator_dsn: str,
    report_dir: Path | str,
    drill_restore_dsn: str = "",
    drill_work_dir: Path | str | None = None,
) -> CutoverPrepResult:
    """Validate cutover prerequisites without importing or switching runtime."""
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    state = _PrepState()

    users_path = Path(sqlite_users_path)
    before_digest = _file_digest_if_exists(users_path)
    _assess_sqlite_users(users_path, state)
    after_digest = _file_digest_if_exists(users_path)
    if before_digest is not None and after_digest != before_digest:
        state.source_invalid = True
        state.blockers.append("sqlite_source_mutated")
        state.sqlite_section["byte_digest_changed"] = True
    else:
        state.sqlite_section["byte_digest_unchanged"] = True

    known_ids = set(state.sqlite_section.get("user_ids") or [])
    known_usernames = set(state.sqlite_section.get("usernames") or [])
    state.sqlite_section.pop("user_ids", None)
    state.sqlite_section.pop("usernames", None)

    _assess_cross_module_refs(
        cross_module_db_paths,
        known_ids=known_ids,
        known_usernames=known_usernames,
        state=state,
    )
    _assess_postgres_readiness(str(postgres_migrator_dsn), state)
    _run_controlled_drill(
        postgres_migrator_dsn=str(postgres_migrator_dsn or ""),
        drill_restore_dsn=str(drill_restore_dsn or ""),
        drill_work_dir=drill_work_dir or (report_root / "drill"),
        state=state,
    )

    if state.source_invalid:
        status = STATUS_INVALID_SOURCE
    elif state.blockers:
        status = STATUS_BLOCKED
    else:
        status = STATUS_READY_FOR_REMAPPING

    report_path = _write_report(report_root, status=status, state=state)
    blockers = tuple(sorted(set(state.blockers)))
    if status == STATUS_READY_FOR_REMAPPING:
        blockers = ()
    return CutoverPrepResult(status=status, report_path=str(report_path), blocker_codes=blockers)


def discover_schema_identity_columns(migration_sql: Path) -> set[tuple[str, str]]:
    """Return (table, column) pairs that look like identity storage in one migration."""
    text = migration_sql.read_text(encoding="utf-8")
    found: set[tuple[str, str]] = set()
    for match in _CREATE_TABLE_RE.finditer(text):
        table = match.group(1)
        body = match.group(2)
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.upper().startswith(
                ("PRIMARY ", "UNIQUE ", "FOREIGN ", "CHECK ", "CONSTRAINT ")
            ):
                continue
            column = line.split(None, 1)[0].strip("`\"[]")
            if column.lower() in {c.lower() for c in DISCOVERABLE_IDENTITY_COLUMNS}:
                if column.lower() == "storage_key" and table != "signature_assets":
                    continue
                found.add((table, column))
    return found


def catalog_coverage_gaps() -> dict[str, list[str]]:
    """Compare catalog to migration schemas; used by the prevention gate test."""
    missing_from_catalog: list[str] = []
    catalogued = catalog_keys()
    for module in MODULE_DATABASES:
        discovered = discover_schema_identity_columns(module.migration_sql)
        for table, column in sorted(discovered):
            key = (module.module_id, table, column)
            if key not in catalogued:
                missing_from_catalog.append(f"{module.module_id}.{table}.{column}")
    missing_from_schema: list[str] = []
    for ref in IDENTITY_COLUMNS:
        module = module_database_by_id(ref.module_id)
        sql = module.migration_sql.read_text(encoding="utf-8")
        if ref.table not in sql or ref.column not in sql:
            missing_from_schema.append(f"{ref.module_id}.{ref.table}.{ref.column}")
    return {
        "missing_from_catalog": missing_from_catalog,
        "missing_from_schema": missing_from_schema,
    }


def _expected_sqlite_migration_steps() -> tuple[MigrationStep, ...]:
    return tuple(
        MigrationStep(
            version=int(step.version),
            name=str(step.name),
            sql_path=Path(step.sql_path),
        )
        for step in USERMANAGEMENT_DATABASE_CONTRIBUTION.migrations
    )


def _file_digest_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _assess_sqlite_users(path: Path, state: _PrepState) -> None:
    section: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "user_count": 0,
        "issues": [],
    }
    state.sqlite_section = section
    if not path.is_file():
        state.source_invalid = True
        state.blockers.append("sqlite_users_missing")
        section["issues"].append("sqlite_users_missing")
        return
    conn: sqlite3.Connection | None = None
    try:
        conn = _open_sqlite_readonly(path)
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        section["integrity_check"] = integrity if integrity == "ok" else "failed"
        if integrity != "ok":
            state.source_invalid = True
            state.blockers.append("sqlite_integrity_failed")
            section["issues"].append("sqlite_integrity_failed")
            return
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        section["foreign_key_violations"] = len(fk_violations)
        if fk_violations:
            state.source_invalid = True
            state.blockers.append("sqlite_fk_failed")
            section["issues"].append("sqlite_fk_failed")
            return
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        section["user_version"] = user_version

        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "users" not in tables:
            state.source_invalid = True
            state.blockers.append("sqlite_users_table_missing")
            section["issues"].append("sqlite_users_table_missing")
            return
        if "_qm_schema_migrations" not in tables:
            state.source_invalid = True
            state.blockers.append("sqlite_users_unversioned")
            section["issues"].append("sqlite_users_unversioned")
            return
        history = conn.execute(
            "SELECT version, name, checksum FROM _qm_schema_migrations ORDER BY version"
        ).fetchall()
        versions = [int(row["version"]) for row in history]
        section["schema_versions"] = versions
        if not versions or versions[:1] != [1] or versions != list(range(1, len(versions) + 1)):
            state.source_invalid = True
            state.blockers.append("sqlite_users_history_invalid")
            section["issues"].append("sqlite_users_history_invalid")
            return
        if user_version != max(versions) or user_version != len(versions):
            state.source_invalid = True
            state.blockers.append("sqlite_user_version_mismatch")
            section["issues"].append("sqlite_user_version_mismatch")
            return

        expected = _expected_sqlite_migration_steps()
        expected_prefix = [step for step in expected if step.version <= max(versions)]
        if len(history) != len(expected_prefix):
            state.source_invalid = True
            state.blockers.append("sqlite_migration_checksum_mismatch")
            section["issues"].append("sqlite_migration_history_length")
            return
        for row, step in zip(history, expected_prefix, strict=True):
            if (
                int(row["version"]) != step.version
                or str(row["name"]) != step.name
                or str(row["checksum"]) != step.checksum
            ):
                state.source_invalid = True
                state.blockers.append("sqlite_migration_checksum_mismatch")
                section["issues"].append(
                    f"sqlite_migration_checksum_mismatch:{step.version}"
                )
                return

        columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        required = {
            "user_id",
            "username",
            "password",
            "role",
            "is_active",
            "is_qmb",
            "must_change_password",
            "created_at",
            "updated_at",
        }
        if not required.issubset(columns):
            state.source_invalid = True
            state.blockers.append("sqlite_users_schema_unexpected")
            section["issues"].append("sqlite_users_schema_unexpected")
            return
        if max(versions) >= 2 and "deactivated_at" not in columns:
            state.source_invalid = True
            state.blockers.append("sqlite_users_schema_unexpected")
            section["issues"].append("sqlite_missing_deactivated_at")
            return

        rows = conn.execute(
            "SELECT user_id, username, password, role, is_active, is_qmb, must_change_password "
            "FROM users"
        ).fetchall()
        section["user_count"] = len(rows)
        user_ids: list[str] = []
        usernames: list[str] = []
        lower_usernames: dict[str, list[str]] = {}
        unhashed = 0
        invalid_role = 0
        invalid_flag = 0
        empty_id = 0
        for row in rows:
            user_id = str(row["user_id"] or "")
            username = str(row["username"] or "")
            password = str(row["password"] or "")
            role = str(row["role"] or "")
            if not user_id or not username:
                empty_id += 1
            user_ids.append(user_id)
            usernames.append(username)
            lower_usernames.setdefault(username.casefold(), []).append(username)
            if not is_password_hash(password):
                unhashed += 1
            if role not in _VALID_ROLES:
                invalid_role += 1
            for flag_name in ("is_active", "is_qmb", "must_change_password"):
                value = row[flag_name]
                if value not in (0, 1, False, True):
                    invalid_flag += 1
        section["unhashed_password_count"] = unhashed
        section["invalid_role_count"] = invalid_role
        section["invalid_flag_count"] = invalid_flag
        section["empty_identity_count"] = empty_id
        section["duplicate_user_id_count"] = len(user_ids) - len(set(user_ids))
        section["duplicate_username_count"] = len(usernames) - len(set(usernames))
        section["case_collision_group_count"] = sum(
            1 for names in lower_usernames.values() if len(names) > 1
        )
        section["user_ids"] = user_ids
        section["usernames"] = usernames

        if empty_id:
            state.blockers.append("sqlite_empty_identity")
        if section["duplicate_user_id_count"]:
            state.blockers.append("sqlite_duplicate_user_id")
        if section["duplicate_username_count"]:
            state.blockers.append("sqlite_duplicate_username")
        if section["case_collision_group_count"]:
            state.blockers.append("sqlite_username_case_collision")
        if unhashed:
            state.blockers.append("sqlite_unhashed_password")
        if invalid_role:
            state.blockers.append("sqlite_invalid_role")
        if invalid_flag:
            state.blockers.append("sqlite_invalid_flag")
    except Exception as exc:  # noqa: BLE001
        state.source_invalid = True
        state.blockers.append("sqlite_users_invalid")
        section["issues"].append(f"sqlite_users_invalid:{type(exc).__name__}")
    finally:
        if conn is not None:
            conn.close()


def _assess_cross_module_refs(
    paths: Mapping[str, Path | str],
    *,
    known_ids: set[str],
    known_usernames: set[str],
    state: _PrepState,
) -> None:
    modules: dict[str, Any] = {}
    total_nonempty = 0
    total_unresolved = 0
    for module in MODULE_DATABASES:
        path = Path(paths[module.module_id]) if module.module_id in paths else None
        entry: dict[str, Any] = {
            "module_id": module.module_id,
            "path": None if path is None else str(path),
            "present": bool(path and path.is_file()),
            "columns": [],
            "nonempty_reference_count": 0,
            "unresolved_reference_count": 0,
        }
        if path is None or not path.is_file():
            state.blockers.append(f"cross_module_db_missing:{module.module_id}")
            entry["issues"] = ["cross_module_db_missing"]
            modules[module.module_id] = entry
            continue
        conn: sqlite3.Connection | None = None
        try:
            conn = _open_sqlite_readonly(path)
            existing_tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            schema_ok = True
            for ref in IDENTITY_COLUMNS:
                if ref.module_id != module.module_id:
                    continue
                col_stats = _inventory_column(
                    conn,
                    ref,
                    known_ids=known_ids,
                    known_usernames=known_usernames,
                    tables=existing_tables,
                )
                entry["columns"].append(col_stats)
                if col_stats.get("schema_missing"):
                    schema_ok = False
                    state.blockers.append(
                        f"cross_module_schema_unexpected:{module.module_id}."
                        f"{ref.table}.{ref.column}"
                    )
                entry["nonempty_reference_count"] += int(col_stats["nonempty_count"])
                entry["unresolved_reference_count"] += int(col_stats["unresolved_count"])
            if not schema_ok:
                entry["issues"] = ["cross_module_schema_unexpected"]
        except Exception as exc:  # noqa: BLE001
            state.blockers.append(f"cross_module_unreadable:{module.module_id}")
            entry["error"] = type(exc).__name__
            modules[module.module_id] = entry
            continue
        finally:
            if conn is not None:
                conn.close()
        total_nonempty += int(entry["nonempty_reference_count"])
        total_unresolved += int(entry["unresolved_reference_count"])
        if entry["nonempty_reference_count"]:
            state.blockers.append(f"cross_module_refs_present:{module.module_id}")
        if entry["unresolved_reference_count"]:
            state.blockers.append(f"cross_module_refs_unresolved:{module.module_id}")
        modules[module.module_id] = entry
    state.cross_module_section = {
        "modules": modules,
        "total_nonempty_reference_count": total_nonempty,
        "total_unresolved_reference_count": total_unresolved,
    }
    if total_nonempty:
        state.blockers.append("cross_module_refs_nonempty")


def _inventory_column(
    conn: sqlite3.Connection,
    ref: IdentityColumnRef,
    *,
    known_ids: set[str],
    known_usernames: set[str],
    tables: set[str],
) -> dict[str, Any]:
    stats = {
        "table": ref.table,
        "column": ref.column,
        "kind": ref.kind,
        "nonempty_count": 0,
        "unresolved_count": 0,
        "schema_missing": False,
    }
    if ref.table not in tables:
        stats["schema_missing"] = True
        return stats
    columns = {
        str(row["name"])
        for row in conn.execute(f"PRAGMA table_info({ref.table})").fetchall()
    }
    if ref.column not in columns:
        stats["schema_missing"] = True
        return stats
    rows = conn.execute(
        f"SELECT {ref.column} AS value FROM {ref.table} WHERE {ref.column} IS NOT NULL"
    ).fetchall()
    for row in rows:
        raw = row["value"]
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        values = _extract_identity_values(text, ref.kind)
        if not values:
            continue
        stats["nonempty_count"] += len(values)
        for value in values:
            if value in known_ids or value in known_usernames:
                continue
            if ref.kind == "path_with_user":
                owner = value.split("/", 1)[0]
                if owner in known_ids or owner in known_usernames:
                    continue
                stats["unresolved_count"] += 1
                continue
            stats["unresolved_count"] += 1
    return stats


def _extract_identity_values(text: str, kind: str) -> list[str]:
    if kind == "json_user_list":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return [text] if text else []
        if isinstance(payload, list):
            return [str(item).strip() for item in payload if str(item).strip()]
        return [text]
    if kind == "path_with_user":
        return [text] if text else []
    return [text]


def _assess_postgres_readiness(dsn: str, state: _PrepState) -> None:
    section: dict[str, Any] = {
        "dsn_provided": bool(str(dsn).strip()),
        "ready": False,
        "read_only": False,
        "migrator_role_active": False,
        "issues": [],
    }
    state.postgres_section = section
    if not str(dsn).strip():
        state.blockers.append("postgres_dsn_missing")
        section["issues"].append("postgres_dsn_missing")
        return
    try:
        with psycopg.connect(str(dsn)) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            read_only = conn.execute("SHOW transaction_read_only").fetchone()
            section["read_only"] = bool(read_only and str(read_only[0]).lower() == "on")
            if not section["read_only"]:
                state.blockers.append("postgres_read_only_required")
                section["issues"].append("postgres_read_only_required")
                return
            try:
                pgs._activate_migrator_role(conn)  # noqa: SLF001
            except Exception as exc:  # noqa: BLE001 — SET ROLE or current_user check
                state.blockers.append("postgres_migrator_role_required")
                section["issues"].append(
                    f"postgres_migrator_role_required:{type(exc).__name__}"
                )
                return
            section["migrator_role_active"] = True
            identity = database_identity_for_connection(conn)
            section["database_name"] = identity.database_name
            section["identity_digest"] = identity.identity_digest
            if not pgs._history_table_exists(conn):  # noqa: SLF001
                state.blockers.append("postgres_history_missing")
                section["issues"].append("postgres_history_missing")
                return
            applied = pgs._fetch_applied(conn)  # noqa: SLF001
            steps = pgs.discover_migrations()
            target = steps[-1].version
            section["applied_versions"] = [row.version for row in applied]
            section["target_version"] = target
            if not applied or applied[-1].version != target:
                state.blockers.append("postgres_schema_not_ready")
                section["issues"].append("postgres_schema_not_ready")
                return
            try:
                pgs._validate_history_prefix(applied, steps)  # noqa: SLF001
            except pgs.PostgresSchemaError:
                state.blockers.append("postgres_history_prefix_invalid")
                section["issues"].append("postgres_history_prefix_invalid")
                return
            current_fp = pgs._compute_schema_fingerprint(conn)  # noqa: SLF001
            section["schema_fingerprint"] = current_fp
            section["fingerprint_matches"] = current_fp == applied[-1].schema_fingerprint
            if not section["fingerprint_matches"]:
                state.blockers.append("postgres_fingerprint_drift")
                section["issues"].append("postgres_fingerprint_drift")
                return
            try:
                pgs._validate_schema_contracts(  # noqa: SLF001
                    conn,
                    require_history_select=True,
                    require_audit_evidence=True,
                )
            except pgs.PostgresSchemaError as exc:
                state.blockers.append("postgres_contract_invalid")
                section["issues"].append(f"postgres_contract_invalid:{exc}")
                return
            counts = {}
            for table in ("users", "sessions", "audit_events"):
                row = conn.execute(
                    f"SELECT COUNT(*) AS c FROM {pgs.SCHEMA_NAME}.{table}"
                ).fetchone()
                counts[table] = int(row[0])
            section["table_counts"] = counts
            if any(counts[name] > 0 for name in counts):
                state.blockers.append("postgres_target_not_empty")
                section["issues"].append("postgres_target_not_empty")
                return
            section["ready"] = True
    except Exception as exc:  # noqa: BLE001
        state.blockers.append("postgres_readiness_failed")
        section["issues"].append(f"postgres_readiness_failed:{type(exc).__name__}")


def _run_controlled_drill(
    *,
    postgres_migrator_dsn: str,
    drill_restore_dsn: str,
    drill_work_dir: Path | str,
    state: _PrepState,
) -> None:
    if not postgres_migrator_dsn.strip() or not drill_restore_dsn.strip():
        state.blockers.append("drill_params_missing")
        state.drill_section = {
            "ok": False,
            "issues": ["drill_params_missing"],
        }
        return
    postgres = state.postgres_section
    if not postgres.get("ready"):
        state.blockers.append("drill_source_not_ready")
        state.drill_section = {
            "ok": False,
            "issues": ["drill_source_not_ready"],
        }
        return
    try:
        expectation = DrillSourceExpectation(
            identity_digest=str(postgres["identity_digest"]),
            migration_tip=int(postgres["target_version"]),
            schema_fingerprint=str(postgres["schema_fingerprint"]),
        )
    except (KeyError, TypeError, ValueError):
        state.blockers.append("drill_source_not_ready")
        state.drill_section = {
            "ok": False,
            "issues": ["drill_source_not_ready"],
        }
        return
    result = run_postgres_backup_restore_drill(
        source_migrator_dsn=postgres_migrator_dsn,
        restore_target_dsn=drill_restore_dsn,
        expected_source=expectation,
        work_dir=drill_work_dir,
    )
    state.drill_section = dict(result.section)
    if result.evidence_path:
        state.drill_section["evidence_path"] = result.evidence_path
    if not result.ok:
        state.blockers.extend(result.blocker_codes or ("drill_failed",))


def _write_report(report_root: Path, *, status: str, state: _PrepState) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_root / f"ap028-m8-cutover-prep-{stamp}-{uuid4().hex[:12]}.json"
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "blocker_codes": sorted(set(state.blockers)),
        "sqlite_users": state.sqlite_section,
        "cross_module_references": state.cross_module_section,
        "postgres_readiness": state.postgres_section,
        "backup_restore_drill": state.drill_section,
        "notes": [
            "Prep-only statuses: invalid_source, blocked, ready_for_remapping.",
            "Productive PostgreSQL cutover is outside this report.",
            "No passwords, tokens, or password hashes are included.",
            "Non-empty cross-module user references block remapping readiness.",
            "Backup/restore drill must be executed by the controlled use-case.",
        ],
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    lowered = serialized.casefold()
    for needle in ("$2a$", "$2b$", "$2y$", "password_hash", "raw_token"):
        if needle in lowered:
            raise RuntimeError("cutover prep report would leak secret material")
    report_path.write_text(serialized + "\n", encoding="utf-8")
    return report_path
