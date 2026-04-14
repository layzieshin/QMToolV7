from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .contracts import (
    ArtifactSourceType,
    ArtifactType,
    ControlClass,
    DocumentArtifact,
    DocumentHeader,
    DocumentStatus,
    DocumentType,
    DocumentVersionState,
    WorkflowAssignments,
    WorkflowProfile,
)
from .repository import DocumentsRepository


class SQLiteDocumentsRepository(DocumentsRepository):
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = db_path
        self._schema_path = schema_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @staticmethod
    def _utcnow_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_dt(raw: str | None) -> datetime | None:
        if raw is None or not str(raw).strip():
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
                INSERT INTO document_versions (
                    document_id, version, title, description, doc_type, control_class, workflow_profile_id, owner_user_id, status, workflow_active,
                    workflow_profile_json,
                    editors_json, reviewers_json, approvers_json, reviewed_by_json, approved_by_json,
                    edit_signature_done, valid_from, valid_until, next_review_at,
                    review_completed_at, review_completed_by, approval_completed_at, approval_completed_by,
                    released_at, archived_at, archived_by, superseded_by_version,
                    extension_count, custom_fields_json, last_event_id, last_event_at, last_actor_user_id, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?
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
                    custom_fields_json = excluded.custom_fields_json,
                    last_event_id = excluded.last_event_id,
                    last_event_at = excluded.last_event_at,
                    last_actor_user_id = excluded.last_actor_user_id,
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
                    1 if state.workflow_active else 0,
                    profile_json,
                    json.dumps(sorted(state.assignments.editors), ensure_ascii=True),
                    json.dumps(sorted(state.assignments.reviewers), ensure_ascii=True),
                    json.dumps(sorted(state.assignments.approvers), ensure_ascii=True),
                    json.dumps(sorted(state.reviewed_by), ensure_ascii=True),
                    json.dumps(sorted(state.approved_by), ensure_ascii=True),
                    1 if state.edit_signature_done else 0,
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
                    json.dumps(state.custom_fields, ensure_ascii=True),
                    state.last_event_id,
                    state.last_event_at.isoformat() if state.last_event_at else None,
                    state.last_actor_user_id,
                    self._utcnow_iso(),
                ),
            )
            conn.commit()

    def upsert_header(self, header: DocumentHeader) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_headers (
                    document_id, doc_type, control_class, workflow_profile_id, register_binding,
                    department, site, regulatory_scope, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    doc_type = excluded.doc_type,
                    control_class = excluded.control_class,
                    workflow_profile_id = excluded.workflow_profile_id,
                    register_binding = excluded.register_binding,
                    department = excluded.department,
                    site = excluded.site,
                    regulatory_scope = excluded.regulatory_scope,
                    updated_at = excluded.updated_at
                """,
                (
                    header.document_id,
                    header.doc_type.value,
                    header.control_class.value,
                    header.workflow_profile_id,
                    1 if header.register_binding else 0,
                    header.department,
                    header.site,
                    header.regulatory_scope,
                    header.created_at.isoformat(),
                    self._utcnow_iso(),
                ),
            )
            conn.commit()

    def get_header(self, document_id: str) -> DocumentHeader | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_headers WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        return self._row_to_header(row) if row else None

    def get(self, document_id: str, version: int) -> DocumentVersionState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM document_versions WHERE document_id = ? AND version = ?",
                (document_id, version),
            ).fetchone()
        return self._row_to_state(row) if row else None

    def list_by_status(self, status: DocumentStatus) -> list[DocumentVersionState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM document_versions WHERE status = ? ORDER BY document_id ASC, version ASC",
                (status.value,),
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def list_versions(self, document_id: str) -> list[DocumentVersionState]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_versions
                WHERE document_id = ?
                ORDER BY version ASC
                """,
                (document_id,),
            ).fetchall()
        return [self._row_to_state(row) for row in rows]

    def add_artifact(self, artifact: DocumentArtifact) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO document_artifacts (
                    artifact_id, document_id, version, artifact_type, source_type, storage_key,
                    original_filename, mime_type, sha256, size_bytes, is_current, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if artifact.is_current else 0,
                    json.dumps(artifact.metadata, ensure_ascii=True),
                    artifact.created_at.isoformat(),
                ),
            )
            conn.commit()

    def list_artifacts(self, document_id: str, version: int) -> list[DocumentArtifact]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_artifacts
                WHERE document_id = ? AND version = ?
                ORDER BY created_at ASC
                """,
                (document_id, version),
            ).fetchall()
        return [self._row_to_artifact(row) for row in rows]

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
                UPDATE document_artifacts
                SET is_current = 0
                WHERE document_id = ? AND version = ? AND artifact_type = ?
                """,
                (document_id, version, artifact_type.value),
            )
            conn.execute(
                """
                UPDATE document_artifacts
                SET is_current = 1
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            )
            conn.commit()

    def _ensure_schema(self) -> None:
        sql = self._schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            self._ensure_document_headers_migration(conn)
            self._ensure_document_versions_migration(conn)
            conn.commit()

    @staticmethod
    def _ensure_document_headers_migration(conn: sqlite3.Connection) -> None:
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='document_headers'"
        ).fetchone()
        if table_exists is None:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_headers (
                    document_id TEXT PRIMARY KEY,
                    doc_type TEXT NOT NULL DEFAULT 'OTHER',
                    control_class TEXT NOT NULL DEFAULT 'CONTROLLED',
                    workflow_profile_id TEXT NOT NULL DEFAULT 'long_release',
                    register_binding INTEGER NOT NULL DEFAULT 1,
                    department TEXT,
                    site TEXT,
                    regulatory_scope TEXT,
                    created_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00',
                    updated_at TEXT NOT NULL DEFAULT '1970-01-01T00:00:00'
                )
                """
            )
        else:
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(document_headers)").fetchall()}
            if "control_class" not in cols:
                conn.execute("ALTER TABLE document_headers ADD COLUMN control_class TEXT NOT NULL DEFAULT 'CONTROLLED'")

    @staticmethod
    def _ensure_document_versions_migration(conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(document_versions)").fetchall()}
        alter_specs = [
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("description", "TEXT"),
            ("doc_type", "TEXT NOT NULL DEFAULT 'OTHER'"),
            ("control_class", "TEXT NOT NULL DEFAULT 'CONTROLLED'"),
            ("workflow_profile_id", "TEXT NOT NULL DEFAULT 'long_release'"),
            ("owner_user_id", "TEXT"),
            ("edit_signature_done", "INTEGER NOT NULL DEFAULT 0"),
            ("valid_from", "TEXT"),
            ("valid_until", "TEXT"),
            ("next_review_at", "TEXT"),
            ("review_completed_at", "TEXT"),
            ("review_completed_by", "TEXT"),
            ("approval_completed_at", "TEXT"),
            ("approval_completed_by", "TEXT"),
            ("archived_at", "TEXT"),
            ("archived_by", "TEXT"),
            ("superseded_by_version", "INTEGER"),
            ("custom_fields_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("last_event_id", "TEXT"),
            ("last_event_at", "TEXT"),
            ("last_actor_user_id", "TEXT"),
        ]
        for col_name, sql_type in alter_specs:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE document_versions ADD COLUMN {col_name} {sql_type}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
            control_class=SQLiteDocumentsRepository._parse_control_class(
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
    def _row_to_header(row: sqlite3.Row) -> DocumentHeader:
        return DocumentHeader(
            document_id=str(row["document_id"]),
            doc_type=SQLiteDocumentsRepository._parse_doc_type(row["doc_type"]),
            control_class=SQLiteDocumentsRepository._parse_control_class(row["control_class"]),
            workflow_profile_id=str(row["workflow_profile_id"]),
            register_binding=bool(row["register_binding"]),
            department=str(row["department"]) if row["department"] else None,
            site=str(row["site"]) if row["site"] else None,
            regulatory_scope=str(row["regulatory_scope"]) if row["regulatory_scope"] else None,
            created_at=SQLiteDocumentsRepository._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
            updated_at=SQLiteDocumentsRepository._parse_dt(str(row["updated_at"])) or datetime.now(timezone.utc),
        )

    def _row_to_state(self, row: sqlite3.Row) -> DocumentVersionState:
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
            custom_fields=json.loads(str(row["custom_fields_json"])) if "custom_fields_json" in row.keys() and row["custom_fields_json"] else {},
            last_event_id=str(row["last_event_id"]) if "last_event_id" in row.keys() and row["last_event_id"] else None,
            last_event_at=self._parse_dt(row["last_event_at"]) if "last_event_at" in row.keys() else None,
            last_actor_user_id=str(row["last_actor_user_id"]) if "last_actor_user_id" in row.keys() and row["last_actor_user_id"] else None,
        )

    @staticmethod
    def _row_to_artifact(row: sqlite3.Row) -> DocumentArtifact:
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
            created_at=SQLiteDocumentsRepository._parse_dt(str(row["created_at"])) or datetime.now(timezone.utc),
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

