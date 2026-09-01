from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from qm_platform.persistence.postgres_schema import (
    MIGRATIONS_TABLE,
    SCHEMA_NAME,
    discover_migrations,
)
from qm_platform.runtime.maintenance import (
    MaintenanceError,
    is_maintenance_active,
    is_rehearsal_in_progress,
)
from qm_platform.runtime.operation_lock import is_operation_lock_held
from qm_platform.runtime.paths import path_writable, resolve_home_path, runtime_home

from .lifecycle import LifecycleManager

_CHECK_OK = "ok"


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    modules: list[str]
    required_ports: list[str]
    capabilities: dict[str, str]
    failed_modules: dict[str, str]


@dataclass(frozen=True)
class ReadinessReport:
    ready: bool
    checks: dict[str, str]


def build_health_report(lifecycle: LifecycleManager) -> HealthReport:
    module_ids = lifecycle.registered_module_ids()
    required_ports = ["logger", "audit_logger", "event_bus", "settings_service", "license_service"]
    container = lifecycle.container
    ok = all(container.has_port(p) for p in required_ports)
    return HealthReport(
        ok=ok,
        modules=module_ids,
        required_ports=required_ports,
        capabilities=lifecycle.capability_map(),
        failed_modules=lifecycle.failed_modules(),
    )


def build_readiness_report(
    *,
    app_home: Path | None = None,
    postgres_dsn: str | None = None,
) -> ReadinessReport:
    """Installation ops readiness (not WCON00 GAP-16 browser readiness)."""
    home = app_home if app_home is not None else runtime_home()
    postgres_status, migrations_status = _probe_postgres_and_migrations(postgres_dsn)
    checks = {
        "postgres": postgres_status,
        "blob_root": _blob_root_status(home),
        "maintenance": _maintenance_status(home),
        "update_rehearsal": _update_rehearsal_status(home),
        "operation_lock": _operation_lock_status(home),
        "migrations": migrations_status,
    }
    ready = all(value == _CHECK_OK for value in checks.values())
    return ReadinessReport(ready=ready, checks=checks)


def _blob_root_status(home: Path) -> str:
    root = resolve_home_path(home, "storage/platform/blobs")
    if not root.exists():
        return "missing"
    if not root.is_dir():
        return "not_a_directory"
    if not path_writable(root / ".ready_probe"):
        return "not_writable"
    return _CHECK_OK


def _maintenance_status(home: Path) -> str:
    if is_maintenance_active(home):
        return "active"
    return _CHECK_OK


def _update_rehearsal_status(home: Path) -> str:
    try:
        if is_rehearsal_in_progress(home):
            return "candidate_staged"
    except MaintenanceError:
        return "invalid_state"
    return _CHECK_OK


def _operation_lock_status(home: Path) -> str:
    if is_operation_lock_held(home):
        return "held"
    return _CHECK_OK


def _probe_postgres_and_migrations(postgres_dsn: str | None) -> tuple[str, str]:
    dsn = (postgres_dsn or "").strip()
    if not dsn:
        return "missing_dsn", "not_checked"
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
            migrations = _migrations_status(conn)
        return _CHECK_OK, migrations
    except Exception:
        return "unreachable", "not_checked"


def _migrations_status(conn: Any) -> str:
    try:
        steps = discover_migrations()
        if not steps:
            return "unavailable"
        target = steps[-1].version
        row = conn.execute(
            f"SELECT COALESCE(MAX(version), 0) FROM {SCHEMA_NAME}.{MIGRATIONS_TABLE}"
        ).fetchone()
        applied = int(row[0]) if row is not None else 0
    except Exception:
        return "unavailable"
    if applied == target:
        return _CHECK_OK
    if applied < target:
        return "pending"
    return "unexpected"
