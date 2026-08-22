from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qm_platform.persistence import (
    DataValidationQuery,
    DatabaseEvolutionService,
    DatabaseSpec,
    MigrationStep,
)
from qm_platform.runtime.bootstrap import core_module_contracts
from qm_platform.persistence.platform_settings_contribution import (
    PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
)
from scripts.json_persistence_gate import evaluate_json_persistence_gate


MANIFEST_PATH = ROOT / "qm_platform" / "persistence" / "migration_manifest.json"
REPOSITORY_FILES = (
    ROOT / "modules" / "documents" / "sqlite_repository.py",
    ROOT / "modules" / "registry" / "sqlite_repository.py",
    ROOT / "modules" / "usermanagement" / "sqlite_repository.py",
    ROOT / "modules" / "signature" / "sqlite_repository.py",
    ROOT / "modules" / "training" / "training_tag_repository.py",
    ROOT / "modules" / "training" / "training_override_repository.py",
    ROOT / "modules" / "training" / "training_snapshot_repository.py",
    ROOT / "modules" / "training" / "training_quiz_repository.py",
    ROOT / "modules" / "training" / "training_comment_repository.py",
    ROOT / "modules" / "training" / "training_report_repository.py",
    ROOT / "modules" / "incident_management" / "sqlite_repository.py",
)
PACKAGING_BUILD_PATH = ROOT / "packaging" / "build_onedir.py"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _registered_specs(root: Path) -> tuple[DatabaseSpec, ...]:
    specs = []
    contributions = []
    for contract in core_module_contracts():
        contributions.extend(contract.database_contributions)
    contributions.append(PLATFORM_SETTINGS_DATABASE_CONTRIBUTION)
    for contribution in contributions:
        specs.append(
            DatabaseSpec(
                database_id=contribution.database_id,
                path=root / f"{contribution.database_id}.db",
                migrations=tuple(
                    MigrationStep(
                        version=item.version,
                        name=item.name,
                        sql_path=item.sql_path.resolve(),
                    )
                    for item in contribution.migrations
                ),
                validation_queries=tuple(
                    DataValidationQuery(name=item.name, sql=item.sql)
                    for item in contribution.validation_queries
                ),
            )
        )
    return tuple(sorted(specs, key=lambda item: item.database_id))


def _table_counts(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path)) as conn:
        tables = [
            str(row[0])
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                  AND name != '_qm_schema_migrations'
                ORDER BY name
                """
            ).fetchall()
        ]
        return {
            table: int(
                conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
            for table in tables
        }


def _git_file(base_ref: str, path: Path) -> bytes | None:
    relative = path.resolve().relative_to(ROOT).as_posix()
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


def evaluate_database_migration_gate(
    *,
    base_ref: str | None = None,
) -> dict[str, object]:
    checks: dict[str, bool] = {}
    diagnostics: dict[str, object] = {}
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    temp_root = ROOT / "build"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="qmtool-database-gate-",
        dir=temp_root,
    ) as tmp:
        root = Path(tmp)
        specs = _registered_specs(root)
        registered_paths: set[str] = set()
        manifest_ok = True
        immutable_ok = True
        fixtures_ok = True

        for spec in specs:
            entries = manifest.get(spec.database_id)
            if not isinstance(entries, list) or len(entries) != len(spec.migrations):
                manifest_ok = False
                continue
            for step, entry in zip(spec.migrations, entries, strict=True):
                relative = step.sql_path.relative_to(ROOT).as_posix()
                registered_paths.add(relative)
                if (
                    int(entry.get("version", -1)) != step.version
                    or str(entry.get("name")) != step.name
                    or str(entry.get("path")) != relative
                    or str(entry.get("sha256")) != step.checksum
                ):
                    manifest_ok = False
                if base_ref and set(base_ref) != {"0"}:
                    previous = _git_file(base_ref, step.sql_path)
                    current = _git_file("HEAD", step.sql_path)
                    if (
                        previous is not None
                        and current is not None
                        and _sha256_bytes(previous) != _sha256_bytes(current)
                    ):
                        immutable_ok = False

            if spec.target_version > 1:
                fixture = (
                    ROOT
                    / "tests"
                    / "fixtures"
                    / "database_migrations"
                    / spec.database_id
                    / f"v{spec.target_version - 1:04d}.db"
                )
                if not fixture.is_file():
                    fixtures_ok = False
                    continue
                upgrade_path = root / f"{spec.database_id}-upgrade.db"
                shutil.copy2(fixture, upgrade_path)
                before = _table_counts(upgrade_path)
                upgrade_spec = DatabaseSpec(
                    database_id=spec.database_id,
                    path=upgrade_path,
                    migrations=spec.migrations,
                    validation_queries=spec.validation_queries,
                )
                service = DatabaseEvolutionService(
                    app_home=root,
                    backup_root=root / "upgrade-backups",
                )
                service.migrate((upgrade_spec,), reason="ci_upgrade_fixture")
                after = _table_counts(upgrade_path)
                if any(after.get(table) != count for table, count in before.items()):
                    fixtures_ok = False

        discovered_paths = {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.glob("modules/*/migrations/*.sql")
        } | {
            path.relative_to(ROOT).as_posix()
            for path in ROOT.glob("qm_platform/**/migrations/*.sql")
            if "postgres" not in path.parts
        }
        checks["manifest_matches_registered_migrations"] = manifest_ok
        checks["all_migration_files_are_registered"] = (
            discovered_paths == registered_paths
        )
        bundled_paths = _bundled_data_paths()
        missing_bundle_paths = sorted(registered_paths - bundled_paths)
        checks["all_migrations_are_bundled"] = not missing_bundle_paths
        if missing_bundle_paths:
            diagnostics["missing_bundle_paths"] = missing_bundle_paths
        checks["applied_migrations_immutable"] = immutable_ok
        checks["upgrade_fixtures_preserve_rows"] = fixtures_ok
        checks["no_parallel_module_schema_files"] = not any(
            ROOT.glob("modules/*/schema.sql")
        )

        forbidden = ("ALTER TABLE", "executescript(", "_ensure_schema")
        repository_findings = [
            f"{path.relative_to(ROOT)}:{token}"
            for path in REPOSITORY_FILES
            for token in forbidden
            if token in path.read_text(encoding="utf-8")
        ]
        checks["repositories_contain_no_schema_mutation"] = not repository_findings
        if repository_findings:
            diagnostics["repository_schema_mutation"] = repository_findings

        service = DatabaseEvolutionService(
            app_home=root,
            backup_root=root / "fresh-backups",
        )
        first = service.migrate(specs, reason="ci_fresh_install")
        second = service.migrate(specs, reason="ci_idempotence")
        checks["all_databases_build_from_empty"] = bool(first["ok"]) and all(
            status.ok for status in service.statuses(specs)
        )
        checks["second_migration_run_is_noop"] = second["backup_id"] is None

        json_gate = evaluate_json_persistence_gate(
            ROOT,
            mode="repo",
            base_ref=base_ref or "HEAD",
        )
        checks["no_unregistered_json_persistence"] = bool(
            json_gate.get("checks", {}).get("no_unregistered_json_persistence")
        ) and bool(json_gate.get("ok"))
        if not checks["no_unregistered_json_persistence"]:
            diagnostics["json_persistence"] = {
                "findings": json_gate.get("findings", []),
                "diagnostics": json_gate.get("diagnostics", {}),
            }

    ok = all(checks.values())
    return {
        "ok": ok,
        "checks": checks,
        "diagnostics": diagnostics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate all registered SQLite migration chains"
    )
    parser.add_argument("--base-ref")
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = evaluate_database_migration_gate(base_ref=args.base_ref)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if bool(payload["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
