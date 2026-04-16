from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from modules.documents.api import DocumentWorkflowError
from modules.documents.contracts import (
    ControlClass, DocumentStatus, DocumentType,
    RejectionReason, SystemRole
)
from modules.signature.api import SignatureError
from modules.signature.contracts import SignRequest, SignaturePlacementInput, LabelLayoutInput
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def _resolve_current_user_and_role(usermanagement) -> tuple[object | None, SystemRole | None]:
    current_user = usermanagement.get_current_user()
    if current_user is None:
        return None, None
    role_map = {"Admin": SystemRole.ADMIN, "QMB": SystemRole.QMB, "User": SystemRole.USER}
    return current_user, role_map.get(current_user.role)


def _print_documents_state(prefix: str, state) -> None:
    payload = {
        "document_id": state.document_id,
        "version": state.version,
        "status": state.status.value,
        "workflow_active": state.workflow_active,
        "extension_count": state.extension_count,
    }
    print(f"{prefix}: {json.dumps(payload, ensure_ascii=True)}")


def _load_documents_state(service, document_id: str, version: int):
    state = service.get_document_version(document_id, version)
    if state is None:
        raise DocumentWorkflowError(f"document version not found: {document_id} v{version}")
    return state


def _parse_optional_datetime(raw: str | None):
    if raw is None or not raw.strip():
        return None
    return datetime.fromisoformat(raw)


def _build_sign_request(args: argparse.Namespace, reason: str, signer_user: str) -> SignRequest:
    date_text = datetime.now().strftime(args.date_format)
    return SignRequest(
        input_pdf=Path(args.sign_input),
        output_pdf=Path(args.sign_output) if args.sign_output else None,
        signature_png=Path(args.sign_signature_png) if args.sign_signature_png else None,
        placement=SignaturePlacementInput(
            page_index=args.sign_page, x=args.sign_x, y=args.sign_y, target_width=args.sign_width,
        ),
        layout=LabelLayoutInput(
            show_signature=args.sign_show_signature,
            show_name=args.sign_show_name,
            show_date=args.sign_show_date,
            name_text=args.sign_name_text or signer_user,
            date_text=args.sign_date_text or date_text,
            name_position=args.sign_name_pos,
            date_position=args.sign_date_pos,
            name_font_size=args.sign_name_size,
            date_font_size=args.sign_date_size,
            color_hex=args.sign_color,
            name_above=args.sign_name_above,
            name_below=args.sign_name_below,
            date_above=args.sign_date_above,
            date_below=args.sign_date_below,
            x_offset=args.sign_x_offset,
        ),
        overwrite_output=args.sign_overwrite_output,
        dry_run=args.sign_dry_run,
        sign_mode=args.sign_mode,
        signer_user=signer_user,
        password=args.signer_password,
        reason=reason,
    )


def cmd_documents(args: argparse.Namespace) -> int:
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    pool_api = container.get_port("documents_pool_api")
    workflow_api = container.get_port("documents_workflow_api")
    service = container.get_port("documents_service")
    registry_api = container.get_port("registry_api")
    usermanagement = container.get_port("usermanagement_service")
    current_user, current_role = _resolve_current_user_and_role(usermanagement)
    if current_user is None:
        print("BLOCKED: login required for documents commands")
        return 6
    if current_role is None:
        print(f"BLOCKED: unsupported user role '{current_user.role}'")
        return 6

    try:
        if args.documents_command == "create-version":
            state = workflow_api.create_document_version(
                args.document_id, args.version,
                owner_user_id=current_user.user_id,
                title=args.title or args.document_id,
                description=args.description,
                doc_type=DocumentType(args.doc_type),
                control_class=ControlClass(args.control_class),
                workflow_profile_id=args.workflow_profile_id,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "import-pdf":
            state = workflow_api.import_existing_pdf(
                args.document_id, args.version, Path(args.input),
                actor_user_id=current_user.user_id, actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "import-docx":
            state = workflow_api.import_existing_docx(
                args.document_id, args.version, Path(args.input),
                actor_user_id=current_user.user_id, actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "create-from-template":
            state = workflow_api.create_from_template(
                args.document_id, args.version, Path(args.template),
                actor_user_id=current_user.user_id, actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "assign-roles":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.assign_workflow_roles(
                state,
                editors={v.strip() for v in args.editors.split(",") if v.strip()},
                reviewers={v.strip() for v in args.reviewers.split(",") if v.strip()},
                approvers={v.strip() for v in args.approvers.split(",") if v.strip()},
                actor_user_id=current_user.user_id, actor_role=current_role,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "workflow-start":
            state = _load_documents_state(service, args.document_id, args.version)
            profile = service.get_profile(args.profile_id)
            state = workflow_api.start_workflow(state, profile, actor_user_id=current_user.user_id, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "editing-complete":
            state = _load_documents_state(service, args.document_id, args.version)
            sign_request = (_build_sign_request(args, "documents.editing_complete", current_user.username) if args.sign_input else None)
            state = workflow_api.complete_editing(state, sign_request=sign_request, actor_user_id=current_user.user_id, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "review-accept":
            state = _load_documents_state(service, args.document_id, args.version)
            sign_request = (_build_sign_request(args, "documents.review_accept", current_user.username) if args.sign_input else None)
            state = workflow_api.accept_review(state, current_user.user_id, sign_request=sign_request, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "review-reject":
            state = _load_documents_state(service, args.document_id, args.version)
            reason = RejectionReason(template_id=args.reason_template_id, template_text=args.reason_template_text, free_text=args.reason_free_text)
            state = workflow_api.reject_review(state, current_user.user_id, reason, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "approval-accept":
            state = _load_documents_state(service, args.document_id, args.version)
            sign_request = (_build_sign_request(args, "documents.approval_accept", current_user.username) if args.sign_input else None)
            state = workflow_api.accept_approval(state, current_user.user_id, sign_request=sign_request, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "approval-reject":
            state = _load_documents_state(service, args.document_id, args.version)
            reason = RejectionReason(template_id=args.reason_template_id, template_text=args.reason_template_text, free_text=args.reason_free_text)
            state = workflow_api.reject_approval(state, current_user.user_id, reason, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "workflow-abort":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.abort_workflow(state, actor_user_id=current_user.user_id, actor_role=current_role)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "archive":
            state = _load_documents_state(service, args.document_id, args.version)
            state = workflow_api.archive_approved(state, current_role, actor_user_id=current_user.user_id)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "annual-extend":
            state = _load_documents_state(service, args.document_id, args.version)
            state, must_recreate = workflow_api.extend_annual_validity(state, signature_present=args.signature_present)
            _print_documents_state("OK", state)
            print(f"RECREATE_REQUIRED: {str(must_recreate).lower()}")
            return 0
        if args.documents_command == "pool-list-by-status":
            status = DocumentStatus(args.status)
            rows = pool_api.list_by_status(status)
            payload = [{"document_id": row.document_id, "version": row.version, "status": row.status.value} for row in rows]
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "pool-list-artifacts":
            rows = pool_api.list_artifacts(args.document_id, args.version)
            payload = [{"artifact_id": row.artifact_id, "artifact_type": row.artifact_type.value, "source_type": row.source_type.value, "storage_key": row.storage_key, "original_filename": row.original_filename, "is_current": row.is_current} for row in rows]
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "pool-get-register":
            row = registry_api.get_entry(args.document_id)
            if row is None:
                print("{}")
                return 0
            payload = {"document_id": row.document_id, "active_version": row.active_version, "register_state": row.register_state.value, "is_findable": row.is_findable, "release_evidence_mode": row.release_evidence_mode.value, "last_update_event_id": row.last_update_event_id}
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "header-get":
            row = pool_api.get_header(args.document_id)
            if row is None:
                print("{}")
                return 0
            payload = {"document_id": row.document_id, "doc_type": row.doc_type.value, "control_class": row.control_class.value, "workflow_profile_id": row.workflow_profile_id, "department": row.department, "site": row.site, "regulatory_scope": row.regulatory_scope}
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "header-set":
            if current_role not in (SystemRole.ADMIN, SystemRole.QMB):
                print("BLOCKED: only QMB or ADMIN may update document headers")
                return 6
            row = workflow_api.update_document_header(args.document_id, doc_type=DocumentType(args.doc_type) if args.doc_type else None, control_class=ControlClass(args.control_class) if args.control_class else None, workflow_profile_id=args.workflow_profile_id, department=args.department, site=args.site, regulatory_scope=args.regulatory_scope, actor_user_id=current_user.user_id, actor_role=current_role)
            payload = {"document_id": row.document_id, "doc_type": row.doc_type.value, "control_class": row.control_class.value, "workflow_profile_id": row.workflow_profile_id, "department": row.department, "site": row.site, "regulatory_scope": row.regulatory_scope}
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "metadata-get":
            state = _load_documents_state(service, args.document_id, args.version)
            payload = {"document_id": state.document_id, "version": state.version, "title": state.title, "description": state.description, "doc_type": state.doc_type.value, "control_class": state.control_class.value, "workflow_profile_id": state.workflow_profile_id, "valid_from": state.valid_from.isoformat() if state.valid_from else None, "valid_until": state.valid_until.isoformat() if state.valid_until else None, "next_review_at": state.next_review_at.isoformat() if state.next_review_at else None, "custom_fields": state.custom_fields}
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "metadata-set":
            state = _load_documents_state(service, args.document_id, args.version)
            custom_fields = json.loads(args.custom_fields_json) if args.custom_fields_json else None
            if custom_fields is not None and not isinstance(custom_fields, dict):
                print("BLOCKED: --custom-fields-json must be a JSON object")
                return 6
            updated = workflow_api.update_version_metadata(state, title=args.title, description=args.description, valid_until=_parse_optional_datetime(args.valid_until), next_review_at=_parse_optional_datetime(args.next_review_at), custom_fields=custom_fields, actor_user_id=current_user.user_id, actor_role=current_role)
            _print_documents_state("OK", updated)
            return 0
    except (DocumentWorkflowError, SignatureError, ValueError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1

