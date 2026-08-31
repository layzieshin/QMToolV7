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
