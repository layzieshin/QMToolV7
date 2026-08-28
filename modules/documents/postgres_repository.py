"""PostgreSQL DocumentsRepository implementation for AP-029 PG01-C."""
from __future__ import annotations

import json
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentReadReceipt,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    PdfReadProgress,
    TrackedPdfReadSession,
    WorkflowCommentContext,
    WorkflowCommentRecord,
    WorkflowCommentSourceKind,
    WorkflowCommentStatus,
    WorkflowAssignments,
    WorkflowProfile,
)
from .repository import DocumentsRepository


class PostgresDocumentsRepository(DocumentsRepository):
    _SCHEMA = "documents"

    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)
        self._txn_local = threading.local()

    def adapt_sql(self, sql: str) -> str:
        adapted = sql.replace("?", "%s")
        adapted = adapted.replace(" is_active = 1", " is_active = true")
        adapted = adapted.replace(" is_active = 0", " is_active = false")
        adapted = adapted.replace("WHERE is_active = 1", "WHERE is_active = true")
        adapted = adapted.replace("AND is_active = 1", "AND is_active = true")
        return adapted

    @staticmethod
    def adapt_params(params: tuple[object, ...] | list[object]) -> tuple[object, ...]:
        return tuple(params)

    def _open_connection(self) -> psycopg.Connection:
        from .postgres_connection import _validate_runtime_identity

        conn = psycopg.connect(self._dsn, row_factory=dict_row)
        _validate_runtime_identity(conn)
        conn.execute(f"SET search_path TO {self._SCHEMA}, public")
        return conn

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(raw: str | datetime | None) -> datetime | None:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            if raw.tzinfo is None:
                return raw.replace(tzinfo=timezone.utc)
            return raw
        if not str(raw).strip():
            return None
        value = datetime.fromisoformat(str(raw))
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def upsert(self, state: DocumentVersionState) -> None:
        profile = state.workflow_profile
        profile_json = self._profile_to_json(profile)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_versions (
                    document_id, version, title, description, doc_type, control_class, workflow_profile_id, owner_user_id, status, workflow_active,
                    workflow_profile_json,
                    editors_json, reviewers_json, approvers_json, reviewed_by_json, approved_by_json,
                    edit_signature_done, valid_from, valid_until, next_review_at,
                    review_completed_at, review_completed_by, approval_completed_at, approval_completed_by,
                    released_at, archived_at, archived_by, superseded_by_version,
                    extension_count, last_extended_at, last_extended_by, last_extension_reason, last_extension_review_outcome,
                    custom_fields_json, last_event_id, last_event_at, last_actor_user_id,
                    created_at, created_by, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT(document_id, version) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    doc_type = excluded.doc_type,
                    control_class = excluded.control_class,
                    workflow_profile_id = excluded.workflow_profile_id,
                    owner_user_id = excluded.owner_user_id,
                    status = excluded.status,
                    workflow_active = excluded.workflow_active,
                    workflow_profile_json = excluded.workflow_profile_json,
                    editors_json = excluded.editors_json,
                    reviewers_json = excluded.reviewers_json,
                    approvers_json = excluded.approvers_json,
                    reviewed_by_json = excluded.reviewed_by_json,
                    approved_by_json = excluded.approved_by_json,
                    edit_signature_done = excluded.edit_signature_done,
                    valid_from = excluded.valid_from,
                    valid_until = excluded.valid_until,
                    next_review_at = excluded.next_review_at,
                    review_completed_at = excluded.review_completed_at,
                    review_completed_by = excluded.review_completed_by,
                    approval_completed_at = excluded.approval_completed_at,
                    approval_completed_by = excluded.approval_completed_by,
                    released_at = excluded.released_at,
                    archived_at = excluded.archived_at,
                    archived_by = excluded.archived_by,
                    superseded_by_version = excluded.superseded_by_version,
                    extension_count = excluded.extension_count,
                    last_extended_at = excluded.last_extended_at,
                    last_extended_by = excluded.last_extended_by,
                    last_extension_reason = excluded.last_extension_reason,
                    last_extension_review_outcome = excluded.last_extension_review_outcome,
                    custom_fields_json = excluded.custom_fields_json,
                    last_event_id = excluded.last_event_id,
                    last_event_at = excluded.last_event_at,
                    last_actor_user_id = excluded.last_actor_user_id,
                    created_at = COALESCE(documents.document_versions.created_at, excluded.created_at),
                    created_by = COALESCE(documents.document_versions.created_by, excluded.created_by),
                    updated_at = excluded.updated_at
                """,
                (
                    state.document_id,
                    state.version,
                    state.title,
                    state.description,
                    state.doc_type.value,
                    state.control_class.value,
                    state.workflow_profile_id,
                    state.owner_user_id,
                    state.status.value,
                    state.workflow_active,
                    profile_json,
                    json.dumps(sorted(state.assignments.editors), ensure_ascii=True),
                    json.dumps(sorted(state.assignments.reviewers), ensure_ascii=True),
                    json.dumps(sorted(state.assignments.approvers), ensure_ascii=True),
                    json.dumps(sorted(state.reviewed_by), ensure_ascii=True),
                    json.dumps(sorted(state.approved_by), ensure_ascii=True),
                    state.edit_signature_done,
                    state.valid_from.isoformat() if state.valid_from else None,
                    state.valid_until.isoformat() if state.valid_until else None,
                    state.next_review_at.isoformat() if state.next_review_at else None,
                    state.review_completed_at.isoformat() if state.review_completed_at else None,
                    state.review_completed_by,
                    state.approval_completed_at.isoformat() if state.approval_completed_at else None,
                    state.approval_completed_by,
                    state.released_at.isoformat() if state.released_at else None,
                    state.archived_at.isoformat() if state.archived_at else None,
                    state.archived_by,
                    state.superseded_by_version,
                    state.extension_count,
                    state.last_extended_at.isoformat() if state.last_extended_at else None,
                    state.last_extended_by,
                    state.last_extension_reason,
                    state.last_extension_review_outcome,
                    json.dumps(state.custom_fields, ensure_ascii=True),
                    state.last_event_id,
                    state.last_event_at.isoformat() if state.last_event_at else None,
                    state.last_actor_user_id,
                    state.created_at.isoformat() if state.created_at else None,
                    state.created_by,
                    self._utcnow_iso(),
                ),
            )
            self._commit_if_needed(conn)

    def upsert_header(self, header: DocumentHeader) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_headers (
                    document_id, doc_type, control_class, workflow_profile_id, register_binding,
                    department, site, regulatory_scope,
                    distribution_roles_json, distribution_sites_json, distribution_departments_json,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(document_id) DO UPDATE SET
                    doc_type = excluded.doc_type,
                    control_class = excluded.control_class,
                    workflow_profile_id = excluded.workflow_profile_id,
                    register_binding = excluded.register_binding,
                    department = excluded.department,
                    site = excluded.site,
                    regulatory_scope = excluded.regulatory_scope,
                    distribution_roles_json = excluded.distribution_roles_json,
                    distribution_sites_json = excluded.distribution_sites_json,
                    distribution_departments_json = excluded.distribution_departments_json,
                    updated_at = excluded.updated_at
                """,
                (
                    header.document_id,
                    header.doc_type.value,
                    header.control_class.value,
                    header.workflow_profile_id,
                    header.register_binding,
                    header.department,
                    header.site,
                    header.regulatory_scope,
                    json.dumps(sorted(header.distribution_roles), ensure_ascii=True),
                    json.dumps(sorted(header.distribution_sites), ensure_ascii=True),
                    json.dumps(sorted(header.distribution_departments), ensure_ascii=True),
                    header.created_at.isoformat(),
                    self._utcnow_iso(),
                ),
            )
            self._commit_if_needed(conn)

    def get_header(self, document_id: str) -> DocumentHeader | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents.document_headers WHERE document_id = %s",
                (document_id,),
            ).fetchone()
        return self._row_to_header(row) if row else None

    def get(self, document_id: str, version: int) -> DocumentVersionState | None:
        with self._connect() as conn:
            sql = (
                "SELECT * FROM documents.document_versions "
                "WHERE document_id = %s AND version = %s"
            )
            if self._txn_conn() is not None:
                sql += " FOR UPDATE"
            row = conn.execute(sql, (document_id, version)).fetchone()
        return self._row_to_state(row) if row else None

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents.document_versions WHERE status = %s ORDER BY document_id ASC, version ASC",
                (status.value,),
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def list_versions(self, document_id: str) -> list[DocumentVersionState]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM documents.document_versions
                WHERE document_id = %s
                ORDER BY version ASC
                """,
                (document_id,),
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def add_artifact(self, artifact: DocumentArtifact) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_artifacts (
                    artifact_id, document_id, version, artifact_type, source_type, storage_key,
                    original_filename, mime_type, sha256, size_bytes, is_current, metadata_json, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    artifact.artifact_id,
                    artifact.document_id,
                    artifact.version,
                    artifact.artifact_type.value,
                    artifact.source_type.value,
                    artifact.storage_key,
                    artifact.original_filename,
                    artifact.mime_type,
                    artifact.sha256,
                    artifact.size_bytes,
                    artifact.is_current,
                    json.dumps(artifact.metadata, ensure_ascii=True),
                    artifact.created_at.isoformat(),
                ),
            )
            self._commit_if_needed(conn)

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM documents.document_artifacts
                WHERE document_id = %s AND version = %s
                ORDER BY created_at ASC
                """,
                (document_id, version),
            ).fetchall()
        return [self._row_to_artifact(row) for row in rows]

    def get_artifact_by_id(self, artifact_id: str) -> DocumentArtifact | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents.document_artifacts WHERE artifact_id = %s",
                (artifact_id,),
            ).fetchone()
        return self._row_to_artifact(row) if row is not None else None

    def delete_artifact(self, artifact_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents.document_artifacts WHERE artifact_id = %s", (artifact_id,))
            self._commit_if_needed(conn)

    def mark_current_artifact(
        self,
        document_id: str,
        version: int,
        artifact_type: ArtifactType,
        artifact_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents.document_artifacts
                SET is_current = false
                WHERE document_id = %s AND version = %s AND artifact_type = %s
                """,
                (document_id, version, artifact_type.value),
            )
            conn.execute(
                """
                UPDATE documents.document_artifacts
                SET is_current = true
                WHERE artifact_id = %s
                """,
                (artifact_id,),
            )
            self._commit_if_needed(conn)

    def _txn_conn(self) -> psycopg.Connection | None:
        return getattr(self._txn_local, "conn", None)

    def _set_txn_conn(self, conn: psycopg.Connection | None) -> None:
        if conn is None:
            if hasattr(self._txn_local, "conn"):
                delattr(self._txn_local, "conn")
            return
        self._txn_local.conn = conn

    @contextmanager
    def write_transaction(self):
        if self._txn_conn() is not None:
            yield
            return
        conn = self._open_connection()
        try:
            conn.execute("BEGIN")
            self._set_txn_conn(conn)
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._set_txn_conn(None)
            conn.close()

    @contextmanager
    def _connect(self):
        existing = self._txn_conn()
        if existing is not None:
            yield existing
            return
        conn = self._open_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _commit_if_needed(self, conn: psycopg.Connection) -> None:
        txn = self._txn_conn()
        if txn is None or conn is not txn:
            conn.commit()

    @staticmethod
    def _profile_to_json(profile: WorkflowProfile | None) -> str | None:
        if profile is None:
            return None
        payload = {
            "profile_id": profile.profile_id,
            "label": profile.label,
            "phases": [phase.value for phase in profile.phases],
            "four_eyes_required": profile.four_eyes_required,
            "control_class": profile.control_class.value,
            "signature_required_transitions": list(profile.signature_required_transitions),
            "requires_editors": profile.requires_editors,
            "requires_reviewers": profile.requires_reviewers,
            "requires_approvers": profile.requires_approvers,
            "allows_content_changes": profile.allows_content_changes,
            "release_evidence_mode": profile.release_evidence_mode,
        }
        return json.dumps(payload, ensure_ascii=True)

    @staticmethod
    def _profile_from_json(raw: str | None) -> WorkflowProfile | None:
        if not raw:
            return None
        data = json.loads(raw)
        return WorkflowProfile(
            profile_id=str(data["profile_id"]),
            label=str(data["label"]),
            phases=tuple(DocumentStatus(str(value)) for value in data["phases"]),
            four_eyes_required=bool(data["four_eyes_required"]),
            control_class=PostgresDocumentsRepository._parse_control_class(
                data.get("control_class", data.get("doc_type", "CONTROLLED"))
            ),
            signature_required_transitions=tuple(str(v) for v in data.get("signature_required_transitions", [])),
            requires_editors=bool(data.get("requires_editors", True)),
            requires_reviewers=bool(data.get("requires_reviewers", True)),
            requires_approvers=bool(data.get("requires_approvers", True)),
            allows_content_changes=bool(data.get("allows_content_changes", True)),
            release_evidence_mode=str(data.get("release_evidence_mode", "WORKFLOW")),
        )

    @staticmethod
    def _row_to_header(row: dict[str, object]) -> DocumentHeader:
        return DocumentHeader(
            document_id=str(row["document_id"]),
            doc_type=PostgresDocumentsRepository._parse_doc_type(row["doc_type"]),
            control_class=PostgresDocumentsRepository._parse_control_class(row["control_class"]),
            workflow_profile_id=str(row["workflow_profile_id"]),
            register_binding=bool(row["register_binding"]),
            department=str(row["department"]) if row["department"] else None,
            site=str(row["site"]) if row["site"] else None,
            regulatory_scope=str(row["regulatory_scope"]) if row["regulatory_scope"] else None,
            distribution_roles=tuple(
                sorted(
                    json.loads(str(row["distribution_roles_json"]))
                    if "distribution_roles_json" in row.keys() and row["distribution_roles_json"]
                    else []
                )
            ),
            distribution_sites=tuple(
                sorted(
                    json.loads(str(row["distribution_sites_json"]))
                    if "distribution_sites_json" in row.keys() and row["distribution_sites_json"]
                    else []
                )
            ),
            distribution_departments=tuple(
                sorted(
                    json.loads(str(row["distribution_departments_json"]))
                    if "distribution_departments_json" in row.keys() and row["distribution_departments_json"]
                    else []
                )
            ),
            created_at=PostgresDocumentsRepository._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
            updated_at=PostgresDocumentsRepository._parse_dt(str(row["updated_at"])) or datetime.now(timezone.utc),
        )

    def _row_to_state(self, row: dict[str, object]) -> DocumentVersionState:
        return DocumentVersionState(
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            title=str(row["title"]) if "title" in row.keys() else "",
            description=str(row["description"]) if "description" in row.keys() and row["description"] else None,
            doc_type=self._parse_doc_type(row["doc_type"]) if "doc_type" in row.keys() else DocumentType.OTHER,
            control_class=self._parse_control_class(row["control_class"]) if "control_class" in row.keys() else ControlClass.RECORD,
            workflow_profile_id=str(row["workflow_profile_id"]) if "workflow_profile_id" in row.keys() else "long_release",
            owner_user_id=str(row["owner_user_id"]) if row["owner_user_id"] else None,
            status=DocumentStatus(str(row["status"])),
            workflow_active=bool(row["workflow_active"]),
            workflow_profile=self._profile_from_json(row["workflow_profile_json"]),
            assignments=WorkflowAssignments(
                editors=frozenset(json.loads(row["editors_json"])),
                reviewers=frozenset(json.loads(row["reviewers_json"])),
                approvers=frozenset(json.loads(row["approvers_json"])),
            ),
            reviewed_by=frozenset(json.loads(row["reviewed_by_json"])),
            approved_by=frozenset(json.loads(row["approved_by_json"])),
            edit_signature_done=bool(row["edit_signature_done"]),
            valid_from=self._parse_dt(row["valid_from"]) if "valid_from" in row.keys() else None,
            valid_until=self._parse_dt(row["valid_until"]) if "valid_until" in row.keys() else None,
            next_review_at=self._parse_dt(row["next_review_at"]) if "next_review_at" in row.keys() else None,
            review_completed_at=self._parse_dt(row["review_completed_at"]) if "review_completed_at" in row.keys() else None,
            review_completed_by=str(row["review_completed_by"]) if "review_completed_by" in row.keys() and row["review_completed_by"] else None,
            approval_completed_at=self._parse_dt(row["approval_completed_at"]) if "approval_completed_at" in row.keys() else None,
            approval_completed_by=str(row["approval_completed_by"]) if "approval_completed_by" in row.keys() and row["approval_completed_by"] else None,
            released_at=self._parse_dt(row["released_at"]),
            archived_at=self._parse_dt(row["archived_at"]) if "archived_at" in row.keys() else None,
            archived_by=str(row["archived_by"]) if "archived_by" in row.keys() and row["archived_by"] else None,
            superseded_by_version=int(row["superseded_by_version"]) if "superseded_by_version" in row.keys() and row["superseded_by_version"] is not None else None,
            extension_count=int(row["extension_count"]),
            last_extended_at=self._parse_dt(row["last_extended_at"]) if "last_extended_at" in row.keys() else None,
            last_extended_by=str(row["last_extended_by"]) if "last_extended_by" in row.keys() and row["last_extended_by"] else None,
            last_extension_reason=(
                str(row["last_extension_reason"])
                if "last_extension_reason" in row.keys() and row["last_extension_reason"]
                else None
            ),
            last_extension_review_outcome=(
                str(row["last_extension_review_outcome"])
                if "last_extension_review_outcome" in row.keys() and row["last_extension_review_outcome"]
                else None
            ),
            custom_fields=json.loads(str(row["custom_fields_json"])) if "custom_fields_json" in row.keys() and row["custom_fields_json"] else {},
            last_event_id=str(row["last_event_id"]) if "last_event_id" in row.keys() and row["last_event_id"] else None,
            last_event_at=self._parse_dt(row["last_event_at"]) if "last_event_at" in row.keys() else None,
            last_actor_user_id=str(row["last_actor_user_id"]) if "last_actor_user_id" in row.keys() and row["last_actor_user_id"] else None,
            created_at=self._parse_dt(row["created_at"]) if "created_at" in row.keys() else None,
            created_by=str(row["created_by"]) if "created_by" in row.keys() and row["created_by"] else None,
        )

    @staticmethod
    def _row_to_artifact(row: dict[str, object]) -> DocumentArtifact:
        return DocumentArtifact(
            artifact_id=str(row["artifact_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            artifact_type=ArtifactType(str(row["artifact_type"])),
            source_type=ArtifactSourceType(str(row["source_type"])),
            storage_key=str(row["storage_key"]),
            original_filename=str(row["original_filename"]),
            mime_type=str(row["mime_type"]),
            sha256=str(row["sha256"]),
            size_bytes=int(row["size_bytes"]),
            is_current=bool(row["is_current"]),
            metadata=json.loads(str(row["metadata_json"])),
            created_at=PostgresDocumentsRepository._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
        )

    @staticmethod
    def _parse_doc_type(raw: object) -> DocumentType:
        value = str(raw)
        legacy_map: dict[str, DocumentType] = {
            "CONTROLLED": DocumentType.OTHER,
            "CONTROLLED_SHORT": DocumentType.OTHER,
            "EXTERNAL": DocumentType.EXT,
            "RECORD": DocumentType.OTHER,
        }
        if value in legacy_map:
            return legacy_map[value]
        return DocumentType(value)

    @staticmethod
    def _parse_control_class(raw: object) -> ControlClass:
        value = str(raw)
        if value in {"VA", "AA", "FB", "LS"}:
            return ControlClass.CONTROLLED
        if value == "EXT":
            return ControlClass.EXTERNAL
        if value == "OTHER":
            return ControlClass.RECORD
        return ControlClass(value)

    # --- Read Receipts ---

    def create_read_receipt(self, receipt: DocumentReadReceipt) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_read_receipts
                (receipt_id, user_id, document_id, version, confirmed_at, source)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, document_id, version) DO UPDATE SET
                    receipt_id = EXCLUDED.receipt_id,
                    confirmed_at = EXCLUDED.confirmed_at,
                    source = EXCLUDED.source
                """,
                (
                    receipt.receipt_id,
                    receipt.user_id,
                    receipt.document_id,
                    receipt.version,
                    receipt.confirmed_at.isoformat(),
                    receipt.source,
                ),
            )
            self._commit_if_needed(conn)

    def get_read_receipt(self, user_id: str, document_id: str, version: int) -> DocumentReadReceipt | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents.document_read_receipts WHERE user_id = %s AND document_id = %s AND version = %s",
                (user_id, document_id, version),
            ).fetchone()
        if row is None:
            return None
        return DocumentReadReceipt(
            receipt_id=str(row["receipt_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            confirmed_at=self._parse_dt(str(row["confirmed_at"])) or datetime.now(timezone.utc),
            source=str(row["source"]),
        )

    # --- Workflow comments ---

    def upsert_workflow_comment(self, record: WorkflowCommentRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_workflow_comments (
                    comment_id, ref_no, document_id, version, context, source_kind, source_comment_key, artifact_id,
                    page_number, anchor_json, author_display, source_created_at, preview_text, full_text,
                    status, status_note, status_changed_by, status_changed_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(comment_id) DO UPDATE SET
                    source_comment_key = excluded.source_comment_key,
                    author_display = excluded.author_display,
                    source_created_at = excluded.source_created_at,
                    preview_text = excluded.preview_text,
                    full_text = excluded.full_text,
                    page_number = excluded.page_number,
                    anchor_json = excluded.anchor_json,
                    status = excluded.status,
                    status_note = excluded.status_note,
                    status_changed_by = excluded.status_changed_by,
                    status_changed_at = excluded.status_changed_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record.comment_id,
                    record.ref_no,
                    record.document_id,
                    record.version,
                    record.context.value,
                    record.source_kind.value,
                    record.source_comment_key,
                    record.artifact_id,
                    record.page_number,
                    record.anchor_json,
                    record.author_display,
                    record.source_created_at.isoformat() if record.source_created_at else None,
                    record.preview_text,
                    record.full_text,
                    record.status.value,
                    record.status_note,
                    record.status_changed_by,
                    record.status_changed_at.isoformat() if record.status_changed_at else None,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            self._commit_if_needed(conn)

    def get_workflow_comment(self, comment_id: str) -> WorkflowCommentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents.document_workflow_comments WHERE comment_id = %s",
                (comment_id,),
            ).fetchone()
        return self._row_to_workflow_comment(row) if row else None

    def list_workflow_comments(
        self, document_id: str, version: int, context: WorkflowCommentContext
    ) -> list[WorkflowCommentRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM documents.document_workflow_comments
                WHERE document_id = %s AND version = %s AND context = %s
                ORDER BY created_at DESC
                """,
                (document_id, version, context.value),
            ).fetchall()
        return [self._row_to_workflow_comment(row) for row in rows]

    # --- Tracked PDF read ---

    def create_pdf_read_session(self, session: TrackedPdfReadSession) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_pdf_read_sessions
                (session_id, user_id, document_id, version, artifact_id, total_pages, min_seconds_per_page, source, opened_at, completed_at, completion_result)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    document_id = EXCLUDED.document_id,
                    version = EXCLUDED.version,
                    artifact_id = EXCLUDED.artifact_id,
                    total_pages = EXCLUDED.total_pages,
                    min_seconds_per_page = EXCLUDED.min_seconds_per_page,
                    source = EXCLUDED.source,
                    opened_at = EXCLUDED.opened_at,
                    completed_at = EXCLUDED.completed_at,
                    completion_result = EXCLUDED.completion_result
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.document_id,
                    session.version,
                    session.artifact_id,
                    session.total_pages,
                    session.min_seconds_per_page,
                    session.source,
                    session.opened_at.isoformat(),
                    session.completed_at.isoformat() if session.completed_at else None,
                    None,
                ),
            )
            self._commit_if_needed(conn)

    def get_pdf_read_session(self, session_id: str) -> TrackedPdfReadSession | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents.document_pdf_read_sessions WHERE session_id = %s",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return TrackedPdfReadSession(
            session_id=str(row["session_id"]),
            user_id=str(row["user_id"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            artifact_id=str(row["artifact_id"]) if row["artifact_id"] else None,
            total_pages=int(row["total_pages"]),
            min_seconds_per_page=int(row["min_seconds_per_page"]),
            source=str(row["source"]),
            opened_at=self._parse_dt(str(row["opened_at"])) or datetime.now(timezone.utc),
            completed_at=self._parse_dt(str(row["completed_at"])) if row["completed_at"] else None,
        )

    def update_pdf_read_page_progress(
        self, session_id: str, page_number: int, accumulated_seconds: int, reached_threshold: bool
    ) -> None:
        now = self._utcnow_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents.document_pdf_read_page_progress
                (session_id, page_number, accumulated_seconds, reached_threshold, first_seen_at, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(session_id, page_number) DO UPDATE SET
                    accumulated_seconds = excluded.accumulated_seconds,
                    reached_threshold = excluded.reached_threshold,
                    last_seen_at = excluded.last_seen_at
                """,
                (session_id, page_number, accumulated_seconds, reached_threshold, now, now),
            )
            self._commit_if_needed(conn)

    def get_pdf_read_progress(self, session_id: str) -> PdfReadProgress | None:
        with self._connect() as conn:
            session_row = conn.execute(
                "SELECT total_pages, min_seconds_per_page FROM documents.document_pdf_read_sessions WHERE session_id = %s",
                (session_id,),
            ).fetchone()
            if session_row is None:
                return None
            rows = conn.execute(
                "SELECT page_number, accumulated_seconds, reached_threshold FROM documents.document_pdf_read_page_progress WHERE session_id = %s",
                (session_id,),
            ).fetchall()
        total_pages = int(session_row["total_pages"])
        completed = sorted(int(r["page_number"]) for r in rows if bool(r["reached_threshold"]))
        page_seconds = {int(r["page_number"]): int(r["accumulated_seconds"]) for r in rows}
        missing = tuple(page for page in range(1, total_pages + 1) if page not in completed)
        return PdfReadProgress(
            session_id=session_id,
            total_pages=total_pages,
            completed_pages=tuple(completed),
            missing_pages=missing,
            page_seconds=page_seconds,
            is_complete=len(missing) == 0 and total_pages > 0,
        )

    def complete_pdf_read_session(self, session_id: str, *, completed_at: str, completion_result: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents.document_pdf_read_sessions
                SET completed_at = %s, completion_result = %s
                WHERE session_id = %s
                """,
                (completed_at, completion_result, session_id),
            )
            self._commit_if_needed(conn)

    def _row_to_workflow_comment(self, row: dict[str, object]) -> WorkflowCommentRecord:
        return WorkflowCommentRecord(
            comment_id=str(row["comment_id"]),
            ref_no=str(row["ref_no"]),
            document_id=str(row["document_id"]),
            version=int(row["version"]),
            context=WorkflowCommentContext(str(row["context"])),
            source_kind=WorkflowCommentSourceKind(str(row["source_kind"])),
            source_comment_key=str(row["source_comment_key"]),
            artifact_id=str(row["artifact_id"]) if row["artifact_id"] else None,
            page_number=int(row["page_number"]) if row["page_number"] is not None else None,
            anchor_json=str(row["anchor_json"]) if row["anchor_json"] else None,
            author_display=str(row["author_display"]) if row["author_display"] else None,
            source_created_at=self._parse_dt(str(row["source_created_at"])) if row["source_created_at"] else None,
            preview_text=str(row["preview_text"]),
            full_text=str(row["full_text"]),
            status=WorkflowCommentStatus(str(row["status"])),
            status_note=str(row["status_note"]) if row["status_note"] else None,
            status_changed_by=str(row["status_changed_by"]) if row["status_changed_by"] else None,
            status_changed_at=self._parse_dt(str(row["status_changed_at"])) if row["status_changed_at"] else None,
            created_at=self._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
            updated_at=self._parse_dt(str(row["updated_at"])) or datetime.now(timezone.utc),
        )
