"""Build server-side SignRequest from workflow sign_intent (J04-M0-P3B)."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from modules.signature.api import SignatureApi
from modules.signature.api import SignRequest
from modules.usermanagement.api import UserContext
from modules.signature.api import layout_from_payload, placement_from_payload

from . import signature_guard
from .contracts import DocumentVersionState
from .service import DocumentsService


def build_workflow_sign_request_from_intent(
    *,
    state: DocumentVersionState,
    transition: str,
    sign_intent: dict[str, object],
    actor: UserContext,
    signature_api: SignatureApi,
    documents_service: DocumentsService,
    scratch_root: Path,
) -> SignRequest:
    placement = placement_from_payload(dict(sign_intent["placement"]))  # type: ignore[arg-type]
    layout = layout_from_payload(dict(sign_intent["layout"]))  # type: ignore[arg-type]
    password = sign_intent.get("password")
    password_s = str(password).strip() if password is not None else None
    reason = str(sign_intent.get("reason") or "WORKFLOW_TRANSITION")

    input_pdf = signature_guard._resolve_signature_input_pdf(  # noqa: SLF001
        state,
        transition,
        repository=documents_service._repository,
        resolve_artifact_path_fn=documents_service._resolve_artifact_path,
    )
    if input_pdf is None or not input_pdf.exists():
        raise ValueError(f"no PDF artifact available for signed transition '{transition}'")

    scratch_root.mkdir(parents=True, exist_ok=True)
    signature_png = scratch_root / f"active-signature-{uuid4().hex}.png"
    exported = signature_api.export_active_signature(actor.user_id, signature_png)
    if not exported.exists():
        raise ValueError("active signature could not be exported on the server")

    resolved_layout = signature_api.resolve_runtime_layout(layout, signer_user=actor.username)
    output_pdf = scratch_root / f"signed-{uuid4().hex}.pdf"

    return SignRequest(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        signature_png=exported,
        placement=placement,
        layout=resolved_layout,
        overwrite_output=True,
        dry_run=False,
        sign_mode="visual",
        signer_user=actor.username,
        password=password_s or None,
        reason=reason,
    )
