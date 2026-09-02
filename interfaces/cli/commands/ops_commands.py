from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from qm_platform.blob.backup_orchestrator import BackupOrchestratorError, create_backup
from qm_platform.export import (
    ExportError,
    create_evidence_export,
    create_portability_export,
    load_json_records,
    load_jsonl_records,
)
from qm_platform.logging.diagnostic_bundle import (
    DiagnosticBundleError,
    create_diagnostic_bundle,
)
from qm_platform.runtime.maintenance import (
    MaintenanceError,
    enter_maintenance,
    exit_maintenance,
    start_update_rehearsal,
)
from src.backend.bootstrap import BackendBootstrapError, resolve_usermanagement_postgres_dsn
from src.backend.service_host import drain_and_stop_active_host


def cmd_ops_backup(args) -> int:
    try:
        source_dsn = resolve_usermanagement_postgres_dsn()
        result = create_backup(
            source_dsn=source_dsn,
            metadata_dsn=source_dsn,
            label=getattr(args, "label", None),
            backup_id=getattr(args, "backup_id", None),
        )
    except (BackupOrchestratorError, BackendBootstrapError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "backup_id": result.backup_id,
        "backup_path": result.backup_path,
        "app_release_fingerprint": result.app_release_fingerprint,
        "schema_migration_fingerprint": result.schema_migration_fingerprint,
        "blob_count": result.blob_count,
        "dump_checksum_sha256": result.dump_checksum_sha256,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def cmd_ops_restore_drill(args) -> int:
    root = Path(__file__).resolve().parents[3]
    script = root / "scripts" / "run_ops00_restore_drill.py"
    if not script.is_file():
        print("OPS00 restore-drill runner is missing", file=sys.stderr)
        return 1
    command = [sys.executable, str(script), "--backup-dir", str(args.backup_dir)]
    target_database = getattr(args, "target_database", None)
    if target_database:
        command.extend(["--target-database", str(target_database)])
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


def cmd_ops_maintenance(args) -> int:
    action = getattr(args, "maintenance_action", None)
    try:
        if action == "enter":
            enter_maintenance()
        elif action == "exit":
            exit_maintenance()
        else:
            print("unknown maintenance action", file=sys.stderr)
            return 1
    except MaintenanceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"maintenance": action}, ensure_ascii=True, indent=2))
    return 0


def cmd_ops_update_rehearsal(args) -> int:
    if getattr(args, "abort", False):
        backup_dir = getattr(args, "backup_dir", None)
        if not backup_dir:
            print("--backup-dir is required with --abort", file=sys.stderr)
            return 1
        root = Path(__file__).resolve().parents[3]
        script = root / "scripts" / "run_ops00_update_rehearsal.py"
        if not script.is_file():
            print("OPS00 update-rehearsal runner is missing", file=sys.stderr)
            return 1
        command = [sys.executable, str(script), "--backup-dir", str(args.backup_dir)]
        target_database = getattr(args, "target_database", None)
        if target_database:
            command.extend(["--target-database", str(target_database)])
        completed = subprocess.run(command, check=False)
        return int(completed.returncode)

    candidate_dir = getattr(args, "candidate_release_dir", None)
    if not candidate_dir:
        print("candidate release directory is required without --abort", file=sys.stderr)
        return 1
    try:
        drain_and_stop_active_host()
        source_dsn = resolve_usermanagement_postgres_dsn()
        result = start_update_rehearsal(
            candidate_release_dir=Path(candidate_dir),
            source_dsn=source_dsn,
            metadata_dsn=source_dsn,
        )
    except (MaintenanceError, BackupOrchestratorError, BackendBootstrapError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "backup_id": result.backup_id,
        "backup_path": result.backup_path,
        "prior_release_fingerprint": result.prior_release_fingerprint,
        "candidate_release_fingerprint": result.candidate_release_fingerprint,
        "app_release_fingerprint": result.app_release_fingerprint,
        "schema_migration_fingerprint": result.schema_migration_fingerprint,
        "blob_count": result.blob_count,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def cmd_ops_export(args) -> int:
    kind = getattr(args, "export_kind", None)
    output_dir = Path(args.output_dir)
    try:
        if kind == "portability":
            records = load_json_records(Path(args.records_file))
            result = create_portability_export(records=records, output_dir=output_dir)
        elif kind == "evidence":
            audit_file = getattr(args, "audit_file", None)
            if not audit_file:
                print("--audit-file is required for evidence export", file=sys.stderr)
                return 1
            audit_path = Path(audit_file)
            if not audit_path.is_file():
                raise ExportError("audit records file is missing")
            audit_records = load_jsonl_records(audit_path)
            result = create_evidence_export(audit_records=audit_records, output_dir=output_dir)
        else:
            print("unknown export kind", file=sys.stderr)
            return 1
    except ExportError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "export_id": result.export_id,
        "export_kind": result.export_kind,
        "schema_id": result.schema_id,
        "archive_path": result.archive_path,
        "member_count": result.member_count,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def cmd_ops_diagnostic_bundle(args) -> int:
    output_dir = Path(args.output_dir)
    try:
        postgres_dsn = resolve_usermanagement_postgres_dsn()
    except BackendBootstrapError:
        postgres_dsn = None
    try:
        result = create_diagnostic_bundle(output_dir=output_dir, postgres_dsn=postgres_dsn)
    except DiagnosticBundleError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    payload = {
        "bundle_id": result.bundle_id,
        "schema_id": result.schema_id,
        "archive_path": result.archive_path,
        "member_count": result.member_count,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


def cmd_ops(args) -> int:
    if args.ops_command == "backup":
        return cmd_ops_backup(args)
    if args.ops_command == "restore-drill":
        return cmd_ops_restore_drill(args)
    if args.ops_command == "maintenance":
        return cmd_ops_maintenance(args)
    if args.ops_command == "update-rehearsal":
        return cmd_ops_update_rehearsal(args)
    if args.ops_command == "export":
        return cmd_ops_export(args)
    if args.ops_command == "diagnostic-bundle":
        return cmd_ops_diagnostic_bundle(args)
    print("unknown ops command", file=sys.stderr)
    return 1
