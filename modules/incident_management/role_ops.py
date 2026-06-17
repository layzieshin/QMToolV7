"""Module-internal role operations."""
from __future__ import annotations

from . import authorization as auth
from . import eventing
from .contracts import ModuleInternalRole, ModuleRoleAssignment
from .sqlite_repository import SQLiteIncidentRepository


def assign_module_role(
    *,
    repo: SQLiteIncidentRepository,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    target_user_id: str,
    role_name: ModuleInternalRole,
) -> ModuleRoleAssignment:
    auth.require_admin_or_qmb(user)
    now = eventing.utcnow()
    assignment = ModuleRoleAssignment(
        assignment_id=eventing.new_id(),
        user_id=target_user_id,
        role_name=role_name,
        assigned_by_user_id=auth.user_id(user),
        assigned_at=now,
    )
    repo.upsert_module_role(assignment)
    eventing.emit_audit(
        audit_logger,
        action="incident.module_role.assign",
        actor=auth.user_id(user),
        target=target_user_id,
        result="ok",
        reason=role_name.value,
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.role.assigned.v1",
        actor_user_id=auth.user_id(user),
        payload={"user_id": target_user_id, "role_name": role_name.value},
    )
    return assignment


def list_module_roles(
    *,
    repo: SQLiteIncidentRepository,
    user: object,
    role_name: ModuleInternalRole | None = None,
) -> list[ModuleRoleAssignment]:
    auth.require_manage_module_roles(user)
    return repo.list_module_roles(role_name)
