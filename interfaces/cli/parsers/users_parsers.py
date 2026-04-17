from __future__ import annotations
import argparse


def register_users_parsers(sub: argparse._SubParsersAction) -> None:
    users_parser = sub.add_parser("users", help="User management operations")
    users_sub = users_parser.add_subparsers(dest="users_command", required=True)
    users_sub.add_parser("list", help="List users")
    user_create = users_sub.add_parser("create", help="Create user")
    user_create.add_argument("--username", required=True)
    user_create.add_argument("--password", required=True)
    user_create.add_argument("--role", choices=["Admin", "QMB", "User"], required=True)
    user_change_password = users_sub.add_parser("change-password", help="Change user password")
    user_change_password.add_argument("--username", required=True)
    user_change_password.add_argument("--password", required=True)
    user_set_active = users_sub.add_parser("set-active", help="Set user active flag")
    user_set_active.add_argument("--username", required=True)
    user_set_active.add_argument("--active", choices=["true", "false"], required=True)
    user_set_qmb = users_sub.add_parser("set-qmb", help="Set user qmb flag")
    user_set_qmb.add_argument("--username", required=True)
    user_set_qmb.add_argument("--enabled", choices=["true", "false"], required=True)

