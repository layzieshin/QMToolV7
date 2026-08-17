"""HTTP transport for documents (J04-M0). No local SQLite access."""
from __future__ import annotations

import os
import json
import hashlib
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from interfaces.clients.http_transport import (
    BackendHttpTransport,
    BackendTransportError,
    resolve_backend_base_url_from_env,
)
from modules.documents.api import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentReadReceipt,
    DocumentReadSession,
    DocumentStatus,
    DocumentTaskItem,
    DocumentType,
    DocumentVersionState,
    DocumentWorkflowError,
    DocumentsFeatureUnavailableError,
    PdfReadProgress,
    RecentDocumentItem,
    ReleasedDocumentItem,
    RejectionReason,
    ReviewActionItem,
    TrackedPdfReadSession,
    document_version_state_from_payload,
)
from modules.signature.api import layout_to_payload, placement_to_payload


class DocumentsBackendTransportError(DocumentWorkflowError):
    """Raised when the documents backend HTTP transport fails."""


class DocumentsBackendFeatureUnavailableError(DocumentsFeatureUnavailableError):
    """Raised when the backend reports a reduced-scope J04-M0 path as unavailable."""


class DocumentsBackendConflictError(DocumentsBackendTransportError):
    """Raised when If-Match identifies a stale documents state."""

    def __init__(self, message: str, *, current_etag: str | None = None, current_state=None) -> None:
        super().__init__(message)
        self.current_etag = current_etag
        self.current_state = current_state


# PyQt binds a process session token provider; CLI may use QMTOOL_SESSION_TOKEN.
_token_provider: Callable[[], str | None] | None = None
_reject_env_token: bool = False
_artifact_temp_dirs: set[Path] = set()


def clear_artifact_temp_files() -> None:
    """Remove all artifact downloads created by this client process."""
    for temp_dir in tuple(_artifact_temp_dirs):
        shutil.rmtree(temp_dir, ignore_errors=True)
        _artifact_temp_dirs.discard(temp_dir)


def bind_pyqt_session_token_provider(provider: Callable[[], str | None]) -> None:
    """PyQt product path: Bearer only from backend_session_api (env token ignored)."""
    global _token_provider, _reject_env_token
    _token_provider = provider
    _reject_env_token = True


def clear_pyqt_session_token_provider() -> None:
    global _token_provider, _reject_env_token
    _token_provider = None
    _reject_env_token = False


def resolve_backend_base_url() -> str:
    return resolve_backend_base_url_from_env()


def resolve_session_token() -> str:
    if _token_provider is not None:
        token = (_token_provider() or "").strip()
        if token:
            return token
        if _reject_env_token:
            raise DocumentsBackendTransportError(
                "backend session is required for documents operations "
                "(QMTOOL_SESSION_TOKEN is ignored in PyQt)"
            )
    if _reject_env_token:
        raise DocumentsBackendTransportError(
            "backend session is required for documents operations "
            "(QMTOOL_SESSION_TOKEN is ignored in PyQt)"
        )
    token = os.environ.get("QMTOOL_SESSION_TOKEN", "").strip()
    if not token:
        raise DocumentsBackendTransportError(
            "QMTOOL_SESSION_TOKEN is required for documents operations (no local SQLite fallback)"
        )
    return token


class DocumentsHttpClient:
    def __init__(self, *, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._transport = BackendHttpTransport(
            base_url=self._base_url,
            token_provider=lambda: self._token,
        )

    @classmethod
    def from_env(cls) -> DocumentsHttpClient:
        """CLI/tests: env token. PyQt must use session provider via for_runtime()."""
        return cls(base_url=resolve_backend_base_url(), token=resolve_session_token())

    @classmethod
    def for_runtime(cls) -> DocumentsHttpClient:
        """Prefer bound PyQt session token; otherwise CLI env token."""
        return cls.from_env()

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        raw_body: bytes | None = None,
        content_type: str = "application/json",
        if_match: str | None = None,
    ) -> Any:
        try:
            return self._transport.request(
                method,
                path,
                body=body,
                raw_body=raw_body,
                content_type=content_type,
                auth=True,
                headers={"If-Match": if_match} if if_match is not None else None,
            )
        except BackendTransportError as exc:
            detail = exc.body or str(exc)
            if exc.status_code == 501 and "documents_feature_unavailable" in detail:
                raise DocumentsBackendFeatureUnavailableError(
                    f"documents backend feature unavailable: {detail}"
                ) from None
            if exc.status_code == 409:
                current_etag = None
                current_state = None
                try:
                    parsed = json.loads(exc.body)
                    conflict = parsed.get("detail", {}) if isinstance(parsed, dict) else {}
                    if isinstance(conflict, dict) and conflict.get("error") == "document_conflict":
                        current_etag = str(conflict.get("current_etag") or "") or None
                        raw_state = conflict.get("current_state")
                        if isinstance(raw_state, dict):
                            current_state = document_version_state_from_payload(raw_state)
                except Exception:
                    pass
                raise DocumentsBackendConflictError(
                    f"document conflict: reload the current version before retrying ({detail})",
                    current_etag=current_etag,
                    current_state=current_state,
                ) from None
            raise DocumentsBackendTransportError(
                f"documents backend HTTP {exc.status_code or '?'}: {detail}"
            ) from None

    def _request_bytes(self, path: str) -> tuple[bytes, dict[str, str]]:
        try:
            return self._transport.request_bytes("GET", path, auth=True)
        except BackendTransportError as exc:
            raise DocumentsBackendTransportError(
                f"documents backend HTTP {exc.status_code or '?'}: {exc.body or str(exc)}"
            ) from None

    @staticmethod
    def _coerce_available_actions(raw: object) -> list[str]:
        """Fail-closed: only a pure list of strings is accepted; otherwise empty."""
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            return []
        return list(raw)

    def _state_from_response(self, payload: dict[str, Any]) -> DocumentVersionState:
        state_payload = payload.get("state") if isinstance(payload, dict) else None
        if not isinstance(state_payload, dict):
            raise DocumentsBackendTransportError("invalid documents state response")
        enriched = dict(state_payload)
        enriched["available_actions"] = self._coerce_available_actions(payload.get("available_actions"))
        return document_version_state_from_payload(enriched)

    @staticmethod
    def _if_match(state: DocumentVersionState) -> str:
        return str(state.last_event_id or "none")

    @staticmethod
    def _workflow_body(sign_intent: object | None) -> dict[str, Any]:
        if sign_intent is None:
            return {}
        placement = getattr(sign_intent, "placement", None)
        layout = getattr(sign_intent, "layout", None)
        if placement is None or layout is None:
            return {}
        password = getattr(sign_intent, "password", None)
        reason = getattr(sign_intent, "reason", None)
        return {
            "sign_intent": {
                "placement": placement_to_payload(placement),
                "layout": layout_to_payload(layout),
                "password": password,
                "reason": reason,
            }
        }

    @staticmethod
    def _artifact_from_payload(row: dict[str, Any]) -> DocumentArtifact:
        metadata = row.get("metadata")
        return DocumentArtifact(
            artifact_id=str(row["artifact_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            artifact_type=ArtifactType(str(row["artifact_type"])),
            source_type=ArtifactSourceType(str(row["source_type"])),
            storage_key="",
            original_filename=str(row.get("original_filename") or "artifact"),
            mime_type=str(row.get("mime_type") or "application/octet-stream"),
            sha256=str(row.get("sha256") or ""),
            size_bytes=int(row.get("size_bytes") or 0),
            is_current=bool(row.get("is_current", False)),
            metadata={
                str(key): str(value)
                for key, value in metadata.items()
            } if isinstance(metadata, dict) else {},
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        rows = self._request("GET", f"/documents/versions/{document_id}/{version}/artifacts")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid artifacts list response")
        return [self._artifact_from_payload(row) for row in rows if isinstance(row, dict)]

    def get_artifact(self, artifact_id: str) -> DocumentArtifact | None:
        try:
            row = self._request("GET", f"/documents/artifacts/{artifact_id}")
        except DocumentsBackendTransportError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid artifact response")
        return self._artifact_from_payload(row)

    def download_artifact(self, artifact_id: str) -> Path:
        artifact = self.get_artifact(artifact_id)
        if artifact is None:
            raise DocumentsBackendTransportError("artifact not found")
        content, headers = self._request_bytes(f"/documents/artifacts/{artifact_id}/content")
        if artifact.size_bytes != len(content):
            raise DocumentsBackendTransportError("artifact content length mismatch")
        digest = hashlib.sha256(content).hexdigest()
        if not artifact.sha256 or digest.lower() != artifact.sha256.lower():
            raise DocumentsBackendTransportError("artifact content SHA-256 mismatch")
        header_hash = next(
            (value for key, value in headers.items() if key.lower() == "x-content-sha256"),
            artifact.sha256,
        )
        if str(header_hash).strip('"').lower() != digest.lower():
            raise DocumentsBackendTransportError("artifact response SHA-256 header mismatch")
        temp_dir = Path(tempfile.mkdtemp(prefix="qmtool-artifact-"))
        _artifact_temp_dirs.add(temp_dir)
        filename = Path(artifact.original_filename).name or f"{artifact.artifact_id}.bin"
        target = temp_dir / filename
        target.write_bytes(content)
        return target

    def clear_artifact_temp_files(self) -> None:
        clear_artifact_temp_files()

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        rows = self._request("GET", f"/documents/pool/by-status/{status.value}")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid documents list response")
        return [document_version_state_from_payload(row) for row in rows if isinstance(row, dict)]

    def get_document_version(self, document_id: str, version: int) -> DocumentVersionState | None:
        try:
            payload = self._request("GET", f"/documents/versions/{document_id}/{version}")
        except DocumentsBackendTransportError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        return self._state_from_response(payload)

    def get_header(self, document_id: str) -> DocumentHeader | None:
        try:
            row = self._request("GET", f"/documents/headers/{document_id}")
        except DocumentsBackendTransportError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid documents header response")
        return DocumentHeader(
            document_id=str(row["document_id"]),
            doc_type=DocumentType(str(row["doc_type"])),
            control_class=ControlClass(str(row["control_class"])),
            workflow_profile_id=str(row["workflow_profile_id"]),
            register_binding=bool(row.get("register_binding", True)),
            department=str(row["department"]) if row.get("department") is not None else None,
            site=str(row["site"]) if row.get("site") is not None else None,
            regulatory_scope=str(row["regulatory_scope"]) if row.get("regulatory_scope") is not None else None,
            distribution_roles=tuple(str(v) for v in row.get("distribution_roles", [])),
            distribution_sites=tuple(str(v) for v in row.get("distribution_sites", [])),
            distribution_departments=tuple(str(v) for v in row.get("distribution_departments", [])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def list_tasks(self, *, scope: str | None = None) -> list[DocumentTaskItem]:
        suffix = f"?scope={scope}" if scope else ""
        rows = self._request("GET", f"/documents/home/tasks{suffix}")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid documents tasks response")
        return [
            DocumentTaskItem(
                document_id=str(row["document_id"]),
                version=int(row["version"]),
                title=str(row.get("title") or ""),
                status=DocumentStatus(str(row["status"])),
                owner_user_id=str(row["owner_user_id"]) if row.get("owner_user_id") else None,
                workflow_active=bool(row.get("workflow_active", False)),
                last_actor_user_id=str(row["last_actor_user_id"]) if row.get("last_actor_user_id") else None,
            )
            for row in rows
            if isinstance(row, dict)
        ]

    def list_review_actions(self) -> list[ReviewActionItem]:
        rows = self._request("GET", "/documents/home/review-actions")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid documents review-actions response")
        return [
            ReviewActionItem(
                document_id=str(row["document_id"]),
                version=int(row["version"]),
                title=str(row.get("title") or ""),
                status=DocumentStatus(str(row["status"])),
                action_required=str(row["action_required"]),
                owner_user_id=str(row["owner_user_id"]) if row.get("owner_user_id") else None,
            )
            for row in rows
            if isinstance(row, dict)
        ]

    def list_recent_documents(self) -> list[RecentDocumentItem]:
        rows = self._request("GET", "/documents/home/recent")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid documents recent response")
        return [
            RecentDocumentItem(
                document_id=str(row["document_id"]),
                version=int(row["version"]),
                title=str(row.get("title") or ""),
                status=DocumentStatus(str(row["status"])),
                owner_user_id=str(row["owner_user_id"]) if row.get("owner_user_id") else None,
                last_event_at=datetime.fromisoformat(str(row["last_event_at"])) if row.get("last_event_at") else None,
            )
            for row in rows
            if isinstance(row, dict)
        ]

    def list_released_documents(self) -> list[ReleasedDocumentItem]:
        rows = self._request("GET", "/documents/released")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid released documents response")
        return [
            ReleasedDocumentItem(
                document_id=str(row["document_id"]),
                version=int(row["version"]),
                title=str(row.get("title") or ""),
                valid_until=datetime.fromisoformat(str(row["valid_until"])) if row.get("valid_until") else None,
                released_at=datetime.fromisoformat(str(row["released_at"])) if row.get("released_at") else None,
                owner_user_id=str(row["owner_user_id"]) if row.get("owner_user_id") else None,
            )
            for row in rows
            if isinstance(row, dict)
        ]

    def get_capabilities(self) -> dict[str, bool]:
        payload = self._request("GET", "/documents/capabilities")
        if not isinstance(payload, dict):
            raise DocumentsBackendTransportError("invalid documents capabilities response")
        return {
            "can_create_new_documents": bool(payload.get("can_create_new_documents", False)),
            "can_administer_workflow_profiles": bool(payload.get("can_administer_workflow_profiles", False)),
            "can_import_docx": bool(payload.get("can_import_docx", False)),
        }

    def assign_workflow_roles(
        self,
        state: DocumentVersionState,
        *,
        editors: set[str],
        reviewers: set[str],
        approvers: set[str],
    ) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/assign-roles",
            body={
                "editors": sorted(editors),
                "reviewers": sorted(reviewers),
                "approvers": sorted(approvers),
            },
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def start_workflow(self, state: DocumentVersionState, *, profile_id: str | None = None) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/start",
            body={"profile_id": profile_id},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def complete_editing(self, state: DocumentVersionState, *, sign_intent: object | None = None) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/editing-complete",
            body=self._workflow_body(sign_intent),
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def accept_review(self, state: DocumentVersionState, *, sign_intent: object | None = None) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/review/accept",
            body=self._workflow_body(sign_intent),
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def reject_review(self, state: DocumentVersionState, reason: RejectionReason) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/review/reject",
            body={"template_text": reason.template_text, "free_text": reason.free_text},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def accept_approval(self, state: DocumentVersionState, *, sign_intent: object | None = None) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/approval/accept",
            body=self._workflow_body(sign_intent),
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def reject_approval(self, state: DocumentVersionState, reason: RejectionReason) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/approval/reject",
            body={"template_text": reason.template_text, "free_text": reason.free_text},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def abort_workflow(self, state: DocumentVersionState) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/abort",
            body={},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def create_document_version(
        self,
        document_id: str,
        version: int,
        *,
        owner_user_id: str | None = None,
        title: str = "",
        description: str | None = None,
        doc_type: str = "OTHER",
        control_class: str = "CONTROLLED",
        workflow_profile_id: str | None = None,
    ):
        payload = self._request(
            "POST",
            "/documents/versions/create",
            body={
                "document_id": document_id,
                "version": version,
                "owner_user_id": owner_user_id,
                "title": title,
                "description": description,
                "doc_type": doc_type,
                "control_class": control_class,
                "workflow_profile_id": workflow_profile_id,
            },
        )
        return self._state_from_response(payload)

    def ensure_source_pdf_for_signing(self, state: DocumentVersionState) -> Path:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/workflow/ensure-source-pdf",
            body={},
            if_match=self._if_match(state),
        )
        if not isinstance(payload, dict):
            raise DocumentsBackendTransportError("invalid ensure-source-pdf response")
        artifact_id = payload.get("artifact_id")
        if not artifact_id:
            raise DocumentsBackendTransportError("ensure-source-pdf did not return artifact_id")
        return self.download_artifact(str(artifact_id))

    def import_existing_pdf(self, state: DocumentVersionState, source_path: Path):
        file_bytes = source_path.read_bytes()
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/import-pdf",
            raw_body=file_bytes,
            content_type="application/pdf",
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def import_existing_docx(self, state: DocumentVersionState, source_path: Path):
        file_bytes = source_path.read_bytes()
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/import-docx",
            raw_body=file_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def update_document_header(
        self,
        document_id: str,
        *,
        workflow_profile_id: str | None = None,
        department: str | None = None,
        site: str | None = None,
        regulatory_scope: str | None = None,
        distribution_roles: list[str] | None = None,
        distribution_sites: list[str] | None = None,
        distribution_departments: list[str] | None = None,
        if_match: str | None = None,
    ) -> DocumentHeader:
        token = str(if_match or "").strip()
        if not token:
            raise ValueError("If-Match token is required for header update")
        row = self._request(
            "PUT",
            f"/documents/headers/{document_id}",
            body={
                "workflow_profile_id": workflow_profile_id,
                "department": department,
                "site": site,
                "regulatory_scope": regulatory_scope,
                "distribution_roles": distribution_roles,
                "distribution_sites": distribution_sites,
                "distribution_departments": distribution_departments,
            },
            if_match=token,
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid documents header response")
        return DocumentHeader(
            document_id=str(row["document_id"]),
            doc_type=DocumentType(str(row["doc_type"])),
            control_class=ControlClass(str(row["control_class"])),
            workflow_profile_id=str(row["workflow_profile_id"]),
            register_binding=bool(row.get("register_binding", True)),
            department=str(row["department"]) if row.get("department") is not None else None,
            site=str(row["site"]) if row.get("site") is not None else None,
            regulatory_scope=str(row["regulatory_scope"]) if row.get("regulatory_scope") is not None else None,
            distribution_roles=tuple(str(v) for v in row.get("distribution_roles", [])),
            distribution_sites=tuple(str(v) for v in row.get("distribution_sites", [])),
            distribution_departments=tuple(str(v) for v in row.get("distribution_departments", [])),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )

    def update_version_metadata(
        self,
        state: DocumentVersionState,
        *,
        title: str | None = None,
        description: str | None = None,
        valid_until: datetime | None = None,
        next_review_at: datetime | None = None,
        custom_fields: dict[str, object] | None = None,
    ) -> DocumentVersionState:
        payload = self._request(
            "PATCH",
            f"/documents/versions/{state.document_id}/{state.version}/metadata",
            body={
                "title": title,
                "description": description,
                "valid_until": valid_until.isoformat() if valid_until is not None else None,
                "next_review_at": next_review_at.isoformat() if next_review_at is not None else None,
                "custom_fields": custom_fields,
            },
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def list_workflow_comments(self, state: DocumentVersionState, *, context: str) -> list[dict[str, object]]:
        rows = self._request(
            "GET",
            f"/documents/versions/{state.document_id}/{state.version}/comments?context={context}",
        )
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid workflow comments list response")
        return [row for row in rows if isinstance(row, dict)]

    def get_workflow_comment_detail(self, comment_id: str) -> dict[str, object]:
        row = self._request("GET", f"/documents/comments/{comment_id}")
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow comment detail response")
        return row

    def sync_docx_comments(self, state: DocumentVersionState) -> list[dict[str, object]]:
        rows = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/comments/sync-docx",
            body={},
            if_match=self._if_match(state),
        )
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid docx comment sync response")
        return [row for row in rows if isinstance(row, dict)]

    def create_pdf_workflow_comment(
        self,
        state: DocumentVersionState,
        *,
        context: str,
        page_number: int,
        comment_text: str,
        anchor_json: str | None = None,
    ) -> dict[str, object]:
        row = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/comments",
            body={
                "context": context,
                "page_number": page_number,
                "comment_text": comment_text,
                "anchor_json": anchor_json,
            },
            if_match=self._if_match(state),
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow comment create response")
        return row

    def set_workflow_comment_status(
        self,
        comment_id: str,
        *,
        new_status: str,
        note: str | None = None,
        if_match: str | None = None,
    ) -> dict[str, object]:
        token = str(if_match or "").strip()
        if not token:
            raise ValueError("If-Match token is required for comment status mutation")
        row = self._request(
            "POST",
            f"/documents/comments/{comment_id}/status",
            body={"new_status": new_status, "note": note},
            if_match=token,
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow comment status response")
        return row

    def archive_approved(self, state: DocumentVersionState) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/lifecycle/archive",
            body={},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def extend_annual_validity(
        self,
        state: DocumentVersionState,
        *,
        duration_days: int,
        reason: str,
        review_outcome: str,
        sign_intent: object,
    ) -> tuple[DocumentVersionState, bool]:
        sign_body = self._workflow_body(sign_intent)
        sign_payload = sign_body.get("sign_intent")
        if not isinstance(sign_payload, dict):
            raise DocumentsBackendTransportError("sign_intent is required for annual validity extension")
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/lifecycle/extend-annual",
            body={
                "duration_days": duration_days,
                "reason": reason,
                "review_outcome": review_outcome,
                "sign_intent": sign_payload,
            },
            if_match=self._if_match(state),
        )
        if not isinstance(payload, dict):
            raise DocumentsBackendTransportError("invalid extend-annual response")
        state_payload = payload.get("state")
        if not isinstance(state_payload, dict):
            raise DocumentsBackendTransportError("invalid extend-annual state response")
        enriched = dict(state_payload)
        enriched["available_actions"] = self._coerce_available_actions(payload.get("available_actions"))
        return document_version_state_from_payload(enriched), bool(payload.get("is_maxed", False))

    def create_new_version_after_archive(self, state: DocumentVersionState, next_version: int) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/lifecycle/new-version-after-archive",
            body={"next_version": next_version},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def list_change_requests(self, state: DocumentVersionState) -> list[dict[str, object]]:
        rows = self._request(
            "GET",
            f"/documents/versions/{state.document_id}/{state.version}/change-requests",
        )
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid change requests list response")
        return [row for row in rows if isinstance(row, dict)]

    def add_change_request(
        self,
        state: DocumentVersionState,
        *,
        change_id: str,
        reason: str,
        impact_refs: list[str],
    ) -> DocumentVersionState:
        payload = self._request(
            "POST",
            f"/documents/versions/{state.document_id}/{state.version}/change-requests",
            body={"change_id": change_id, "reason": reason, "impact_refs": impact_refs},
            if_match=self._if_match(state),
        )
        return self._state_from_response(payload)

    def create_from_template(self, state: DocumentVersionState, source_path: Path) -> DocumentVersionState:
        return self.create_from_template_for_version(
            state.document_id,
            state.version,
            source_path,
            state=state,
        )

    def create_from_template_for_version(
        self,
        document_id: str,
        version: int,
        source_path: Path,
        *,
        state: DocumentVersionState | None,
    ) -> DocumentVersionState:
        file_bytes = source_path.read_bytes()
        suffix = source_path.suffix.lower()
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.template"
            if suffix == ".dotx"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        if_match = self._if_match(state) if state is not None else "none"
        payload = self._request(
            "POST",
            f"/documents/versions/{document_id}/{version}/create-from-template",
            raw_body=file_bytes,
            content_type=content_type,
            if_match=if_match,
        )
        return self._state_from_response(payload)

    def create_workflow_profile_definition(self, payload: dict[str, object], *, change_reason: str) -> dict[str, object]:
        row = self._request(
            "POST",
            "/documents/workflow-profiles/definitions",
            body={"payload": payload, "change_reason": change_reason},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow profile create response")
        return row

    def list_workflow_profile_versions(self, profile_code: str) -> list[dict[str, object]]:
        rows = self._request("GET", f"/documents/workflow-profiles/definitions/{profile_code}/versions")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid workflow profile versions response")
        return rows

    def create_workflow_profile_version(
        self,
        profile_code: str,
        payload: dict[str, object],
        *,
        change_reason: str,
    ) -> dict[str, object]:
        row = self._request(
            "POST",
            f"/documents/workflow-profiles/definitions/{profile_code}/versions",
            body={"payload": payload, "change_reason": change_reason},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow profile version response")
        return row

    def activate_workflow_profile_definition(self, profile_code: str, *, change_reason: str) -> dict[str, object]:
        row = self._request(
            "POST",
            f"/documents/workflow-profiles/definitions/{profile_code}/activate",
            body={"change_reason": change_reason},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow profile activate response")
        return row

    def deactivate_workflow_profile_definition(self, profile_code: str, *, change_reason: str) -> dict[str, object]:
        row = self._request(
            "POST",
            f"/documents/workflow-profiles/definitions/{profile_code}/deactivate",
            body={"change_reason": change_reason},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow profile deactivate response")
        return row

    def bind_document_type_default_profile(
        self,
        doc_type: str,
        profile_code: str,
        *,
        change_reason: str,
    ) -> dict[str, object]:
        row = self._request(
            "POST",
            "/documents/workflow-profiles/bindings",
            body={"doc_type": doc_type, "profile_code": profile_code, "change_reason": change_reason},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid workflow profile bind response")
        return row

    def list_workflow_profile_definitions(self, *, include_inactive: bool = True) -> list[dict[str, object]]:
        suffix = "?include_inactive=true" if include_inactive else "?include_inactive=false"
        rows = self._request("GET", f"/documents/workflow-profiles/definitions{suffix}")
        if not isinstance(rows, list):
            raise DocumentsBackendTransportError("invalid workflow profile list response")
        return rows

    @staticmethod
    def _parse_iso_datetime(raw: object) -> datetime:
        if not isinstance(raw, str) or not raw.strip():
            raise DocumentsBackendTransportError("invalid datetime in documents read response")
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))

    @classmethod
    def _read_session_from_payload(cls, row: dict[str, Any]) -> DocumentReadSession:
        return DocumentReadSession(
            session_id=str(row["session_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            opened_at=cls._parse_iso_datetime(row["opened_at"]),
        )

    @classmethod
    def _read_receipt_from_payload(cls, row: dict[str, Any]) -> DocumentReadReceipt:
        return DocumentReadReceipt(
            receipt_id=str(row["receipt_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            confirmed_at=cls._parse_iso_datetime(row["confirmed_at"]),
            source=str(row["source"]),
        )

    @classmethod
    def _tracked_session_from_payload(cls, row: dict[str, Any]) -> TrackedPdfReadSession:
        completed_raw = row.get("completed_at")
        completed_at = cls._parse_iso_datetime(completed_raw) if completed_raw else None
        return TrackedPdfReadSession(
            session_id=str(row["session_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            artifact_id=str(row["artifact_id"]) if row.get("artifact_id") else None,
            total_pages=int(row["total_pages"]),
            min_seconds_per_page=int(row["min_seconds_per_page"]),
            source=str(row["source"]),
            opened_at=cls._parse_iso_datetime(row["opened_at"]),
            completed_at=completed_at,
        )

    @classmethod
    def _read_progress_from_payload(cls, row: dict[str, Any]) -> PdfReadProgress:
        page_seconds_raw = row.get("page_seconds") or {}
        page_seconds: dict[int, int] = {}
        if isinstance(page_seconds_raw, dict):
            for key, value in page_seconds_raw.items():
                page_seconds[int(key)] = int(value)
        return PdfReadProgress(
            session_id=str(row["session_id"]),
            total_pages=int(row["total_pages"]),
            completed_pages=tuple(int(v) for v in row.get("completed_pages") or []),
            missing_pages=tuple(int(v) for v in row.get("missing_pages") or []),
            page_seconds=page_seconds,
            is_complete=bool(row.get("is_complete")),
        )

    def open_released_document(self, document_id: str, version: int) -> DocumentReadSession:
        row = self._request(
            "POST",
            "/documents/reads/open-released",
            body={"document_id": document_id, "version": version, "source": "training"},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid open-released read response")
        return self._read_session_from_payload(row)

    def confirm_released_document_read(
        self, document_id: str, version: int, *, source: str
    ) -> DocumentReadReceipt:
        row = self._request(
            "POST",
            "/documents/reads/confirm",
            body={"document_id": document_id, "version": version, "source": source},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid confirm read response")
        return self._read_receipt_from_payload(row)

    def get_read_receipt(self, document_id: str, version: int) -> DocumentReadReceipt | None:
        row = self._request("GET", f"/documents/reads/receipt/{document_id}/{version}")
        if row is None:
            return None
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid read receipt response")
        return self._read_receipt_from_payload(row)

    def start_tracked_pdf_read(
        self,
        document_id: str,
        version: int,
        *,
        artifact_id: str | None,
        total_pages: int,
        source: str,
        min_seconds_per_page: int = 10,
    ) -> TrackedPdfReadSession:
        row = self._request(
            "POST",
            "/documents/reads/tracked/start",
            body={
                "document_id": document_id,
                "version": version,
                "source": source,
                "artifact_id": artifact_id,
                "total_pages": total_pages,
                "min_seconds_per_page": min_seconds_per_page,
            },
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid tracked read start response")
        return self._tracked_session_from_payload(row)

    def record_page_dwell(self, session_id: str, *, page_number: int, dwell_seconds: int) -> PdfReadProgress:
        row = self._request(
            "POST",
            f"/documents/reads/tracked/{session_id}/dwell",
            body={"page_number": page_number, "dwell_seconds": dwell_seconds},
        )
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid page dwell response")
        return self._read_progress_from_payload(row)

    def get_pdf_read_progress(self, session_id: str) -> PdfReadProgress:
        row = self._request("GET", f"/documents/reads/tracked/{session_id}/progress")
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid read progress response")
        return self._read_progress_from_payload(row)

    def finalize_tracked_pdf_read(self, session_id: str, *, source: str) -> DocumentReadReceipt | None:
        row = self._request(
            "POST",
            f"/documents/reads/tracked/{session_id}/finalize",
            body={"source": source},
        )
        if row is None:
            return None
        if not isinstance(row, dict):
            raise DocumentsBackendTransportError("invalid finalize read response")
        return self._read_receipt_from_payload(row)
