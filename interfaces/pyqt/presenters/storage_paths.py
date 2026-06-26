from __future__ import annotations

from pathlib import Path


def workflow_profiles_file(container: object, app_home: Path) -> Path:
    if not getattr(container, "has_port")("settings_service"):
        return app_home / "modules" / "documents" / "workflow_profiles.json"
    cfg = getattr(container, "get_port")("settings_service").get_module_settings("documents")
    raw = str(cfg.get("profiles_file", "modules/documents/workflow_profiles.json")).strip()
    path = Path(raw)
    return path if path.is_absolute() else app_home / path


def platform_logs_root(app_home: Path) -> Path:
    return app_home / "storage" / "platform" / "logs"
