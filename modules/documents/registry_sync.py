"""Registry projection sync for documents module.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations

from .contracts import DocumentVersionState
from qm_platform.events.event_envelope import EventEnvelope


def sync_registry(
    registry_projection_api: object | None,
    state: DocumentVersionState,
    event: EventEnvelope | None,
) -> None:
    if registry_projection_api is None:
        return
    apply = getattr(registry_projection_api, "apply_documents_projection", None)
    if not callable(apply):
        return
    release_mode = state.workflow_profile.release_evidence_mode if state.workflow_profile is not None else "WORKFLOW"
    apply(
        source_module_id="documents",
        document_id=state.document_id,
        version=state.version,
        status=state.status.value,
        release_evidence_mode=release_mode,
        valid_from=state.valid_from,
        valid_until=state.valid_until,
        event=event,
    )

