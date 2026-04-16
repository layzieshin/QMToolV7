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

