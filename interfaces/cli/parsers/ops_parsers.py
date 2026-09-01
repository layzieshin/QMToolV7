from __future__ import annotations

import argparse


def register_ops_parsers(sub: argparse._SubParsersAction) -> None:
    ops_parser = sub.add_parser("ops", help="PostgreSQL + blob operator commands (OPS00)")
    ops_sub = ops_parser.add_subparsers(dest="ops_command", required=True)

    backup_parser = ops_sub.add_parser("backup", help="Create a sealed PostgreSQL + blob backup set")
    backup_parser.add_argument("--label", help="Optional backup set label")
    backup_parser.add_argument("--backup-id", help="Optional backup set identifier")

    restore_parser = ops_sub.add_parser(
        "restore-drill",
        help="Run the guarded Slot-2 restore drill against a sealed backup set",
    )
    restore_parser.add_argument(
        "--backup-dir",
        required=True,
        help="Path to a sealed backup set directory under QMTOOL_HOME/backups/",
    )
    restore_parser.add_argument(
        "--target-database",
        help="Isolated restore database name (must start with qmtool_ops00_restore_)",
    )

    maintenance_parser = ops_sub.add_parser(
        "maintenance",
        help="Enter or exit installation maintenance mode (OPS00-D)",
    )
    maintenance_sub = maintenance_parser.add_subparsers(
        dest="maintenance_action", required=True
    )
    maintenance_sub.add_parser("enter", help="Enable maintenance mode")
    maintenance_sub.add_parser("exit", help="Disable maintenance mode")

    rehearsal_parser = ops_sub.add_parser(
        "update-rehearsal",
        help="Controlled update rehearsal start or abort (OPS00-D)",
    )
    rehearsal_parser.add_argument(
        "--abort",
        action="store_true",
        help="Abort rehearsal: restore prior release tree and sealed backup set",
    )
    rehearsal_parser.add_argument(
        "--backup-dir",
        help="Sealed backup set directory (required with --abort)",
    )
    rehearsal_parser.add_argument(
        "--target-database",
        help="Isolated restore database name for abort (must start with qmtool_ops00_restore_)",
    )
    rehearsal_parser.add_argument(
        "--candidate-release-dir",
        help="Candidate release tree directory containing identity (required without --abort)",
    )

    export_parser = ops_sub.add_parser(
        "export",
        help="Portability or Nachweis export (not a technical backup)",
    )
    export_sub = export_parser.add_subparsers(dest="export_kind", required=True)
    portability = export_sub.add_parser(
        "portability",
        help="Create a schema-allowlisted portability ZIP",
    )
    portability.add_argument("--records-file", required=True, help="JSON array of portability records")
    portability.add_argument("--output-dir", required=True, help="Directory for the export ZIP")
    evidence = export_sub.add_parser(
        "evidence",
        help="Create a readable allowlisted Nachweis ZIP",
    )
    evidence.add_argument(
        "--audit-file",
        required=True,
        help="JSONL allowlisted audit records for Nachweis (not technical logs)",
    )
    evidence.add_argument("--output-dir", required=True, help="Directory for the export ZIP")
