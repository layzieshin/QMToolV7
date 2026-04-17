from __future__ import annotations
import argparse

from modules.documents.contracts import ControlClass, DocumentStatus, DocumentType, ValidityExtensionOutcome
from interfaces.cli.parsers.signature_parsers import add_sign_layout_args


def register_documents_parsers(sub: argparse._SubParsersAction) -> None:
    documents_parser = sub.add_parser("documents", help="Document pool and workflow operations")
    documents_sub = documents_parser.add_subparsers(dest="documents_command", required=True)

    doc_create = documents_sub.add_parser("create-version", help="Create a document version in PLANNED")
    doc_create.add_argument("--document-id", required=True)
    doc_create.add_argument("--version", type=int, required=True)
    doc_create.add_argument(
        "--doc-type",
        choices=[v.value for v in DocumentType],
        default=DocumentType.OTHER.value,
    )
    doc_create.add_argument(
        "--control-class",
        choices=[v.value for v in ControlClass],
        default=ControlClass.CONTROLLED.value,
    )
    doc_create.add_argument("--workflow-profile-id", default="long_release")
    doc_create.add_argument("--title")
    doc_create.add_argument("--description")

    doc_import_pdf = documents_sub.add_parser("import-pdf", help="Import existing PDF into document pool")
    doc_import_pdf.add_argument("--document-id", required=True)
    doc_import_pdf.add_argument("--version", type=int, required=True)
    doc_import_pdf.add_argument("--input", required=True)

    doc_import_docx = documents_sub.add_parser("import-docx", help="Import existing DOCX into document pool")
    doc_import_docx.add_argument("--document-id", required=True)
    doc_import_docx.add_argument("--version", type=int, required=True)
    doc_import_docx.add_argument("--input", required=True)

    doc_create_from_template = documents_sub.add_parser(
        "create-from-template",
        help="Create a new document from DOTX (DOCT fallback supported)",
    )
    doc_create_from_template.add_argument("--document-id", required=True)
    doc_create_from_template.add_argument("--version", type=int, required=True)
    doc_create_from_template.add_argument("--template", required=True)

    doc_assign = documents_sub.add_parser("assign-roles", help="Assign editors/reviewers/approvers")
    doc_assign.add_argument("--document-id", required=True)
    doc_assign.add_argument("--version", type=int, required=True)
    doc_assign.add_argument("--editors", required=True, help="Comma-separated user ids")
    doc_assign.add_argument("--reviewers", required=True, help="Comma-separated user ids")
    doc_assign.add_argument("--approvers", required=True, help="Comma-separated user ids")

    doc_start = documents_sub.add_parser("workflow-start", help="Start workflow from PLANNED")
    doc_start.add_argument("--document-id", required=True)
    doc_start.add_argument("--version", type=int, required=True)
    doc_start.add_argument("--profile-id", default="long_release")

    doc_edit_done = documents_sub.add_parser("editing-complete", help="Complete editing and move to next phase")
    doc_edit_done.add_argument("--document-id", required=True)
    doc_edit_done.add_argument("--version", type=int, required=True)
    add_sign_layout_args(doc_edit_done)

    doc_review_accept = documents_sub.add_parser("review-accept", help="Accept review")
    doc_review_accept.add_argument("--document-id", required=True)
    doc_review_accept.add_argument("--version", type=int, required=True)
    add_sign_layout_args(doc_review_accept)

    doc_review_reject = documents_sub.add_parser("review-reject", help="Reject review")
    doc_review_reject.add_argument("--document-id", required=True)
    doc_review_reject.add_argument("--version", type=int, required=True)
    doc_review_reject.add_argument("--reason-template-id")
    doc_review_reject.add_argument("--reason-template-text")
    doc_review_reject.add_argument("--reason-free-text")

    doc_approval_accept = documents_sub.add_parser("approval-accept", help="Accept approval")
    doc_approval_accept.add_argument("--document-id", required=True)
    doc_approval_accept.add_argument("--version", type=int, required=True)
    add_sign_layout_args(doc_approval_accept)

    doc_approval_reject = documents_sub.add_parser("approval-reject", help="Reject approval")
    doc_approval_reject.add_argument("--document-id", required=True)
    doc_approval_reject.add_argument("--version", type=int, required=True)
    doc_approval_reject.add_argument("--reason-template-id")
    doc_approval_reject.add_argument("--reason-template-text")
    doc_approval_reject.add_argument("--reason-free-text")

    doc_abort = documents_sub.add_parser("workflow-abort", help="Abort active workflow and return to PLANNED")
    doc_abort.add_argument("--document-id", required=True)
    doc_abort.add_argument("--version", type=int, required=True)

    doc_archive = documents_sub.add_parser("archive", help="Archive approved document")
    doc_archive.add_argument("--document-id", required=True)
    doc_archive.add_argument("--version", type=int, required=True)

    doc_extend = documents_sub.add_parser("annual-extend", help="Perform annual validity extension")
    doc_extend.add_argument("--document-id", required=True)
    doc_extend.add_argument("--version", type=int, required=True)
    doc_extend.add_argument("--signature-present", action="store_true")
    doc_extend.add_argument("--duration-days", type=int, default=365)
    doc_extend.add_argument("--reason", required=True)
    doc_extend.add_argument(
        "--outcome",
        choices=[value.value for value in ValidityExtensionOutcome],
        default=ValidityExtensionOutcome.UNCHANGED.value,
    )

    doc_pool_list = documents_sub.add_parser("pool-list-by-status", help="List documents by status")
    doc_pool_list.add_argument(
        "--status",
        choices=[s.value for s in DocumentStatus],
        default=DocumentStatus.PLANNED.value,
        help="Defaults to PLANNED",
    )

    doc_pool_artifacts = documents_sub.add_parser("pool-list-artifacts", help="List artifacts for a document version")
    doc_pool_artifacts.add_argument("--document-id", required=True)
    doc_pool_artifacts.add_argument("--version", type=int, required=True)

    doc_pool_register = documents_sub.add_parser(
        "pool-get-register",
        help="Get central registry entry for a document",
    )
    doc_pool_register.add_argument("--document-id", required=True)

    doc_header_get = documents_sub.add_parser("header-get", help="Get document header metadata")
    doc_header_get.add_argument("--document-id", required=True)

    doc_header_set = documents_sub.add_parser("header-set", help="Set document header metadata (QMB/Admin)")
    doc_header_set.add_argument("--document-id", required=True)
    doc_header_set.add_argument("--doc-type", choices=[v.value for v in DocumentType])
    doc_header_set.add_argument("--control-class", choices=[v.value for v in ControlClass])
    doc_header_set.add_argument("--workflow-profile-id")
    doc_header_set.add_argument("--department")
    doc_header_set.add_argument("--site")
    doc_header_set.add_argument("--regulatory-scope")

    doc_meta_get = documents_sub.add_parser("metadata-get", help="Get document version metadata")
    doc_meta_get.add_argument("--document-id", required=True)
    doc_meta_get.add_argument("--version", type=int, required=True)

    doc_meta_set = documents_sub.add_parser("metadata-set", help="Set document version metadata")
    doc_meta_set.add_argument("--document-id", required=True)
    doc_meta_set.add_argument("--version", type=int, required=True)
    doc_meta_set.add_argument("--title")
    doc_meta_set.add_argument("--description")
    doc_meta_set.add_argument("--valid-until")
    doc_meta_set.add_argument("--next-review-at")
    doc_meta_set.add_argument("--custom-fields-json")

    doc_change_add = documents_sub.add_parser("change-request-add", help="Add structured change request to document version")
    doc_change_add.add_argument("--document-id", required=True)
    doc_change_add.add_argument("--version", type=int, required=True)
    doc_change_add.add_argument("--change-id", required=True)
    doc_change_add.add_argument("--reason", required=True)
    doc_change_add.add_argument("--impact-refs", default="", help="Comma-separated related document ids")

    doc_change_list = documents_sub.add_parser("change-request-list", help="List structured change requests for document version")
    doc_change_list.add_argument("--document-id", required=True)
    doc_change_list.add_argument("--version", type=int, required=True)

    doc_change_export = documents_sub.add_parser(
        "change-request-export",
        help="Export structured change requests for a document version",
    )
    doc_change_export.add_argument("--document-id", required=True)
    doc_change_export.add_argument("--version", type=int, required=True)
    doc_change_export.add_argument("--output", required=True, help="Output file path")
    doc_change_export.add_argument("--format", choices=["json", "csv"], default="json")

