#!/usr/bin/env python3
"""Fail-closed gate for documents PostgreSQL migrations (AP-029 PG01-A)."""
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

from modules.documents.postgres_schema import (  # noqa: E402
    PostgresSchemaError,
    discover_migrations,
)

PG_MIGRATIONS_REL = Path("modules/documents/postgres/migrations")
PROVISION_REL = Path("modules/documents/postgres/provision_documents_schema.sql")
PACKAGING_BUILD_REL = Path("packaging/build_onedir.py")


def _sha256_text(content: bytes) -> str:
    normalized = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _git_file(root: Path, base_ref: str, relative: str) -> bytes | None:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{base_ref}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if probe.returncode != 0:
        return None
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{relative}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _literal_assignment(path: Path, variable: str) -> object | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if isinstance(node.target, ast.Name) and node.target.id == variable:
            return ast.literal_eval(node.value)
    return None


def _bundled_data_paths(packaging_build_path: Path) -> set[str]:
    entries = _literal_assignment(packaging_build_path, "_BUNDLE_DATA")
    if not isinstance(entries, list):
        return set()
    return {str(source).replace("\\", "/") for source, _target in entries}


def _collect_all_packages(packaging_build_path: Path) -> set[str]:
    entries = _literal_assignment(packaging_build_path, "_COLLECT_ALL")
    if not isinstance(entries, list):
        return set()
    return {str(entry) for entry in entries}


def _migration_version(relative: str) -> int | None:
    name = Path(relative).name
    if len(name) < 4 or not name[:4].isdigit():
        return None
    return int(name[:4])


def _sqlite_discovery_paths(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.glob("modules/*/migrations/*.sql")
    }


def evaluate_documents_postgres_migration_gate(
    *,
    base_ref: str,
    root: Path = ROOT,
) -> dict[str, object]:
    root = root.resolve()
    migrations_dir = root / PG_MIGRATIONS_REL
    provision_path = root / PROVISION_REL
    packaging_build_path = root / PACKAGING_BUILD_REL
    checks: dict[str, bool] = {}
    diagnostics: dict[str, object] = {}

    try:
        discover_migrations(migrations_dir)
        checks["migration_chain_valid"] = True
    except PostgresSchemaError as exc:
        checks["migration_chain_valid"] = False
        diagnostics["migration_chain_error"] = str(exc)

    sqlite_discovered = _sqlite_discovery_paths(root)
    pg_paths = {
        path.relative_to(root).as_posix()
        for path in migrations_dir.glob("*.sql")
    }
    checks["pg_migrations_outside_sqlite_discovery"] = pg_paths.isdisjoint(
        sqlite_discovered
    )
    checks["provision_documents_schema_present"] = provision_path.is_file()

    provision_text = (
        provision_path.read_text(encoding="utf-8") if provision_path.is_file() else ""
    )
    provision_upper = provision_text.upper()
    checks["provision_has_no_passwords"] = (
        "PASSWORD '" not in provision_upper
        and 'PASSWORD "' not in provision_upper
        and "LOGIN PASSWORD" not in provision_upper
    )
    checks["provision_reuses_shared_roles"] = (
        "QMTOOL_MIGRATOR" in provision_upper
        and "QMTOOL_RUNTIME" in provision_upper
        and "CREATE ROLE QMTOOL_MIGRATOR" not in provision_upper
        and "CREATE ROLE QMTOOL_RUNTIME" not in provision_upper
        and "CREATE SCHEMA DOCUMENTS AUTHORIZATION QMTOOL_MIGRATOR" in provision_upper
    )

    verify_result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    base_ref_valid = verify_result.returncode == 0
    checks["base_ref_valid"] = base_ref_valid
    if not base_ref_valid:
        diagnostics["base_ref_error"] = (
            verify_result.stderr.strip() or f"invalid git base ref: {base_ref}"
        )

    list_result = None
    if base_ref_valid:
        list_result = subprocess.run(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                base_ref,
                "--",
                PG_MIGRATIONS_REL.as_posix(),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    base_listing_ok = bool(list_result is not None and list_result.returncode == 0)
    checks["base_listing_ok"] = base_listing_ok

    if not base_ref_valid or not base_listing_ok:
        if base_ref_valid and list_result is not None:
            diagnostics["base_listing_error"] = (
                list_result.stderr.strip()
                or "failed to list PostgreSQL migrations at base ref"
            )
        checks["no_deleted_migrations"] = False
        checks["existing_pg_migrations_immutable"] = False
        checks["pg_migrations_append_only"] = False
    else:
        assert list_result is not None
        base_pg_files = {
            line.strip()
            for line in list_result.stdout.splitlines()
            if line.strip().endswith(".sql")
        }
        deleted = sorted(base_pg_files - pg_paths)
        checks["no_deleted_migrations"] = not deleted
        if deleted:
            diagnostics["deleted_migrations"] = deleted

        unreadable: list[str] = []
        mutated: list[str] = []
        for relative in sorted(base_pg_files & pg_paths):
            previous = _git_file(root, base_ref, relative)
            if previous is None:
                unreadable.append(relative)
                continue
            current = (root / relative).read_bytes()
            if _sha256_text(previous) != _sha256_text(current):
                mutated.append(relative)
        checks["existing_pg_migrations_immutable"] = not unreadable and not mutated
        if unreadable:
            diagnostics["unreadable_base_migrations"] = unreadable
        if mutated:
            diagnostics["mutated_migrations"] = mutated

        base_versions = [
            version
            for relative in base_pg_files
            if (version := _migration_version(relative)) is not None
        ]
        base_max = max(base_versions, default=0)
        non_append = sorted(
            relative
            for relative in pg_paths - base_pg_files
            if (version := _migration_version(relative)) is None
            or version <= base_max
        )
        checks["pg_migrations_append_only"] = not non_append
        if non_append:
            diagnostics["non_append_migrations"] = non_append

    bundled = _bundled_data_paths(packaging_build_path)
    required_bundle = set(pg_paths)
    required_bundle.add(PROVISION_REL.as_posix())
    missing_bundle = sorted(required_bundle - bundled)
    checks["pg_artifacts_are_bundled"] = not missing_bundle
    if missing_bundle:
        diagnostics["missing_bundle_paths"] = missing_bundle

    collect_all = _collect_all_packages(packaging_build_path)
    checks["psycopg_collected_in_bundle"] = (
        "psycopg" in collect_all and "psycopg_binary" in collect_all
    )

    return {
        "ok": all(checks.values()),
        "checks": checks,
        "diagnostics": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Documents PostgreSQL migration gate")
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Git ref for append-only/immutability checks",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_documents_postgres_migration_gate(base_ref=args.base_ref)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
