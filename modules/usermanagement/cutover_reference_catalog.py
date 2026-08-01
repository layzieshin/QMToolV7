"""Declarative catalog of cross-module persistent usermanagement identity refs (AP-028 M8).

Internal only — not part of ``modules.usermanagement.api``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ModuleDatabaseSpec:
    module_id: str
    database_id: str
    default_path: str
    migration_sql: Path


@dataclass(frozen=True)
class IdentityColumnRef:
    module_id: str
    table: str
    column: str
    kind: str  # user_id | username_snapshot | json_user_list | path_with_user | other


MODULE_DATABASES: tuple[ModuleDatabaseSpec, ...] = (
    ModuleDatabaseSpec(
        module_id="documents",
        database_id="documents",
        default_path="storage/documents/documents.db",
        migration_sql=ROOT / "modules/documents/migrations/0001_initial.sql",
    ),
    ModuleDatabaseSpec(
        module_id="training",
        database_id="training",
        default_path="storage/training/training.db",
        migration_sql=ROOT / "modules/training/migrations/0001_initial.sql",
    ),
    ModuleDatabaseSpec(
        module_id="incident_management",
        database_id="incidents",
        default_path="storage/incident_management/incidents.db",
        migration_sql=ROOT / "modules/incident_management/migrations/0001_initial.sql",
    ),
    ModuleDatabaseSpec(
        module_id="signature",
        database_id="signature",
        default_path="storage/signature/templates.db",
        migration_sql=ROOT / "modules/signature/migrations/0001_initial.sql",
    ),
)

IDENTITY_COLUMNS: tuple[IdentityColumnRef, ...] = (
    # documents
    IdentityColumnRef("documents", "document_versions", "owner_user_id", "user_id"),
    IdentityColumnRef("documents", "document_versions", "editors_json", "json_user_list"),
    IdentityColumnRef("documents", "document_versions", "reviewers_json", "json_user_list"),
    IdentityColumnRef("documents", "document_versions", "approvers_json", "json_user_list"),
    IdentityColumnRef("documents", "document_versions", "reviewed_by_json", "json_user_list"),
    IdentityColumnRef("documents", "document_versions", "approved_by_json", "json_user_list"),
    IdentityColumnRef("documents", "document_versions", "review_completed_by", "user_id"),
    IdentityColumnRef("documents", "document_versions", "approval_completed_by", "user_id"),
    IdentityColumnRef("documents", "document_versions", "archived_by", "user_id"),
    IdentityColumnRef("documents", "document_versions", "last_extended_by", "user_id"),
    IdentityColumnRef("documents", "document_versions", "last_actor_user_id", "user_id"),
    IdentityColumnRef("documents", "document_versions", "created_by", "user_id"),
    IdentityColumnRef("documents", "document_read_receipts", "user_id", "user_id"),
    IdentityColumnRef("documents", "document_workflow_comments", "author_display", "other"),
    IdentityColumnRef("documents", "document_workflow_comments", "status_changed_by", "user_id"),
    IdentityColumnRef("documents", "document_pdf_read_sessions", "user_id", "user_id"),
    # training
    IdentityColumnRef("training", "training_user_tags", "user_id", "user_id"),
    IdentityColumnRef("training", "training_manual_assignments", "user_id", "user_id"),
    IdentityColumnRef("training", "training_manual_assignments", "granted_by", "user_id"),
    IdentityColumnRef("training", "training_exemptions", "user_id", "user_id"),
    IdentityColumnRef("training", "training_exemptions", "granted_by", "user_id"),
    IdentityColumnRef("training", "training_assignment_snapshots", "user_id", "user_id"),
    IdentityColumnRef("training", "training_progress", "user_id", "user_id"),
    IdentityColumnRef("training", "training_quiz_bindings", "replaced_by", "user_id"),
    IdentityColumnRef("training", "training_quiz_replacement_history", "confirmed_by", "user_id"),
    IdentityColumnRef("training", "training_quiz_attempts", "user_id", "user_id"),
    IdentityColumnRef("training", "training_comments", "user_id", "user_id"),
    IdentityColumnRef("training", "training_comments", "username_snapshot", "username_snapshot"),
    IdentityColumnRef("training", "training_comments", "resolved_by", "user_id"),
    IdentityColumnRef("training", "training_comments", "inactive_by", "user_id"),
    IdentityColumnRef("training", "training_audit_log", "actor_user_id", "user_id"),
    # incident_management
    IdentityColumnRef("incident_management", "incidents", "reporter_user_id", "user_id"),
    IdentityColumnRef("incident_management", "incident_timeline", "actor_user_id", "user_id"),
    IdentityColumnRef("incident_management", "incident_inquiries", "asked_by_user_id", "user_id"),
    IdentityColumnRef("incident_management", "incident_inquiries", "answered_by_user_id", "user_id"),
    IdentityColumnRef("incident_management", "incident_actions", "owner_user_id", "user_id"),
    IdentityColumnRef("incident_management", "incident_actions", "completed_by_user_id", "user_id"),
    IdentityColumnRef("incident_management", "effectiveness_reviews", "completed_by_user_id", "user_id"),
    IdentityColumnRef("incident_management", "incident_groups", "created_by_user_id", "user_id"),
    IdentityColumnRef(
        "incident_management", "leadership_acknowledgements", "forwarded_by_user_id", "user_id"
    ),
    IdentityColumnRef(
        "incident_management", "leadership_acknowledgements", "leadership_user_id", "user_id"
    ),
    IdentityColumnRef(
        "incident_management", "management_review_batches", "created_by_user_id", "user_id"
    ),
    IdentityColumnRef(
        "incident_management", "management_review_items", "acknowledged_by_user_id", "user_id"
    ),
    IdentityColumnRef("incident_management", "module_role_assignments", "user_id", "user_id"),
    IdentityColumnRef(
        "incident_management", "module_role_assignments", "assigned_by_user_id", "user_id"
    ),
    # signature
    IdentityColumnRef("signature", "signature_assets", "owner_user_id", "user_id"),
    IdentityColumnRef("signature", "signature_assets", "storage_key", "path_with_user"),
    IdentityColumnRef("signature", "user_signature_templates", "owner_user_id", "user_id"),
    IdentityColumnRef("signature", "user_active_signatures", "owner_user_id", "user_id"),
)

# Column names that look like identity storage and must be catalogued when present in schema.
DISCOVERABLE_IDENTITY_COLUMNS = frozenset(
    {
        "user_id",
        "owner_user_id",
        "actor_user_id",
        "reporter_user_id",
        "asked_by_user_id",
        "answered_by_user_id",
        "completed_by_user_id",
        "created_by_user_id",
        "forwarded_by_user_id",
        "leadership_user_id",
        "acknowledged_by_user_id",
        "assigned_by_user_id",
        "last_actor_user_id",
        "granted_by",
        "confirmed_by",
        "replaced_by",
        "resolved_by",
        "inactive_by",
        "created_by",
        "archived_by",
        "review_completed_by",
        "approval_completed_by",
        "last_extended_by",
        "status_changed_by",
        "editors_json",
        "reviewers_json",
        "approvers_json",
        "reviewed_by_json",
        "approved_by_json",
        "username_snapshot",
        "author_display",
        "storage_key",  # only identity-bearing on signature_assets (catalogued)
    }
)


def module_database_by_id(module_id: str) -> ModuleDatabaseSpec:
    for item in MODULE_DATABASES:
        if item.module_id == module_id:
            return item
    raise KeyError(f"unknown module_id: {module_id}")


def catalog_keys() -> frozenset[tuple[str, str, str]]:
    return frozenset((ref.module_id, ref.table, ref.column) for ref in IDENTITY_COLUMNS)
