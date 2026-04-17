from __future__ import annotations

import argparse
import json

from modules.documents.contracts import SystemRole
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.settings.settings_service import SettingsService
from modules.usermanagement.role_policies import is_effective_qmb

from interfaces.cli.bootstrap import build_container


def cmd_settings(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    settings_service: SettingsService = container.get_port("settings_service")
    usermanagement = container.get_port("usermanagement_service")
    current_user = usermanagement.get_current_user()
    if current_user is None:
        print("BLOCKED: login required for settings commands")
        return 6
    role_map = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    current_role = role_map.get(current_user.role)
    if current_role == SystemRole.USER and is_effective_qmb(current_user):
        current_role = SystemRole.QMB
    if current_role is None:
        print("BLOCKED: login required for settings commands")
        return 6

    try:
        if args.settings_command == "list-modules":
            payload = settings_service.registry.list_module_ids()
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.settings_command == "get":
            payload = settings_service.get_module_settings(args.module)
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.settings_command == "set":
            if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
                print("BLOCKED: only QMB or ADMIN may set settings")
                return 6
            values = json.loads(args.values_json)
            if not isinstance(values, dict):
                print("BLOCKED: --values-json must be a JSON object")
                return 6
            settings_service.set_module_settings(
                args.module,
                values,
                acknowledge_governance_change=bool(args.acknowledge_governance_change),
            )
            persisted = settings_service.get_module_settings(args.module)
            print(json.dumps(persisted, ensure_ascii=True))
            return 0
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1

