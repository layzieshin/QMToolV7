#!/usr/bin/env python3
"""Fail-closed gate for Usermanagement PostgreSQL migrations (AP-028 M3)."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.usermanagement.postgres_schema import (  # noqa: E402
    MIGRATIONS_DIR,
    PROVISION_ROLES_PATH,
    PostgresSchemaError,
    discover_migrations,
)

PACKAGING_BUILD_PATH = ROOT / "packaging" / "build_onedir.py"
PG_MIGRATION_GLOB = "modules/usermanagement/postgres/migrations/*.sql"
PROVISION_REL = "modules/usermanagement/postgres/provision_roles.sql"


def _sha256_text(content: bytes) -> str:
    normalized = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _git_file(base_ref: str, relative: str) -> bytes | None:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{base_ref}:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return result.stdout


def _bundled_data_paths() -> set[str]:
    tree = ast.parse(
        PACKAGING_BUILD_PATH.read_text(encoding="utf-8"),
        filename=str(PACKAGING_BUILD_PATH),
    )
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "_BUNDLE_DATA":
            continue
        entries = ast.literal_eval(node.value)
        return {str(source).replace("\\", "/") for source, _target in entries}
    return set()


def _collect_all_packages() -> set[str]:
    tree = ast.parse(
        PACKAGING_BUILD_PATH.read_text(encoding="utf-8"),
        filename=str(PACKAGING_BUILD_PATH),
    )
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "_COLLECT_ALL":
            continue
        return set(ast.literal_eval(node.value))
    return set()


def evaluate_postgres_migration_gate(*, base_ref: str) -> dict:
    checks: dict[str, bool] = {}
    diagnostics: dict[str, object] = {}

    try:
        steps = discover_migrations()
        checks["migration_chain_valid"] = True
    except PostgresSchemaError as exc:
        checks["migration_chain_valid"] = False
        diagnostics["migration_chain_error"] = str(exc)
        steps = ()

    sqlite_discovered = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob("modules/*/migrations/*.sql")
    }
    pg_paths = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.glob(PG_MIGRATION_GLOB)
    }
    checks["pg_migrations_outside_sqlite_discovery"] = pg_paths.isdisjoint(sqlite_discovered)
    checks["provision_roles_present"] = PROVISION_ROLES_PATH.is_file()

    provision_text = (
        PROVISION_ROLES_PATH.read_text(encoding="utf-8") if PROVISION_ROLES_PATH.is_file() else ""
    )
    checks["provision_has_no_passwords"] = (
        "PASSWORD '" not in provision_text.upper()
        and 'PASSWORD "' not in provision_text.upper()
        and "LOGIN PASSWORD" not in provision_text.upper()
    )
    checks["provision_roles_are_nologin"] = (
        provision_text.count("NOLOGIN") >= 2
        and "LOGIN PASSWORD" not in provision_text.upper()
        and "CREATE ROLE qmtool_migrator LOGIN" not in provision_text
        and "CREATE ROLE qmtool_runtime LOGIN" not in provision_text
    )

    immutable_ok = True
    append_only_ok = True
    base_versions: list[int] = []
    for path in sorted((ROOT / "modules/usermanagement/postgres/migrations").glob("*.sql")):
        relative = path.relative_to(ROOT).as_posix()
        current = path.read_bytes()
        previous = _git_file(base_ref, relative)
        if previous is None:
            # New file — must append after base max version
            continue
        if _sha256_text(previous) != _sha256_text(current):
            immutable_ok = False
            diagnostics.setdefault("mutated_migrations", []).append(relative)  # type: ignore[union-attr]
        # track base versions
        name = path.name
        if len(name) >= 4 and name[:4].isdigit():
            base_versions.append(int(name[:4]))

    base_pg_files = []
    list_result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", base_ref, "modules/usermanagement/postgres/migrations"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if list_result.returncode == 0 and list_result.stdout.strip():
        base_pg_files = [line.strip() for line in list_result.stdout.splitlines() if line.strip()]

    base_max = 0
    for relative in base_pg_files:
        name = Path(relative).name
        if len(name) >= 4 and name[:4].isdigit():
            base_max = max(base_max, int(name[:4]))

    for step in steps:
        relative = step.sql_path.relative_to(ROOT).as_posix()
        if relative in base_pg_files:
            continue
        if step.version <= base_max:
            append_only_ok = False
            diagnostics.setdefault("non_append_migrations", []).append(relative)  # type: ignore[union-attr]

    checks["existing_pg_migrations_immutable"] = immutable_ok
    checks["pg_migrations_append_only"] = append_only_ok

    bundled = _bundled_data_paths()
    required_bundle = set(pg_paths)
    required_bundle.add(PROVISION_REL)
    missing_bundle = sorted(required_bundle - bundled)
    checks["pg_artifacts_are_bundled"] = not missing_bundle
    if missing_bundle:
        diagnostics["missing_bundle_paths"] = missing_bundle

    collect_all = _collect_all_packages()
    checks["psycopg_collected_in_bundle"] = "psycopg" in collect_all and "psycopg_binary" in collect_all

    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "diagnostics": diagnostics}


def main() -> int:
    parser = argparse.ArgumentParser(description="Usermanagement PostgreSQL migration gate")
    parser.add_argument("--base-ref", required=True, help="Git ref for append-only/immutability checks")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_postgres_migration_gate(base_ref=args.base_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
