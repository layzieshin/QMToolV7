from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .contracts import ControlClass, DocumentStatus, DocumentType, WorkflowProfile
from .errors import ValidationError
from .workflow_profile_runtime_adapter import (
    normalize_legacy_status_for_storage,
    runtime_status_from_relational,
    runtime_transition_key_from_relational,
)
from .bootstrap_provenance import DocumentsBootstrapProvenance

_ALLOWED_PROFILE_STATUSES = frozenset({"DRAFT", "IN_REVIEW", "IN_APPROVAL", "APPROVED"})
_ALLOWED_ROLES = frozenset({"EDITOR", "REVIEWER", "APPROVER", "QMB", "NONE"})
_ALLOWED_POLICIES = frozenset({"ONE_OF_POOL", "ALL_ASSIGNED", "NONE"})
_ENGINE_POLICIES = frozenset({"ONE_OF_POOL", "NONE"})


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_legacy_status(status: str) -> str:
    """Compatibility wrapper — storage normalization lives in the runtime adapter."""
    return normalize_legacy_status_for_storage(status)


@dataclass(frozen=True)
class WorkflowProfileTransitionDefinition:
    transition_no: int
    from_status: str
    to_status: str
    required_role: str
    decision_policy: str
    signature_required: bool
    four_eyes_required: bool
    revoke_if_changed: bool = False
    deadline_seconds: int | None = None
    is_enabled: bool = True

    def semantic_payload(self) -> dict[str, object]:
        return {
            "transition_no": self.transition_no,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "required_role": self.required_role,
            "decision_policy": self.decision_policy,
            "signature_required": self.signature_required,
            "four_eyes_required": self.four_eyes_required,
            "revoke_if_changed": self.revoke_if_changed,
            "deadline_seconds": self.deadline_seconds,
            "is_enabled": self.is_enabled,
        }


@dataclass(frozen=True)
class WorkflowProfileVersionDefinition:
    profile_code: str
    label: str
    control_class: ControlClass
    release_evidence_mode: str
    requires_editors: bool
    requires_reviewers: bool
    requires_approvers: bool
    allows_content_changes: bool
    transitions: tuple[WorkflowProfileTransitionDefinition, ...]

    @property
    def four_eyes_required(self) -> bool:
        return any(item.four_eyes_required for item in self.transitions if item.is_enabled)

    def semantic_payload(self) -> dict[str, object]:
        return {
            "profile_code": self.profile_code,
            "label": self.label,
            "control_class": self.control_class.value,
            "release_evidence_mode": self.release_evidence_mode,
            "requires_editors": self.requires_editors,
            "requires_reviewers": self.requires_reviewers,
            "requires_approvers": self.requires_approvers,
            "allows_content_changes": self.allows_content_changes,
            "transitions": [item.semantic_payload() for item in self.transitions],
        }

    def definition_hash(self) -> str:
        return _sha256_text(json.dumps(self.semantic_payload(), sort_keys=True, separators=(",", ":")))

    def to_runtime_profile(self) -> WorkflowProfile:
        """Build an engine-compatible WorkflowProfile (IN_PROGRESS start) from relational DRAFT."""
        enabled = tuple(item for item in self.transitions if item.is_enabled)
        relational_phases = (DocumentStatus.DRAFT,) + tuple(DocumentStatus(item.to_status) for item in enabled)
        # Deduplicate while preserving order, then adapt DRAFT -> IN_PROGRESS at this boundary only.
        deduped: list[DocumentStatus] = []
        for status in relational_phases:
            if not deduped or deduped[-1] != status:
                deduped.append(status)
        runtime_phases = tuple(runtime_status_from_relational(status) for status in deduped)
        signature_required = tuple(
            runtime_transition_key_from_relational(item.from_status, item.to_status)
            for item in enabled
            if item.signature_required
        )
        return WorkflowProfile(
            profile_id=self.profile_code,
            label=self.label,
            phases=runtime_phases,
            four_eyes_required=self.four_eyes_required,
            control_class=self.control_class,
            signature_required_transitions=signature_required,
            requires_editors=self.requires_editors,
            requires_reviewers=self.requires_reviewers,
            requires_approvers=self.requires_approvers,
            allows_content_changes=self.allows_content_changes,
            release_evidence_mode=self.release_evidence_mode,
        )


@dataclass(frozen=True)
class WorkflowProfileImportReportRow:
    source_path: str
    file_sha256: str
    profile_id: str
    canonical_profile_hash: str
    seed_compare_hash: str | None
    classification: str
    import_status: str
    block_reason: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "file_sha256": self.file_sha256,
            "profile_id": self.profile_id,
            "canonical_profile_hash": self.canonical_profile_hash,
            "seed_compare_hash": self.seed_compare_hash,
            "classification": self.classification,
            "import_status": self.import_status,
            "block_reason": self.block_reason,
        }


class WorkflowProfileRelationalStore:
    def __init__(
        self,
        repository,
        *,
        bundled_seed_path: Path,
        legacy_profiles_path: Path,
        bootstrap_provenance: DocumentsBootstrapProvenance | None = None,
        is_pre_j03_upgrade: bool | None = None,
    ) -> None:
        self._repository = repository
        self._bundled_seed_path = bundled_seed_path
        self._legacy_profiles_path = legacy_profiles_path
        if bootstrap_provenance is not None:
            self._bootstrap_provenance = bootstrap_provenance
        elif is_pre_j03_upgrade is not None:
            # Test-helper compatibility: map the legacy boolean onto provenance.
            self._bootstrap_provenance = (
                DocumentsBootstrapProvenance.PRE_J03_UPGRADE
                if is_pre_j03_upgrade
                else DocumentsBootstrapProvenance.FRESH_INSTALL
            )
        else:
            self._bootstrap_provenance = DocumentsBootstrapProvenance.FRESH_INSTALL
        self._is_pre_j03_upgrade = (
            self._bootstrap_provenance == DocumentsBootstrapProvenance.PRE_J03_UPGRADE
        )
        self.last_import_report: tuple[WorkflowProfileImportReportRow, ...] = ()

    def ensure_seeded(self, seed_reader) -> None:
        if self.has_profiles():
            self._consistency_check(seed_reader)
            return
        if self._bootstrap_provenance == DocumentsBootstrapProvenance.POST_J03_SCHEMA:
            raise ValidationError(
                "documents schema is already at J03 workflow-profile version but "
                "workflow_profile_definitions is empty; refusing silent re-seed"
            )
        source_path, source_kind = self._resolve_import_source()
        bundled_payload = seed_reader.read(self._bundled_seed_path)
        imported = seed_reader.read(source_path) if source_path != self._bundled_seed_path else bundled_payload
        self.import_seed(
            source_path=source_path,
            source_kind=source_kind,
            seed_payload=imported,
            bundled_payload=bundled_payload,
            legacy_migration=(source_kind == "legacy_profiles_file"),
        )

    def has_profiles(self) -> bool:
        with self._repository._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM workflow_profile_definitions").fetchone()
        return bool(row and int(row[0]) > 0)

    def get(self, profile_code: str) -> WorkflowProfile:
        return self.get_active_definition(profile_code).to_runtime_profile()

    def get_active_definition(self, profile_code: str) -> WorkflowProfileVersionDefinition:
        now = _utcnow_iso()
        with self._repository._connect() as conn:
            row = conn.execute(
                """
                SELECT d.profile_code, d.label, d.control_class,
                       v.profile_version_id, v.version_no, v.release_evidence_mode,
                       v.requires_editors, v.requires_reviewers, v.requires_approvers,
                       v.allows_content_changes
                FROM workflow_profile_definitions d
                JOIN workflow_profile_versions v
                  ON v.profile_code = d.profile_code
                WHERE d.profile_code = ?
                  AND d.is_active = 1
                  AND v.effective_from <= ?
                ORDER BY v.version_no DESC
                LIMIT 1
                """,
                (profile_code, now),
            ).fetchone()
            if row is None:
                raise ValidationError(f"unknown active workflow profile: {profile_code}")
            transitions = self._load_transitions(conn, str(row["profile_version_id"]))
        return WorkflowProfileVersionDefinition(
            profile_code=str(row["profile_code"]),
            label=str(row["label"]),
            control_class=ControlClass(str(row["control_class"])),
            release_evidence_mode=str(row["release_evidence_mode"]),
            requires_editors=bool(row["requires_editors"]),
            requires_reviewers=bool(row["requires_reviewers"]),
            requires_approvers=bool(row["requires_approvers"]),
            allows_content_changes=bool(row["allows_content_changes"]),
            transitions=transitions,
        )

    def resolve_default_profile_code(self, doc_type: DocumentType) -> tuple[str, bool]:
        with self._repository._connect() as conn:
            row = conn.execute(
                """
                SELECT default_profile_code, allows_profile_override
                FROM document_type_definitions
                WHERE document_type = ?
                """,
                (doc_type.value,),
            ).fetchone()
        if row is None:
            raise ValidationError(f"document type binding missing for {doc_type.value}")
        return str(row["default_profile_code"]), bool(row["allows_profile_override"])

    def list_definitions(self, *, include_inactive: bool = True) -> list[dict[str, object]]:
        sql = """
            SELECT profile_code, label, control_class, is_active, active_version
            FROM workflow_profile_definitions
        """
        if not include_inactive:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY profile_code ASC"
        with self._repository._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            {
                "profile_code": str(row["profile_code"]),
                "label": str(row["label"]),
                "control_class": str(row["control_class"]),
                "is_active": bool(row["is_active"]),
                "active_version": int(row["active_version"]) if row["active_version"] is not None else None,
            }
            for row in rows
        ]

    def list_versions(self, profile_code: str) -> list[dict[str, object]]:
        with self._repository._connect() as conn:
            versions = conn.execute(
                """
                SELECT profile_version_id, profile_code, version_no, source_kind, change_reason,
                       definition_hash, effective_from, release_evidence_mode,
                       requires_editors, requires_reviewers, requires_approvers,
                       allows_content_changes, created_at, created_by
                FROM workflow_profile_versions
                WHERE profile_code = ?
                ORDER BY version_no ASC
                """,
                (profile_code,),
            ).fetchall()
            result: list[dict[str, object]] = []
            for row in versions:
                transitions = self._load_transitions(conn, str(row["profile_version_id"]))
                result.append(
                    {
                        "profile_version_id": str(row["profile_version_id"]),
                        "profile_code": str(row["profile_code"]),
                        "version": int(row["version_no"]),
                        "source_kind": str(row["source_kind"]),
                        "change_reason": str(row["change_reason"]),
                        "definition_hash": str(row["definition_hash"]),
                        "effective_from": str(row["effective_from"]),
                        "release_evidence_mode": str(row["release_evidence_mode"]),
                        "four_eyes_required": any(item.four_eyes_required for item in transitions),
                        "requires_editors": bool(row["requires_editors"]),
                        "requires_reviewers": bool(row["requires_reviewers"]),
                        "requires_approvers": bool(row["requires_approvers"]),
                        "allows_content_changes": bool(row["allows_content_changes"]),
                        "created_at": str(row["created_at"]),
                        "created_by": str(row["created_by"]),
                        "transitions": [item.semantic_payload() for item in transitions],
                    }
                )
        return result

    def list_profile_ids_for_control_class(self, control_class: ControlClass) -> list[str]:
        with self._repository._connect() as conn:
            rows = conn.execute(
                """
                SELECT profile_code
                FROM workflow_profile_definitions
                WHERE control_class = ? AND is_active = 1
                ORDER BY profile_code ASC
                """,
                (control_class.value,),
            ).fetchall()
        return [str(row["profile_code"]) for row in rows]

    def create_definition(
        self,
        payload: WorkflowProfileVersionDefinition,
        *,
        source_kind: str,
        change_reason: str,
        actor_user_id: str,
    ) -> dict[str, object]:
        self._validate_definition(payload)
        if not actor_user_id.strip():
            raise ValidationError("actor_user_id is required")
        now = _utcnow_iso()
        with self._repository.write_transaction():
            with self._repository._connect() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM workflow_profile_definitions WHERE profile_code = ?",
                    (payload.profile_code,),
                ).fetchone()
                if exists is not None:
                    raise ValidationError(f"workflow profile definition already exists: {payload.profile_code}")
                conn.execute(
                    """
                    INSERT INTO workflow_profile_definitions (
                        profile_code, label, control_class, is_active, active_version,
                        created_at, created_by, updated_at, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.profile_code,
                        payload.label,
                        payload.control_class.value,
                        1,
                        1,
                        now,
                        actor_user_id,
                        now,
                        actor_user_id,
                    ),
                )
                self._insert_version(
                    conn,
                    payload,
                    version_no=1,
                    source_kind=source_kind,
                    change_reason=change_reason,
                    actor_user_id=actor_user_id,
                    effective_from=now,
                )
        return {"profile_code": payload.profile_code, "version": 1, "is_active": True}

    def create_version(
        self,
        payload: WorkflowProfileVersionDefinition,
        *,
        source_kind: str,
        change_reason: str,
        actor_user_id: str,
    ) -> dict[str, object]:
        self._validate_definition(payload)
        if not actor_user_id.strip():
            raise ValidationError("actor_user_id is required")
        now = _utcnow_iso()
        with self._repository.write_transaction():
            with self._repository._connect() as conn:
                current = conn.execute(
                    """
                    SELECT d.label, d.control_class, COALESCE(MAX(v.version_no), 0) AS latest_version
                    FROM workflow_profile_definitions d
                    LEFT JOIN workflow_profile_versions v ON v.profile_code = d.profile_code
                    WHERE d.profile_code = ?
                    GROUP BY d.label, d.control_class
                    """,
                    (payload.profile_code,),
                ).fetchone()
                if current is None or int(current["latest_version"]) <= 0:
                    raise ValidationError(f"workflow profile definition not found: {payload.profile_code}")
                if str(current["label"]) != payload.label:
                    raise ValidationError("workflow profile label is immutable in J03")
                if str(current["control_class"]) != payload.control_class.value:
                    raise ValidationError("workflow profile control_class is immutable in J03")
                next_version = int(current["latest_version"]) + 1
                self._insert_version(
                    conn,
                    payload,
                    version_no=next_version,
                    source_kind=source_kind,
                    change_reason=change_reason,
                    actor_user_id=actor_user_id,
                    effective_from=now,
                )
                conn.execute(
                    """
                    UPDATE workflow_profile_definitions
                    SET active_version = ?, updated_at = ?, updated_by = ?
                    WHERE profile_code = ?
                    """,
                    (next_version, now, actor_user_id, payload.profile_code),
                )
        return {"profile_code": payload.profile_code, "version": next_version, "is_active": True}

    def set_active(self, profile_code: str, *, is_active: bool, actor_user_id: str) -> dict[str, object]:
        if not actor_user_id.strip():
            raise ValidationError("actor_user_id is required")
        with self._repository.write_transaction():
            with self._repository._connect() as conn:
                row = conn.execute(
                    "SELECT profile_code FROM workflow_profile_definitions WHERE profile_code = ?",
                    (profile_code,),
                ).fetchone()
                if row is None:
                    raise ValidationError(f"workflow profile definition not found: {profile_code}")
                conn.execute(
                    """
                    UPDATE workflow_profile_definitions
                    SET is_active = ?, updated_at = ?, updated_by = ?
                    WHERE profile_code = ?
                    """,
                    (1 if is_active else 0, _utcnow_iso(), actor_user_id, profile_code),
                )
        return {"profile_code": profile_code, "is_active": is_active}

    def bind_default_profile(
        self,
        doc_type: DocumentType,
        profile_code: str,
        *,
        actor_user_id: str,
        allows_profile_override: bool | None = None,
    ) -> dict[str, object]:
        if not actor_user_id.strip():
            raise ValidationError("actor_user_id is required")
        with self._repository.write_transaction():
            with self._repository._connect() as conn:
                profile = conn.execute(
                    "SELECT control_class FROM workflow_profile_definitions WHERE profile_code = ? AND is_active = 1",
                    (profile_code,),
                ).fetchone()
                if profile is None:
                    raise ValidationError(f"active workflow profile definition not found: {profile_code}")
                control_class = str(profile["control_class"])
                existing = conn.execute(
                    "SELECT allows_profile_override FROM document_type_definitions WHERE document_type = ?",
                    (doc_type.value,),
                ).fetchone()
                override = (
                    bool(allows_profile_override)
                    if allows_profile_override is not None
                    else (bool(existing["allows_profile_override"]) if existing is not None else False)
                )
                now = _utcnow_iso()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO document_type_definitions (
                            document_type, control_class, default_profile_code, allows_profile_override,
                            binding_source, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            doc_type.value,
                            control_class,
                            profile_code,
                            1 if override else 0,
                            f"admin:{actor_user_id}",
                            now,
                            now,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE document_type_definitions
                        SET default_profile_code = ?, control_class = ?, allows_profile_override = ?,
                            binding_source = ?, updated_at = ?
                        WHERE document_type = ?
                        """,
                        (
                            profile_code,
                            control_class,
                            1 if override else 0,
                            f"admin:{actor_user_id}",
                            now,
                            doc_type.value,
                        ),
                    )
        return {
            "document_type": doc_type.value,
            "default_profile_code": profile_code,
            "allows_profile_override": override,
        }

    def import_seed(
        self,
        *,
        source_path: Path,
        source_kind: str,
        seed_payload,
        bundled_payload,
        legacy_migration: bool,
    ) -> None:
        raw_sha256 = str(seed_payload["raw_sha256"])
        bundled_by_code = {item.profile_code: item for item in bundled_payload["profiles"]}
        source_profiles = list(seed_payload["profiles"])
        report_rows: list[WorkflowProfileImportReportRow] = []
        to_import: list[tuple[WorkflowProfileVersionDefinition, str]] = []

        for item in source_profiles:
            self._validate_definition(item)
            seed_item = bundled_by_code.get(item.profile_code)
            seed_hash = seed_item.definition_hash() if seed_item is not None else None
            canonical = item.definition_hash()
            if seed_hash is not None and seed_hash == canonical:
                classification = "SEED"
            else:
                classification = "MIGRATED"
            to_import.append((item, classification))
            report_rows.append(
                WorkflowProfileImportReportRow(
                    source_path=str(source_path),
                    file_sha256=raw_sha256,
                    profile_id=item.profile_code,
                    canonical_profile_hash=canonical,
                    seed_compare_hash=seed_hash,
                    classification=classification,
                    import_status="pending",
                )
            )

        if legacy_migration:
            # Package-only profiles are intentionally not auto-added on legacy migration.
            for code, seed_item in bundled_by_code.items():
                if code in {item.profile_code for item in source_profiles}:
                    continue
                report_rows.append(
                    WorkflowProfileImportReportRow(
                        source_path=str(source_path),
                        file_sha256=raw_sha256,
                        profile_id=code,
                        canonical_profile_hash=seed_item.definition_hash(),
                        seed_compare_hash=seed_item.definition_hash(),
                        classification="SEED",
                        import_status="skipped_package_only",
                        block_reason="package-only profile not auto-added during legacy migration",
                    )
                )

        classifications = {row.classification for row in report_rows if row.import_status == "pending"}
        if classifications == {"SEED"}:
            batch_classification = "SEED"
        elif classifications == {"MIGRATED"}:
            batch_classification = "MIGRATED"
        else:
            batch_classification = "MIXED"

        try:
            with self._repository.write_transaction():
                with self._repository._connect() as conn:
                    for item, classification in to_import:
                        now = _utcnow_iso()
                        conn.execute(
                            """
                            INSERT INTO workflow_profile_definitions (
                                profile_code, label, control_class, is_active, active_version,
                                created_at, created_by, updated_at, updated_by
                            ) VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?)
                            """,
                            (
                                item.profile_code,
                                item.label,
                                item.control_class.value,
                                now,
                                "seed-import",
                                now,
                                "seed-import",
                            ),
                        )
                        self._insert_version(
                            conn,
                            item,
                            version_no=1,
                            source_kind=classification,
                            change_reason=f"initial {source_kind}",
                            actor_user_id="seed-import",
                            effective_from=now,
                        )
                    self._ensure_document_type_bindings(conn, available_codes={item.profile_code for item, _ in to_import})
                    finalized = []
                    for row in report_rows:
                        if row.import_status == "pending":
                            finalized.append(
                                WorkflowProfileImportReportRow(
                                    source_path=row.source_path,
                                    file_sha256=row.file_sha256,
                                    profile_id=row.profile_id,
                                    canonical_profile_hash=row.canonical_profile_hash,
                                    seed_compare_hash=row.seed_compare_hash,
                                    classification=row.classification,
                                    import_status="imported",
                                )
                            )
                        else:
                            finalized.append(row)
                    conn.execute(
                        """
                        INSERT INTO workflow_profile_imports (
                            import_id, source_path, source_kind, raw_sha256, semantic_sha256,
                            import_classification, imported_at, report_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            uuid4().hex,
                            str(source_path),
                            source_kind,
                            raw_sha256,
                            seed_payload["semantic_sha256"],
                            batch_classification,
                            _utcnow_iso(),
                            json.dumps([row.as_dict() for row in finalized], sort_keys=True),
                        ),
                    )
                    self.last_import_report = tuple(finalized)
        except Exception:
            blocked = [
                WorkflowProfileImportReportRow(
                    source_path=row.source_path,
                    file_sha256=row.file_sha256,
                    profile_id=row.profile_id,
                    canonical_profile_hash=row.canonical_profile_hash,
                    seed_compare_hash=row.seed_compare_hash,
                    classification=row.classification,
                    import_status="blocked",
                    block_reason="import aborted; no partial write",
                )
                for row in report_rows
            ]
            self.last_import_report = tuple(blocked)
            raise

    def _consistency_check(self, seed_reader) -> None:
        with self._repository._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM workflow_profile_definitions").fetchone()
            if not count or int(count[0]) <= 0:
                raise ValidationError("workflow profile store consistency check failed: empty definitions")
            missing_types = []
            for doc_type in DocumentType:
                row = conn.execute(
                    "SELECT 1 FROM document_type_definitions WHERE document_type = ?",
                    (doc_type.value,),
                ).fetchone()
                if row is None:
                    missing_types.append(doc_type.value)
            if missing_types:
                raise ValidationError(
                    "workflow profile store consistency check failed: missing document type bindings: "
                    + ", ".join(missing_types)
                )

    def _ensure_document_type_bindings(self, conn: sqlite3.Connection, *, available_codes: set[str]) -> None:
        # Evidenced sources only (module settings defaults + import_existing_pdf EXT path).
        bindings = {
            DocumentType.VA.value: ("long_release", False, "module.settings.doc_type_profile_rules"),
            DocumentType.AA.value: ("long_release", False, "module.settings.doc_type_profile_rules"),
            DocumentType.FB.value: ("long_release", False, "module.settings.doc_type_profile_rules"),
            DocumentType.LS.value: ("long_release", False, "module.settings.doc_type_profile_rules"),
            DocumentType.EXT.value: ("external_control", False, "service.import_existing_pdf hardcoded path"),
            DocumentType.OTHER.value: ("long_release", True, "module.settings.doc_type_profile_rules"),
        }
        control = {
            DocumentType.VA.value: ControlClass.CONTROLLED.value,
            DocumentType.AA.value: ControlClass.CONTROLLED.value,
            DocumentType.FB.value: ControlClass.CONTROLLED.value,
            DocumentType.LS.value: ControlClass.CONTROLLED.value,
            DocumentType.EXT.value: ControlClass.EXTERNAL.value,
            DocumentType.OTHER.value: ControlClass.CONTROLLED.value,
        }
        for doc_type, (profile_code, override, source) in bindings.items():
            if profile_code not in available_codes:
                raise ValidationError(
                    f"document type binding for {doc_type} requires profile '{profile_code}' "
                    f"which is not present in the import source ({source})"
                )
            now = _utcnow_iso()
            conn.execute(
                """
                INSERT INTO document_type_definitions (
                    document_type, control_class, default_profile_code, allows_profile_override,
                    binding_source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_type) DO NOTHING
                """,
                (
                    doc_type,
                    control[doc_type],
                    profile_code,
                    1 if override else 0,
                    source,
                    now,
                    now,
                ),
            )

    def _insert_version(
        self,
        conn: sqlite3.Connection,
        payload: WorkflowProfileVersionDefinition,
        *,
        version_no: int,
        source_kind: str,
        change_reason: str,
        actor_user_id: str,
        effective_from: str,
    ) -> str:
        profile_version_id = uuid4().hex
        conn.execute(
            """
            INSERT INTO workflow_profile_versions (
                profile_version_id, profile_code, version_no, source_kind, change_reason,
                definition_hash, effective_from, release_evidence_mode, four_eyes_required,
                requires_editors, requires_reviewers, requires_approvers, allows_content_changes,
                created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_version_id,
                payload.profile_code,
                version_no,
                source_kind,
                change_reason,
                payload.definition_hash(),
                effective_from,
                payload.release_evidence_mode,
                1 if payload.four_eyes_required else 0,
                1 if payload.requires_editors else 0,
                1 if payload.requires_reviewers else 0,
                1 if payload.requires_approvers else 0,
                1 if payload.allows_content_changes else 0,
                _utcnow_iso(),
                actor_user_id,
            ),
        )
        for item in payload.transitions:
            conn.execute(
                """
                INSERT INTO workflow_profile_transitions (
                    profile_transition_id, profile_version_id, transition_no, from_status, to_status,
                    required_role, decision_policy, signature_required, four_eyes_required,
                    revoke_if_changed, deadline_seconds, is_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid4().hex,
                    profile_version_id,
                    item.transition_no,
                    item.from_status,
                    item.to_status,
                    item.required_role,
                    item.decision_policy,
                    1 if item.signature_required else 0,
                    1 if item.four_eyes_required else 0,
                    1 if item.revoke_if_changed else 0,
                    item.deadline_seconds,
                    1 if item.is_enabled else 0,
                ),
            )
        return profile_version_id

    def _load_transitions(self, conn: sqlite3.Connection, profile_version_id: str) -> tuple[WorkflowProfileTransitionDefinition, ...]:
        rows = conn.execute(
            """
            SELECT transition_no, from_status, to_status, required_role, decision_policy,
                   signature_required, four_eyes_required, revoke_if_changed, deadline_seconds, is_enabled
            FROM workflow_profile_transitions
            WHERE profile_version_id = ?
            ORDER BY transition_no ASC
            """,
            (profile_version_id,),
        ).fetchall()
        return tuple(
            WorkflowProfileTransitionDefinition(
                transition_no=int(item["transition_no"]),
                from_status=str(item["from_status"]),
                to_status=str(item["to_status"]),
                required_role=str(item["required_role"]),
                decision_policy=str(item["decision_policy"]),
                signature_required=bool(item["signature_required"]),
                four_eyes_required=bool(item["four_eyes_required"]),
                revoke_if_changed=bool(item["revoke_if_changed"]),
                deadline_seconds=int(item["deadline_seconds"]) if item["deadline_seconds"] is not None else None,
                is_enabled=bool(item["is_enabled"]),
            )
            for item in rows
        )

    def _resolve_import_source(self) -> tuple[Path, str]:
        # Fresh install: always bundled seed. Upgrade from pre-J03 DB: previously resolved runtime profiles_file.
        if self._is_pre_j03_upgrade:
            if not self._legacy_profiles_path.exists():
                raise ValidationError(
                    f"legacy workflow profiles file not found for pre-J03 upgrade: {self._legacy_profiles_path}"
                )
            if self._legacy_profiles_path.resolve() == self._bundled_seed_path.resolve():
                # Same path bytes can still be a legacy runtime source; treat as legacy file kind.
                return self._legacy_profiles_path, "legacy_profiles_file"
            return self._legacy_profiles_path, "legacy_profiles_file"
        return self._bundled_seed_path, "bundled_seed"

    def _validate_definition(self, payload: WorkflowProfileVersionDefinition) -> None:
        if not payload.profile_code.strip():
            raise ValidationError("profile_code is required")
        if not payload.label.strip():
            raise ValidationError("label is required")
        if not payload.transitions:
            raise ValidationError("workflow profile requires at least one transition")
        enabled = [item for item in payload.transitions if item.is_enabled]
        if not enabled:
            raise ValidationError("workflow profile requires at least one enabled transition")
        if enabled[0].from_status != "DRAFT":
            raise ValidationError("workflow profile must start with DRAFT")
        if enabled[0].to_status == "DRAFT":
            raise ValidationError("workflow profile first transition must leave DRAFT")
        if enabled[-1].to_status != "APPROVED":
            raise ValidationError("workflow profile must end with APPROVED")
        expected_nos = list(range(1, len(payload.transitions) + 1))
        if [item.transition_no for item in payload.transitions] != expected_nos:
            raise ValidationError("workflow profile transitions must use contiguous transition_no starting at 1")
        seen_from: set[str] = set()
        seen_edges: set[tuple[str, str]] = set()
        for index, item in enumerate(enabled):
            if item.from_status not in _ALLOWED_PROFILE_STATUSES or item.to_status not in _ALLOWED_PROFILE_STATUSES:
                raise ValidationError("workflow profile contains unsupported status")
            if item.from_status == "IN_PROGRESS" or item.to_status == "IN_PROGRESS":
                raise ValidationError("IN_PROGRESS is legacy-only and must be normalized to DRAFT before storage")
            if item.decision_policy not in _ALLOWED_POLICIES:
                raise ValidationError("workflow profile contains unsupported decision_policy")
            if item.decision_policy not in _ENGINE_POLICIES:
                raise ValidationError("workflow profile contains unsupported decision_policy for current engine")
            if item.required_role not in _ALLOWED_ROLES:
                raise ValidationError("workflow profile contains unsupported required_role")
            if item.deadline_seconds is not None:
                raise ValidationError("deadline_seconds is not evaluated by the current engine")
            if item.revoke_if_changed:
                raise ValidationError("revoke_if_changed is not evaluated by the current engine")
            expected_role = _expected_role(item.from_status, item.to_status)
            if item.required_role != expected_role:
                raise ValidationError(
                    f"required_role '{item.required_role}' is not executable for {item.from_status}->{item.to_status}"
                )
            if item.from_status in seen_from:
                raise ValidationError("workflow profile must be linear without branching")
            edge = (item.from_status, item.to_status)
            if edge in seen_edges:
                raise ValidationError("workflow profile contains duplicate transition edge")
            seen_from.add(item.from_status)
            seen_edges.add(edge)
            if index > 0 and enabled[index - 1].to_status != item.from_status:
                raise ValidationError("workflow profile transitions must form a contiguous chain")
        runtime_profile = payload.to_runtime_profile()
        if runtime_profile.phases[0] != DocumentStatus.IN_PROGRESS:
            raise ValidationError("runtime workflow profile must start with IN_PROGRESS")
        if runtime_profile.phases[-1] != DocumentStatus.APPROVED:
            raise ValidationError("runtime workflow profile must end with APPROVED")


def _expected_role(from_status: str, to_status: str) -> str:
    if from_status == "DRAFT":
        return "EDITOR"
    if from_status == "IN_REVIEW":
        return "REVIEWER"
    if from_status == "IN_APPROVAL":
        return "APPROVER"
    if to_status == "APPROVED":
        return "APPROVER"
    return "NONE"
