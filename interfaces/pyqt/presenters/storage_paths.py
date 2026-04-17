from __future__ import annotations

from pathlib import Path


def artifacts_root(container: object, app_home: Path) -> Path:
    if not getattr(container, "has_port")("settings_service"):
        return app_home / "storage" / "documents" / "artifacts"
    settings_service = getattr(container, "get_port")("settings_service")
    docs_settings = settings_service.get_module_settings("documents")
    raw_root = docs_settings.get("artifacts_root", "storage/documents/artifacts")
    root = Path(raw_root)
    return root if root.is_absolute() else app_home / root


def workflow_profiles_file(container: object, app_home: Path) -> Path:
    if not getattr(container, "has_port")("settings_service"):
        return app_home / "modules" / "documents" / "workflow_profiles.json"
    cfg = getattr(container, "get_port")("settings_service").get_module_settings("documents")
    raw = str(cfg.get("profiles_file", "modules/documents/workflow_profiles.json")).strip()
    path = Path(raw)
    return path if path.is_absolute() else app_home / path


def platform_logs_root(app_home: Path) -> Path:
    return app_home / "storage" / "platform" / "logs"
