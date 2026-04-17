from __future__ import annotations

from pathlib import Path

from interfaces.pyqt.presenters.storage_paths import platform_logs_root
from modules.documents.contracts import DocumentStatus
from qm_platform.runtime.container import RuntimeContainer


def tail_file(path: Path, max_lines: int = 400) -> str:
    if not path.exists():
        return f"Datei nicht gefunden: {path}"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def build_functional_summary(registry_api, pool_api) -> dict[str, object]:
    entries = registry_api.list_entries()
    by_status: dict[str, int] = {}
    for status in DocumentStatus:
        by_status[status.value] = len(pool_api.list_by_status(status))
    return {
        "registry_entries": len(entries),
        "status_buckets": by_status,
        "registry_preview": entries[:50],
    }


def build_doc_history(registry_api, pool_api, documents_service, doc_id: str, version: int) -> dict[str, object]:
    return {
        "registry": registry_api.get_entry(doc_id),
        "header": pool_api.get_header(doc_id),
        "state": documents_service.get_document_version(doc_id, version),
        "artifacts": pool_api.list_artifacts(doc_id, version),
    }


def build_technical_rows(app_home: Path | str) -> list[tuple[str, str, str, str]]:
    app_home_path = Path(app_home)
    log_dir = platform_logs_root(app_home_path)
    platform_log = log_dir / "platform.log"
    audit_log = log_dir / "audit.log"
    rows: list[tuple[str, str, str, str]] = []
    for line in tail_file(platform_log).splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|", 3)]
            if len(parts) == 4:
                rows.append((parts[0], parts[1], parts[2], parts[3]))
                continue
        rows.append(("", "INFO", "platform", line))
    for line in tail_file(audit_log).splitlines():
        rows.append(("", "AUDIT", "audit", line))
    return rows


def build_admin_checks(container: RuntimeContainer, license_service, settings_service) -> dict[str, object]:
    app_home = Path(container.get_port("app_home"))
    cfg_docs = settings_service.get_module_settings("documents")
    cfg_users = settings_service.get_module_settings("usermanagement")
    cfg_reg = settings_service.get_module_settings("registry")
    return {
        "app_home": str(app_home),
        "license": license_service.validate(),
        "required_ports": {
            "logger": container.has_port("logger"),
            "audit_logger": container.has_port("audit_logger"),
            "event_bus": container.has_port("event_bus"),
            "settings_service": container.has_port("settings_service"),
            "license_service": container.has_port("license_service"),
        },
        "paths": {
            "users_db_path": cfg_users.get("users_db_path"),
            "documents_db_path": cfg_docs.get("documents_db_path"),
            "registry_db_path": cfg_reg.get("registry_db_path"),
        },
    }
