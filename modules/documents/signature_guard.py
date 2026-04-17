"""Signature enforcement guard for workflow transitions.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from modules.signature.errors import SignatureError

from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    DocumentVersionState,
)
from .errors import SignatureTransitionError, ValidationError
from .repository import DocumentsRepository
from .storage import DocumentsStoragePort


def enforce_signature_transition(
    state: DocumentVersionState,
    transition: str,
    sign_request: object | None,
    *,
    signature_api: object | None,
    repository: DocumentsRepository | None,
    storage_port: DocumentsStoragePort | None,
    create_artifact_fn,
    resolve_artifact_path_fn,
) -> None:
    """Enforce signature requirement for a workflow transition."""
    profile = state.workflow_profile
    if profile is None:
        raise ValidationError("workflow profile is missing")
    if transition not in profile.signature_required_transitions:
        return
    if signature_api is None:
        raise SignatureTransitionError(f"signature_api missing for required transition '{transition}'")
    if sign_request is None:
        raise SignatureTransitionError(f"signature request required for transition '{transition}'")

    canonical_input = _resolve_signature_input_pdf(
        state, transition, repository=repository, resolve_artifact_path_fn=resolve_artifact_path_fn,
    )
    if canonical_input is not None and hasattr(sign_request, "input_pdf"):
        sign_request = replace(sign_request, input_pdf=canonical_input)

    sign = getattr(signature_api, "sign_with_fixed_position", None)
    if not callable(sign):
        raise SignatureTransitionError("signature_api does not provide sign_with_fixed_position")
    try:
        sign(sign_request)
    except SignatureError as exc:
        raise SignatureTransitionError(f"signature step failed: {exc}") from exc

    output_pdf = getattr(sign_request, "output_pdf", None)
    if (
        repository is not None
        and storage_port is not None
        and isinstance(output_pdf, Path)
        and output_pdf.exists()
        and output_pdf.suffix.lower() == ".pdf"
    ):
        create_artifact_fn(
            state=state,
            source_path=output_pdf,
            artifact_type=ArtifactType.SIGNED_PDF,
            source_type=ArtifactSourceType.GENERATED,
            metadata={
                "transition": transition,
                "generated_from": str(getattr(sign_request, "input_pdf", "")),
            },
        )


def is_signature_required(state: DocumentVersionState, transition: str) -> bool:
    profile = state.workflow_profile
    if profile is None:
        return False
    return transition in profile.signature_required_transitions


def _resolve_signature_input_pdf(
    state: DocumentVersionState,
    transition: str,
    *,
    repository: DocumentsRepository | None,
    resolve_artifact_path_fn,
) -> Path | None:
    if repository is None:
        return None
    artifacts = repository.list_artifacts(state.document_id, state.version)
    ordered = sorted(artifacts, key=lambda item: 0 if item.is_current else 1)
    transition_key = transition.strip().upper()
    if transition_key in {"IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED"}:
        priority = [ArtifactType.SIGNED_PDF]
    elif transition_key == "IN_PROGRESS->IN_REVIEW":
        priority = [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF]
    else:
        priority = [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF, ArtifactType.RELEASED_PDF]
    for artifact_type in priority:
        for artifact in ordered:
            if artifact.artifact_type != artifact_type:
                continue
            resolved = resolve_artifact_path_fn(artifact)
            if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
                return resolved
    return None

