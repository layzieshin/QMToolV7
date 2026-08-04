"""Single adapter boundary between relational DRAFT and runtime IN_PROGRESS.

Relational workflow-profile storage (J03) uses DRAFT as the canonical editor-phase
start status. The existing Documents workflow engine, DocumentVersionState, and
immutable workflow_profile_json snapshots continue to use IN_PROGRESS.

All translations between those vocabularies must go through this module.
"""
from __future__ import annotations

from .contracts import DocumentStatus

RELATIONAL_EDITOR_STATUS = "DRAFT"
RUNTIME_EDITOR_STATUS = "IN_PROGRESS"


def normalize_legacy_status_for_storage(status: str) -> str:
    """Map legacy/runtime editor status to relational storage vocabulary."""
    value = str(status).strip().upper()
    if value == RUNTIME_EDITOR_STATUS:
        return RELATIONAL_EDITOR_STATUS
    return value


def runtime_status_from_relational(status: str | DocumentStatus) -> DocumentStatus:
    """Map relational status vocabulary onto the engine/runtime DocumentStatus."""
    value = status.value if isinstance(status, DocumentStatus) else str(status).strip().upper()
    if value == RELATIONAL_EDITOR_STATUS:
        return DocumentStatus.IN_PROGRESS
    return DocumentStatus(value)


def runtime_transition_key_from_relational(from_status: str, to_status: str) -> str:
    """Build an engine-compatible signature/transition key from relational statuses."""
    runtime_from = runtime_status_from_relational(from_status).value
    runtime_to = runtime_status_from_relational(to_status).value
    return f"{runtime_from}->{runtime_to}"
