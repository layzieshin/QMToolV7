"""Explicit local-only Container Swagger demo; it never changes production bootstrap."""
from __future__ import annotations

import argparse
from pathlib import Path

from fastapi.responses import RedirectResponse
from uvicorn import run

from modules.usermanagement.api import UserContext, issue_local_demo_context
from qm_platform.events.event_bus import EventBus
from qm_platform.logging.audit_logger import AuditLogger
from qm_platform.logging.logger_service import LoggerService
from qm_platform.runtime.container import RuntimeContainer
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from src.backend.api import create_app
from src.backend.auth_dependencies import require_user_context_normal
from src.backend.bootstrap import wire_backend_container
from src.backend.container_admin import router as container_admin_router
from src.backend.container_user import router as container_user_router


def demo_user_context() -> UserContext:
    return issue_local_demo_context()


def build_demo_app(app_home: Path):
    """Build an isolated SQLite-backed app with an explicit dependency override only."""
    app_home = Path(app_home).resolve()
    container = RuntimeContainer()
    container.register_port("app_home", app_home)
    # Demo data must remain below the selected app_home even when production
    # path override environment variables are present in the shell.
    container.register_port("container_db_path_override", app_home / "storage/container/container.db")
    container.register_port("container_artifact_files_root_override", app_home / "storage/container/artifacts")
    container.register_port("logger", LoggerService(app_home / "storage/platform/logs/demo.log"))
    container.register_port("audit_logger", AuditLogger(app_home / "storage/platform/logs/audit.log"))
    container.register_port("event_bus", EventBus())
    container.register_port("settings_service", SettingsService(SettingsRegistry()))
    # The module guard needs a confirmed public context, while lifecycle only needs this port to exist.
    container.register_port("usermanagement_service", object())
    wire_backend_container(container)
    app = create_app(container, include_auth_routes=False, demo_mode=True)
    app.dependency_overrides[require_user_context_normal] = demo_user_context
    app.include_router(container_admin_router)
    app.include_router(container_user_router)

    @app.get("/container/demo", include_in_schema=False)
    def landing() -> RedirectResponse:
        return RedirectResponse(url="/container/app", status_code=307)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="QMTool Container LOCAL DEMO – NO PRODUCTION AUTH")
    parser.add_argument("--app-home", type=Path, default=Path("/tmp/qmtool-container-demo"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(build_demo_app(args.app_home), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
