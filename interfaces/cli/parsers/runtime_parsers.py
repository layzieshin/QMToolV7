from __future__ import annotations
import argparse


def register_runtime_parsers(sub: argparse._SubParsersAction) -> None:
    init_parser = sub.add_parser("init", help="Initialize runtime paths and admin seed")
    init_parser.add_argument("--app-home")
    init_parser.add_argument("--users-db-path")
    init_parser.add_argument("--documents-db-path")
    init_parser.add_argument("--artifacts-root")
    init_parser.add_argument("--registry-db-path")
    init_parser.add_argument("--admin-username", default="admin")
    init_parser.add_argument("--admin-password")
    init_parser.add_argument("--non-interactive", action="store_true")
    doctor_parser = sub.add_parser("doctor", help="Check runtime readiness and critical paths")
    doctor_parser.add_argument("--strict", action="store_true", help="Enable strict production security checks")

    database_parser = sub.add_parser("database", help="Inspect and maintain application databases")
    database_sub = database_parser.add_subparsers(dest="database_command", required=True)
    database_sub.add_parser("status", help="Show database versions and integrity")
    migrate_parser = database_sub.add_parser("migrate", help="Run pending forward migrations")
    migrate_parser.add_argument("--dry-run", action="store_true")
    database_sub.add_parser("backups", help="List complete database backup sets")
    restore_parser = database_sub.add_parser("restore", help="Restore a complete database backup set")
    restore_parser.add_argument("--backup-id", required=True)

