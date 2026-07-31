from __future__ import annotations

import json
from dataclasses import asdict

from interfaces.cli.bootstrap import build_container
from qm_platform.persistence.database_evolution import DatabaseEvolutionError
from qm_platform.runtime import bootstrap as runtime_bootstrap


def _database_runtime():
    container = build_container()
    lifecycle = runtime_bootstrap.prepare_core_modules(container)
    service, specs = runtime_bootstrap.configure_database_evolution(container, lifecycle)
    return service, specs


def cmd_database(args) -> int:
    try:
        service, specs = _database_runtime()
        if args.database_command == "status":
            statuses = service.statuses(specs)
            ok = (
                not service.has_interrupted_migration
                and all(status.ok for status in statuses)
            )
            print(
                json.dumps(
                    {
                        "ok": ok,
                        "interrupted_migration": service.has_interrupted_migration,
                        "databases": [asdict(status) for status in statuses],
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if ok else 8

        if args.database_command == "migrate":
            result = service.migrate(
                specs,
                dry_run=bool(args.dry_run),
                reason="cli_database_migrate",
            )
            print(json.dumps(result, ensure_ascii=True))
            return 0

        if args.database_command == "backups":
            print(
                json.dumps(
                    {
                        "ok": True,
                        "backups": [
                            asdict(backup) for backup in service.list_backups()
                        ],
                    },
                    ensure_ascii=True,
                )
            )
            return 0

        if args.database_command == "restore":
            result = service.restore(args.backup_id, specs=specs)
            print(json.dumps(result, ensure_ascii=True))
            return 0
    except (DatabaseEvolutionError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
        return 9
    return 2
