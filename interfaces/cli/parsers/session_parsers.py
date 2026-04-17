from __future__ import annotations
import argparse


def register_session_parsers(sub: argparse._SubParsersAction) -> None:
    sub.add_parser("health", help="Run platform health check")
    sub.add_parser("logs-backup", help="Create logs/audit backup ZIP and rotate log files")
    license_parser = sub.add_parser("license-check", help="Check module license")
    license_parser.add_argument("--module", required=True)
    login_parser = sub.add_parser("login", help="Authenticate against usermanagement module")
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password", required=True)
    sub.add_parser("logout", help="Clear active session")

