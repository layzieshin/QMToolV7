from __future__ import annotations

import argparse
import json

from modules.documents.contracts import SystemRole
from modules.usermanagement.role_policies import is_effective_qmb
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def cmd_users(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    usermanagement = container.get_port("usermanagement_service")
    current_user = usermanagement.get_current_user()
    if current_user is None:
        print("BLOCKED: login required for users commands")
        return 6
    role_map = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    current_role = role_map.get(current_user.role, SystemRole.USER)
    if current_user.role not in role_map:
        print("BLOCKED: login required for users commands")
        return 6
    if current_role != SystemRole.ADMIN and not is_effective_qmb(current_user):
        print("BLOCKED: only QMB or ADMIN may execute users commands")
        return 6

    try:
        if args.users_command == "list":
            rows = usermanagement.list_users()
            payload = [
                {
                    "user_id": row.user_id,
                    "username": row.username,
                    "role": row.role,
                    "is_active": bool(getattr(row, "is_active", True)),
                    "is_qmb": bool(getattr(row, "is_qmb", False)),
                }
                for row in rows
            ]
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.users_command == "create":
            created = usermanagement.create_user(args.username, args.password, args.role)
            print(
                json.dumps(
                    {"user_id": created.user_id, "username": created.username, "role": created.role},
                    ensure_ascii=True,
                )
            )
            return 0
        if args.users_command == "change-password":
            usermanagement.change_password(args.username, args.password)
            print(f"OK: password changed for '{args.username}'")
            return 0
        if args.users_command == "set-active":
            updated = usermanagement.set_user_active(args.username, args.active == "true")
            print(json.dumps({"username": updated.username, "is_active": updated.is_active}, ensure_ascii=True))
            return 0
        if args.users_command == "set-qmb":
            updated = usermanagement.set_user_qmb(args.username, args.enabled == "true")
            print(json.dumps({"username": updated.username, "is_qmb": updated.is_qmb}, ensure_ascii=True))
            return 0
    except (ValueError, KeyError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1

