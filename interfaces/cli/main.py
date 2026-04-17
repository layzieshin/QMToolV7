from __future__ import annotations

import argparse
import os

from interfaces.cli.commands.documents_commands import cmd_documents
from interfaces.cli.commands.platform_commands import cmd_health, cmd_license_check, cmd_logs_backup
from interfaces.cli.commands.runtime_commands import cmd_init, cmd_doctor
from interfaces.cli.commands.session_commands import cmd_login, cmd_logout
from interfaces.cli.commands.settings_commands import cmd_settings
from interfaces.cli.commands.signature_commands import cmd_sign, cmd_sign_visual
from interfaces.cli.commands.training_commands import cmd_training
from interfaces.cli.commands.users_commands import cmd_users
from interfaces.cli.parsers.documents_parsers import register_documents_parsers
from interfaces.cli.parsers.runtime_parsers import register_runtime_parsers
from interfaces.cli.parsers.session_parsers import register_session_parsers
from interfaces.cli.parsers.settings_parsers import register_settings_parsers
from interfaces.cli.parsers.signature_parsers import register_signature_parsers
from interfaces.cli.parsers.training_parsers import register_training_parsers
from interfaces.cli.parsers.users_parsers import register_users_parsers


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QmToolV4 Platform CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    register_session_parsers(sub)
    register_runtime_parsers(sub)
    register_users_parsers(sub)
    register_settings_parsers(sub)
    register_signature_parsers(sub)
    register_documents_parsers(sub)
    register_training_parsers(sub)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "health":
        return cmd_health()
    if args.command == "init":
        return cmd_init(args)
    if args.command == "doctor":
        strict_mode = bool(args.strict or os.environ.get("QMTOOL_DOCTOR_STRICT", "0") == "1")
        return cmd_doctor(strict=strict_mode)
    if args.command == "license-check":
        return cmd_license_check(args.module)
    if args.command == "logs-backup":
        return cmd_logs_backup()
    if args.command == "login":
        return cmd_login(args.username, args.password)
    if args.command == "logout":
        return cmd_logout()
    if args.command == "users":
        return cmd_users(args)
    if args.command == "settings":
        return cmd_settings(args)
    if args.command == "sign-visual":
        return cmd_sign_visual(args)
    if args.command == "sign":
        return cmd_sign(args)
    if args.command == "documents":
        return cmd_documents(args)
    if args.command == "training":
        return cmd_training(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

