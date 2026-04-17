from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


from enum import Enum
from typing import Any

from .errors import DocumentWorkflowError  # noqa: F401 - public re-export for adapters


class SystemRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    QMB = "QMB"


class DocumentStatus(str, Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    IN_APPROVAL = "IN_APPROVAL"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class DocumentType(str, Enum):
    VA = "VA"
    AA = "AA"
    FB = "FB"
    LS = "LS"
    EXT = "EXT"
    OTHER = "OTHER"


class ControlClass(str, Enum):
    CONTROLLED = "CONTROLLED"
    CONTROLLED_SHORT = "CONTROLLED_SHORT"
    EXTERNAL = "EXTERNAL"
    RECORD = "RECORD"


def control_class_for(doc_type: DocumentType) -> ControlClass:
    if doc_type == DocumentType.EXT:
        return ControlClass.EXTERNAL
    return ControlClass.CONTROLLED


class ArtifactType(str, Enum):
    SOURCE_DOCX = "SOURCE_DOCX"
    SOURCE_PDF = "SOURCE_PDF"
    REVIEW_PDF = "REVIEW_PDF"
    SIGNED_PDF = "SIGNED_PDF"
    RELEASED_PDF = "RELEASED_PDF"
    SUPERSEDED_RELEASED_PDF = "SUPERSEDED_RELEASED_PDF"
    ATTACHMENT = "ATTACHMENT"
    COMMENT_EXPORT = "COMMENT_EXPORT"


class ArtifactSourceType(str, Enum):
    IMPORT_PDF = "IMPORT_PDF"
    IMPORT_DOCX = "IMPORT_DOCX"
    TEMPLATE_DOTX = "TEMPLATE_DOTX"
    TEMPLATE_DOCT = "TEMPLATE_DOCT"
    GENERATED = "GENERATED"


class ValidityExtensionOutcome(str, Enum):
    UNCHANGED = "unchanged"
    EDITORIAL = "editorial"
    NEW_VERSION_REQUIRED = "new_version_required"


@dataclass(frozen=True)
class RejectionReason:
    template_id: str | None = None
    template_text: str | None = None
    free_text: str | None = None

    def is_valid(self) -> bool:
        template = (self.template_text or "").strip()
        free = (self.free_text or "").strip()
        return bool(template or free)


@dataclass(frozen=True)
class WorkflowProfile:
    profile_id: str
    label: str
    phases: tuple[DocumentStatus, ...]
    four_eyes_required: bool
    control_class: ControlClass = ControlClass.CONTROLLED
    signature_required_transitions: tuple[str, ...] = ()
    requires_editors: bool = True
    requires_reviewers: bool = True
    requires_approvers: bool = True
    allows_content_changes: bool = True
    release_evidence_mode: str = "WORKFLOW"

    @staticmethod
    def long_release_path() -> "WorkflowProfile":
        return WorkflowProfile(
            profile_id="long_release",
            label="Long release path",
            control_class=ControlClass.CONTROLLED,
            phases=(
                DocumentStatus.IN_PROGRESS,
                DocumentStatus.IN_REVIEW,
                DocumentStatus.IN_APPROVAL,
                DocumentStatus.APPROVED,
            ),
            four_eyes_required=True,
            signature_required_transitions=("IN_PROGRESS->IN_REVIEW", "IN_REVIEW->IN_APPROVAL", "IN_APPROVAL->APPROVED"),
            requires_editors=True,
            requires_reviewers=True,
            requires_approvers=True,
            allows_content_changes=True,
            release_evidence_mode="WORKFLOW",
        )


@dataclass(frozen=True)
class DocumentHeader:
    # document_id is ALWAYS a caller-provided fachliche Kennung (e.g. "VA-2024-001").
    # The system NEVER auto-generates UUIDs for document_id.
    # Stability invariant: document_id is immutable across all versions of the same document.
    document_id: str
    doc_type: DocumentType
    control_class: ControlClass
    workflow_profile_id: str
    register_binding: bool = True
    department: str | None = None
    site: str | None = None
    regulatory_scope: str | None = None
    distribution_roles: tuple[str, ...] = ()
    distribution_sites: tuple[str, ...] = ()
    distribution_departments: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class WorkflowAssignments:
    editors: frozenset[str] = field(default_factory=frozenset)
    reviewers: frozenset[str] = field(default_factory=frozenset)
    approvers: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class DocumentVersionState:
    document_id: str
    version: int
    title: str = ""
    description: str | None = None
    doc_type: DocumentType = DocumentType.OTHER
    control_class: ControlClass = ControlClass.CONTROLLED
    workflow_profile_id: str = "long_release"
    owner_user_id: str | None = None
    status: DocumentStatus = DocumentStatus.PLANNED
    workflow_active: bool = False
    workflow_profile: WorkflowProfile | None = None
    assignments: WorkflowAssignments = field(default_factory=WorkflowAssignments)
    reviewed_by: frozenset[str] = field(default_factory=frozenset)
    approved_by: frozenset[str] = field(default_factory=frozenset)
    edit_signature_done: bool = False
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    next_review_at: datetime | None = None
    review_completed_at: datetime | None = None
    review_completed_by: str | None = None
    approval_completed_at: datetime | None = None
    approval_completed_by: str | None = None
    released_at: datetime | None = None
    archived_at: datetime | None = None
    archived_by: str | None = None
    superseded_by_version: int | None = None
    extension_count: int = 0
    last_extended_at: datetime | None = None
    last_extended_by: str | None = None
    last_extension_reason: str | None = None
    last_extension_review_outcome: str | None = None
    custom_fields: dict[str, Any] = field(default_factory=dict)
    last_event_id: str | None = None
    last_event_at: datetime | None = None
    last_actor_user_id: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class DocumentArtifact:
    artifact_id: str
    document_id: str
    version: int
    artifact_type: ArtifactType
    source_type: ArtifactSourceType
    storage_key: str
    original_filename: str
    mime_type: str
    sha256: str
    size_bytes: int
    is_current: bool
    metadata: dict[str, str]
    created_at: datetime


@dataclass(frozen=True)
class DocumentTaskItem:
    document_id: str
    version: int
    title: str
    status: DocumentStatus
    owner_user_id: str | None
    workflow_active: bool
    last_actor_user_id: str | None


@dataclass(frozen=True)
class ReviewActionItem:
    document_id: str
    version: int
    title: str
    status: DocumentStatus
    action_required: str
    owner_user_id: str | None


@dataclass(frozen=True)
class RecentDocumentItem:
    document_id: str
    version: int
    title: str
    status: DocumentStatus
    owner_user_id: str | None
    last_event_at: datetime | None


@dataclass(frozen=True)
class ReleasedDocumentItem:
    document_id: str
    version: int
    title: str
    valid_until: datetime | None
    released_at: datetime | None
    owner_user_id: str | None


@dataclass(frozen=True)
class DocumentReadSession:
    session_id: str
    user_id: str
    document_id: str
    version: int
    opened_at: datetime


@dataclass(frozen=True)
class DocumentReadReceipt:
    receipt_id: str
    user_id: str
    document_id: str
    version: int
    confirmed_at: datetime
    source: str


@dataclass(frozen=True)
class ChangeRequest:
    change_id: str
    reason: str
    impact_refs: tuple[str, ...] = ()
    created_by: str | None = None
    created_at: datetime = field(default_factory=utcnow)

