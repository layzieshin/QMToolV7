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

