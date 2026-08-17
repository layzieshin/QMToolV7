from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from modules.documents.api import (
    ControlClass, DocumentStatus, DocumentType, DocumentWorkflowError,
    RejectionReason, SystemRole, ValidityExtensionOutcome,
)
from modules.signature.api import SignatureError
from interfaces.clients.documents_http import resolve_session_token
from modules.signature.api import SignRequest, SignaturePlacementInput, LabelLayoutInput
from qm_platform.runtime import bootstrap as runtime_bootstrap

from interfaces.cli.bootstrap import build_container


def _print_documents_state(prefix: str, state) -> None:
    payload = {
        "document_id": state.document_id,
        "version": state.version,
        "status": state.status.value,
        "workflow_active": state.workflow_active,
        "extension_count": state.extension_count,
    }
    print(f"{prefix}: {json.dumps(payload, ensure_ascii=True)}")


def _load_profile_definition(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DocumentWorkflowError("workflow profile definition must be a JSON object")
    return payload


def _load_documents_state(pool_api, document_id: str, version: int):
    state = pool_api.get_document_version(document_id, version)
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
    legacy_not_in_m0 = {
        "profile-create",
        "profile-create-version",
        "profile-activate",
        "profile-deactivate",
        "profile-bind-doc-type",
        "header-get",
        "pool-list-artifacts",
        "change-request-list",
        "change-request-export",
    }
    if args.documents_command in legacy_not_in_m0:
        label = "artifact reads" if args.documents_command == "pool-list-artifacts" else args.documents_command
        print(
            f"BLOCKED: {label} is outside the reduced J04-M0 transition-client scope"
        )
        return 6
    container = build_container()
    lifecycle = runtime_bootstrap.register_core_modules(container)
    lifecycle.start()
    pool_api = container.get_port("documents_pool_api")
    workflow_api = container.get_port("documents_workflow_api")
    registry_api = container.get_port("registry_api")
    usermanagement = container.get_port("usermanagement_service")
    profile_admin_commands = {
        "profile-list",
        "profile-create",
        "profile-create-version",
        "profile-activate",
        "profile-deactivate",
        "profile-bind-doc-type",
    }
    if args.documents_command in profile_admin_commands:
        try:
            resolve_session_token()
            if args.documents_command == "profile-list":
                if args.profile_id:
                    payload = workflow_api.list_workflow_profile_versions(args.profile_id)
                else:
                    payload = workflow_api.list_workflow_profile_definitions(include_inactive=args.include_inactive)
                print(json.dumps(payload, ensure_ascii=True))
                return 0
            if args.documents_command == "profile-create":
                payload = workflow_api.create_workflow_profile_definition(_load_profile_definition(args.definition_json), change_reason=args.change_reason)
                print(json.dumps(payload, ensure_ascii=True)); return 0
            if args.documents_command == "profile-create-version":
                payload = workflow_api.create_workflow_profile_version(args.profile_id, _load_profile_definition(args.definition_json), change_reason=args.change_reason)
                print(json.dumps(payload, ensure_ascii=True)); return 0
            if args.documents_command == "profile-activate":
                payload = workflow_api.activate_workflow_profile_definition(args.profile_id, change_reason=args.change_reason)
                print(json.dumps(payload, ensure_ascii=True)); return 0
            if args.documents_command == "profile-deactivate":
                payload = workflow_api.deactivate_workflow_profile_definition(args.profile_id, change_reason=args.change_reason)
                print(json.dumps(payload, ensure_ascii=True)); return 0
            if args.documents_command == "profile-bind-doc-type":
                payload = workflow_api.bind_document_type_default_profile(args.doc_type, args.profile_id, change_reason=args.change_reason)
                print(json.dumps(payload, ensure_ascii=True)); return 0
        except (DocumentWorkflowError, SignatureError, ValueError) as exc:
            print(f"BLOCKED: {exc}")
            return 6
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED: {exc}")
            return 7
    try:
        resolve_session_token()
    except DocumentWorkflowError as exc:
        print(f"BLOCKED: {exc}")
        return 6

    try:
        if args.documents_command == "create-version":
            state = workflow_api.create_document_version(
                args.document_id, args.version,
                title=args.title or args.document_id,
                description=args.description,
                doc_type=DocumentType(args.doc_type),
                control_class=ControlClass(args.control_class),
                workflow_profile_id=args.workflow_profile_id,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "import-pdf":
            state = workflow_api.import_existing_pdf(args.document_id, args.version, Path(args.input))
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "import-docx":
            state = workflow_api.import_existing_docx(args.document_id, args.version, Path(args.input))
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "create-from-template":
            state = workflow_api.create_from_template(args.document_id, args.version, Path(args.template))
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "assign-roles":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            state = workflow_api.assign_workflow_roles(
                state,
                editors={v.strip() for v in args.editors.split(",") if v.strip()},
                reviewers={v.strip() for v in args.reviewers.split(",") if v.strip()},
                approvers={v.strip() for v in args.approvers.split(",") if v.strip()},
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "workflow-start":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            state = workflow_api.start_workflow(state, profile_id=args.profile_id)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "editing-complete":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            sign_intent = _build_sign_request(args, "CLI_EDITING_COMPLETE", "") if args.sign_input else None
            state = workflow_api.complete_editing(state, sign_request=sign_intent)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "review-accept":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            sign_intent = _build_sign_request(args, "CLI_REVIEW_ACCEPT", "") if args.sign_input else None
            state = workflow_api.accept_review(state, sign_request=sign_intent)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "review-reject":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            reason = RejectionReason(template_id=args.reason_template_id, template_text=args.reason_template_text, free_text=args.reason_free_text)
            state = workflow_api.reject_review(state, reason)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "approval-accept":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            sign_intent = _build_sign_request(args, "CLI_APPROVAL_ACCEPT", "") if args.sign_input else None
            state = workflow_api.accept_approval(state, sign_request=sign_intent)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "approval-reject":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            reason = RejectionReason(template_id=args.reason_template_id, template_text=args.reason_template_text, free_text=args.reason_free_text)
            state = workflow_api.reject_approval(state, reason)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "workflow-abort":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            state = workflow_api.abort_workflow(state)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "archive":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            state = workflow_api.archive_approved(state)
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "annual-extend":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            sign_intent = _build_sign_request(args, "CLI_ANNUAL_EXTENSION", "")
            state, is_maxed = workflow_api.extend_annual_validity(
                state,
                duration_days=args.duration_days,
                reason=args.reason,
                review_outcome=ValidityExtensionOutcome(args.outcome),
                sign_intent=sign_intent,
            )
            _print_documents_state("OK", state)
            print(json.dumps({"is_maxed": is_maxed}))
            return 0
        if args.documents_command == "pool-list-by-status":
            status = DocumentStatus(args.status)
            rows = pool_api.list_by_status(status)
            payload = [{"document_id": row.document_id, "version": row.version, "status": row.status.value} for row in rows]
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "pool-list-artifacts":
            rows = pool_api.list_artifacts(args.document_id, args.version)
            print(json.dumps([{"artifact_id": row.artifact_id, "artifact_type": row.artifact_type.value, "size_bytes": row.size_bytes} for row in rows]))
            return 0
        if args.documents_command == "pool-get-register":
            print("BLOCKED: registry reads are outside the reduced J04-M0 documents scope")
            return 6
        if args.documents_command == "header-get":
            header = pool_api.get_header(args.document_id)
            if header is None:
                raise DocumentWorkflowError("document header not found")
            print(json.dumps({"document_id": header.document_id, "workflow_profile_id": header.workflow_profile_id, "department": header.department, "site": header.site}, ensure_ascii=True))
            return 0
        if args.documents_command == "header-set":
            header = pool_api.get_header(args.document_id)
            if header is None:
                raise DocumentWorkflowError("document header not found")
            updated = workflow_api.update_document_header(
                args.document_id,
                workflow_profile_id=args.workflow_profile_id,
                department=args.department,
                site=args.site,
                regulatory_scope=args.regulatory_scope,
                if_match=header.updated_at.isoformat(),
            )
            print(json.dumps({"document_id": updated.document_id, "updated_at": updated.updated_at.isoformat()}, ensure_ascii=True))
            return 0
        if args.documents_command == "metadata-get":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            payload = {"document_id": state.document_id, "version": state.version, "title": state.title, "description": state.description, "doc_type": state.doc_type.value, "control_class": state.control_class.value, "workflow_profile_id": state.workflow_profile_id, "valid_from": state.valid_from.isoformat() if state.valid_from else None, "valid_until": state.valid_until.isoformat() if state.valid_until else None, "next_review_at": state.next_review_at.isoformat() if state.next_review_at else None, "custom_fields": state.custom_fields}
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        if args.documents_command == "metadata-set":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            custom = json.loads(args.custom_fields_json) if args.custom_fields_json else None
            state = workflow_api.update_version_metadata(
                state,
                title=args.title,
                description=args.description,
                valid_until=_parse_optional_datetime(args.valid_until),
                next_review_at=_parse_optional_datetime(args.next_review_at),
                custom_fields=custom,
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "change-request-add":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            state = workflow_api.add_change_request(
                state,
                change_id=args.change_id,
                reason=args.reason,
                impact_refs=[value for value in args.impact_refs.split(",") if value],
            )
            _print_documents_state("OK", state)
            return 0
        if args.documents_command == "change-request-list":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            print(json.dumps(workflow_api.list_change_requests(state), ensure_ascii=True))
            return 0
        if args.documents_command == "change-request-export":
            state = _load_documents_state(pool_api, args.document_id, args.version)
            rows = workflow_api.list_change_requests(state)
            output = Path(args.output)
            if args.format == "json":
                output.write_text(json.dumps(rows, ensure_ascii=True, indent=2), encoding="utf-8")
            else:
                fields = sorted({key for row in rows for key in row} or {"change_id"})
                with output.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)
            print(str(output))
            return 0
    except (DocumentWorkflowError, SignatureError, ValueError) as exc:
        print(f"BLOCKED: {exc}")
        return 6
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 7
    return 1

