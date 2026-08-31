from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from qm_platform.blob.backup_orchestrator import BackupOrchestratorError, create_backup
from src.backend.bootstrap import BackendBootstrapError, resolve_usermanagement_postgres_dsn


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
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "run_ops00_restore_drill.py"
    command = [sys.executable, str(script), "--backup-dir", str(args.backup_dir)]
    target_database = getattr(args, "target_database", None)
    if target_database:
        command.extend(["--target-database", str(target_database)])
    completed = subprocess.run(command, check=False)
    return int(completed.returncode)


def cmd_ops(args) -> int:
    if args.ops_command == "backup":
        return cmd_ops_backup(args)
    if args.ops_command == "restore-drill":
        return cmd_ops_restore_drill(args)
    print("unknown ops command", file=sys.stderr)
    return 1
