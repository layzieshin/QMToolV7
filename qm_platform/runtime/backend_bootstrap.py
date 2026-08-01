"""Slim Usermanagement wiring for the backend host (AP-028 M5).

Does not start Documents/Training/Registry/Incidents or run SQLite evolution.
"""
from __future__ import annotations

from modules.usermanagement.api import ensure_postgres_schema_ready
from modules.usermanagement.module import create_usermanagement_module_contract

from .container import RuntimeContainer
from .lifecycle import LifecycleManager


def wire_backend_usermanagement(container: RuntimeContainer) -> LifecycleManager:
    """Prepare, wire, and start only the Usermanagement module contract."""
    if not container.has_port("usermanagement_postgres_dsn"):
        raise RuntimeError("backend requires usermanagement_postgres_dsn")

    ensure_postgres_schema_ready(container)

    lifecycle = LifecycleManager(container)
    lifecycle.prepare(create_usermanagement_module_contract())
    lifecycle.wire("usermanagement")
    lifecycle.start(strict=True)
    return lifecycle
