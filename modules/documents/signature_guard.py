"""Signature enforcement guard for workflow transitions.

Internal module — extracted from service.py (Phase 4A).
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from modules.signature.api import SignatureError
from modules.signature.contracts import SignRequest
from modules.usermanagement.api import UserContext

from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    DocumentVersionState,
)
from .errors import SignatureTransitionError, ValidationError
from .repository import DocumentsRepository
from .storage import DocumentsStoragePort


def execute_sign_dispatch(
    sign_request: object,
    *,
    signature_api: object | None,
    actor: UserContext | None = None,
) -> None:
    """Run fixed-position or template signing based on ``SignRequest.template_id``."""
    if signature_api is None:
        raise SignatureTransitionError("signature_api missing for signing")
    if isinstance(sign_request, SignRequest) and sign_request.template_id:
        if actor is None:
            raise SignatureTransitionError("template_id requires authenticated actor")
        sign_fn = getattr(signature_api, "sign_with_template_for_actor", None)
        if not callable(sign_fn):
            raise SignatureTransitionError("signature_api does not provide sign_with_template_for_actor")
        try:
            sign_fn(
                actor,
                template_id=sign_request.template_id,
                input_pdf=sign_request.input_pdf,
                password=sign_request.password,
                output_pdf=sign_request.output_pdf,
                dry_run=sign_request.dry_run,
                overwrite_output=sign_request.overwrite_output,
                sign_mode=sign_request.sign_mode,
                reason=sign_request.reason,
                placement_override=sign_request.placement,
                layout_override=sign_request.layout,
            )
        except SignatureError as exc:
            raise SignatureTransitionError(
                f"signature step failed: {exc}",
                field_errors=getattr(exc, "field_errors", None),
            ) from exc
        return
    sign = getattr(signature_api, "sign_with_fixed_position", None)
    if not callable(sign):
        raise SignatureTransitionError("signature_api does not provide sign_with_fixed_position")
    try:
        sign(sign_request)
    except SignatureError as exc:
        raise SignatureTransitionError(
            f"signature step failed: {exc}",
            field_errors=getattr(exc, "field_errors", None),
        ) from exc


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
    actor: UserContext | None = None,
) -> None:
    """Enforce signature requirement for a workflow transition."""
    profile = state.workflow_profile
    if profile is None:
        raise ValidationError("workflow profile is missing")
    if transition not in profile.signature_required_transitions:
        return
    if sign_request is None:
        raise SignatureTransitionError(f"signature request required for transition '{transition}'")

    canonical_input = _resolve_signature_input_pdf(
        state, transition, repository=repository, resolve_artifact_path_fn=resolve_artifact_path_fn,
    )
    if canonical_input is not None and hasattr(sign_request, "input_pdf"):
        sign_request = replace(sign_request, input_pdf=canonical_input)

    signature_png = getattr(sign_request, "signature_png", None)
    output_pdf = getattr(sign_request, "output_pdf", None)
    input_pdf = getattr(sign_request, "input_pdf", None)
    try:
        execute_sign_dispatch(sign_request, signature_api=signature_api, actor=actor)

        output_pdf = getattr(sign_request, "output_pdf", None)
        if repository is None or storage_port is None:
            return
        if not isinstance(output_pdf, Path) or not output_pdf.exists() or output_pdf.suffix.lower() != ".pdf":
            raise SignatureTransitionError(
                f"signature transition '{transition}' did not produce a valid signed PDF output"
            )
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
        signed_artifacts = repository.list_artifacts(state.document_id, state.version)
        has_current_signed = any(
            item.artifact_type == ArtifactType.SIGNED_PDF and bool(item.is_current)
            for item in signed_artifacts
        )
        if not has_current_signed:
            raise SignatureTransitionError(
                f"signature transition '{transition}' did not persist a current SIGNED_PDF artifact"
            )
    finally:
        import gc
        import time

        gc.collect()
        protected = []
        for candidate in (canonical_input, input_pdf):
            if isinstance(candidate, Path):
                try:
                    protected.append(candidate.resolve())
                except OSError:
                    protected.append(candidate)
        for path in (signature_png, output_pdf):
            if not isinstance(path, Path):
                continue
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in protected:
                continue
            for attempt in range(8):
                try:
                    path.unlink(missing_ok=True)
                    break
                except OSError:
                    time.sleep(0.05 * (attempt + 1))


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
    transition_key = transition.strip().upper()
    if transition_key in {"IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED"}:
        priority = [ArtifactType.SIGNED_PDF]
    elif transition_key in {"IN_PROGRESS->IN_REVIEW", "IN_PROGRESS->IN_APPROVAL", "IN_PROGRESS->APPROVED"}:
        priority = [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF]
    else:
        priority = [ArtifactType.SIGNED_PDF, ArtifactType.SOURCE_PDF, ArtifactType.RELEASED_PDF]
    def _created_at_value(item: object) -> datetime:
        value = getattr(item, "created_at", None)
        return value if isinstance(value, datetime) else datetime.min

    def _resolve_by_type(artifact_type: ArtifactType, *, current_only: bool) -> Path | None:
        candidates = [a for a in artifacts if a.artifact_type == artifact_type and (a.is_current if current_only else True)]
        candidates.sort(key=_created_at_value, reverse=True)
        for artifact in candidates:
            resolved = resolve_artifact_path_fn(artifact)
            if resolved is not None and resolved.exists() and resolved.suffix.lower() == ".pdf":
                return resolved
        return None

    for artifact_type in priority:
        resolved = _resolve_by_type(artifact_type, current_only=True)
        if resolved is not None:
            return resolved
    for artifact_type in priority:
        resolved = _resolve_by_type(artifact_type, current_only=False)
        if resolved is not None:
            return resolved
    return None
