"""Thin CLI wrapper for AP-028 M8 cutover prep (no import/SQL/mapping logic)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.usermanagement import api as um_api  # noqa: E402
from qm_platform.runtime.container import RuntimeContainer  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AP-028 M8 prepare_postgres_cutover (prep-only)."
    )
    parser.add_argument("--sqlite-users", required=True, type=Path)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--postgres-migrator-dsn", required=True)
    parser.add_argument("--drill-restore-dsn", required=True)
    parser.add_argument("--drill-work-dir", type=Path, default=None)
    parser.add_argument("--documents-db", required=True, type=Path)
    parser.add_argument("--training-db", required=True, type=Path)
    parser.add_argument("--incident-management-db", required=True, type=Path)
    parser.add_argument("--signature-db", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cross = {
        "documents": args.documents_db,
        "training": args.training_db,
        "incident_management": args.incident_management_db,
        "signature": args.signature_db,
    }
    container = RuntimeContainer()
    try:
        result = um_api.prepare_postgres_cutover(
            container,
            sqlite_users_path=args.sqlite_users,
            cross_module_db_paths=cross,
            postgres_migrator_dsn=args.postgres_migrator_dsn,
            report_dir=args.report_dir,
            drill_restore_dsn=args.drill_restore_dsn,
            drill_work_dir=args.drill_work_dir or (args.report_dir / "drill"),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result.status,
                "report_path": result.report_path,
                "blocker_codes": list(result.blocker_codes),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.status == "ready_for_remapping" else 1


if __name__ == "__main__":
    raise SystemExit(main())
