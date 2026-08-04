"""Internal Documents bootstrap provenance derived from preflight DatabaseStatus.

Not a public module API. Documents wiring owns the J03 classification rule;
the platform only stores generic pre-migrate DatabaseStatus values.
"""
from __future__ import annotations

from enum import Enum
from typing import Mapping

from qm_platform.persistence.database_evolution import (
    DATABASE_PREFLIGHT_STATUSES_PORT,
    DatabaseStatus,
)


class DocumentsBootstrapProvenance(str, Enum):
    FRESH_INSTALL = "fresh_install"
    PRE_J03_UPGRADE = "pre_j03_upgrade"
    POST_J03_SCHEMA = "post_j03_schema"


# Schema version introduced by modules/documents/migrations/0002_workflow_profiles.sql
_J03_WORKFLOW_PROFILES_SCHEMA_VERSION = 2


def derive_documents_bootstrap_provenance(status: DatabaseStatus) -> DocumentsBootstrapProvenance:
    """Map a pre-migrate Documents DatabaseStatus onto bootstrap provenance."""
    if status.database_id != "documents":
        raise ValueError(f"expected documents status, got {status.database_id}")

    if status.state == "missing":
        return DocumentsBootstrapProvenance.FRESH_INSTALL

    if status.state == "adoptable_v1":
        return DocumentsBootstrapProvenance.PRE_J03_UPGRADE

    if status.current_version >= _J03_WORKFLOW_PROFILES_SCHEMA_VERSION:
        return DocumentsBootstrapProvenance.POST_J03_SCHEMA

    if status.current_version == 1 and status.state in {"pending", "current"}:
        return DocumentsBootstrapProvenance.PRE_J03_UPGRADE

    raise ValueError(
        f"cannot derive documents bootstrap provenance from state={status.state} "
        f"version={status.current_version} ({status.detail or 'no detail'})"
    )


def resolve_documents_bootstrap_provenance(container) -> DocumentsBootstrapProvenance:
    """Read generic preflight statuses and apply Documents-owned J03 classification."""
    if not container.has_port(DATABASE_PREFLIGHT_STATUSES_PORT):
        raise RuntimeError(
            "database_preflight_statuses is required; capture DatabaseStatus "
            "for all core databases before runtime_preflight migrate"
        )
    statuses = container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
    if not isinstance(statuses, Mapping):
        raise RuntimeError(
            f"database_preflight_statuses must be a mapping, got {type(statuses)!r}"
        )
    status = statuses.get("documents")
    if status is None:
        raise RuntimeError("database_preflight_statuses is missing documents status")
    if not isinstance(status, DatabaseStatus):
        raise RuntimeError(
            f"documents preflight status must be DatabaseStatus, got {type(status)!r}"
        )
    return derive_documents_bootstrap_provenance(status)
