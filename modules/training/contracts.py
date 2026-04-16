"""Training module contracts – clean-slate redesign per §12.2."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CommentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    INACTIVE = "INACTIVE"


class AssignmentSource(str, Enum):
    SCOPE = "SCOPE"
    TAG = "TAG"
    MANUAL = "MANUAL"
    EXEMPTED = "EXEMPTED"
    NOT_RELEVANT = "NOT_RELEVANT"


class TrainingAssignmentStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    READ_CONFIRMED = "READ_CONFIRMED"
    QUIZ_PASSED = "QUIZ_PASSED"
    QUIZ_FAILED = "QUIZ_FAILED"
    SUPERSEDED = "SUPERSEDED"


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QuizAnswer:
    answer_id: str
    text: str


@dataclass(frozen=True)
class QuizQuestion:
    question_id: str
    text: str
    answers: tuple[QuizAnswer, ...]
    correct_answer_id: str


@dataclass(frozen=True)
class QuizSession:
    session_id: str
    user_id: str
    document_id: str
    version: int
    selected_question_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class QuizResult:
    session_id: str
    user_id: str
    document_id: str
    version: int
    score: int
    total: int
    passed: bool
    completed_at: datetime


@dataclass(frozen=True)
class QuizImportResult:
    import_id: str
    document_id: str
    document_version: int
    question_count: int
    auto_bound: bool
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class PendingQuizMapping:
    import_id: str
    document_id: str
    document_version: int
    created_at: datetime


@dataclass(frozen=True)
class QuizBinding:
    binding_id: str
    document_id: str
    version: int
    import_id: str
    active: bool
    created_at: datetime
    replaced_at: datetime | None = None
    replaced_by: str | None = None


@dataclass(frozen=True)
class QuizReplacementCheckResult:
    conflict_id: str | None
    existing_binding: QuizBinding | None
    has_conflict: bool


@dataclass(frozen=True)
class QuizBindingReplacementResult:
    old_binding_id: str
    new_binding_id: str
    replaced_by: str
    replaced_at: datetime


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentTagSet:
    document_id: str
    tags: frozenset[str]


@dataclass(frozen=True)
class UserTagSet:
    user_id: str
    tags: frozenset[str]


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ManualAssignment:
    assignment_id: str
    user_id: str
    document_id: str
    reason: str
    granted_by: str
    granted_at: datetime = field(default_factory=utcnow)
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class TrainingExemption:
    exemption_id: str
    user_id: str
    document_id: str
    version: int
    reason: str
    granted_by: str
    granted_at: datetime = field(default_factory=utcnow)
    valid_until: datetime | None = None
    revoked_at: datetime | None = None


# ---------------------------------------------------------------------------
# Snapshots / Inbox
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrainingAssignmentSnapshot:
    snapshot_id: str
    user_id: str
    document_id: str
    version: int
    source: AssignmentSource
    exempted: bool
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class TrainingProgress:
    user_id: str
    document_id: str
    version: int
    read_confirmed_at: datetime | None = None
    quiz_passed_at: datetime | None = None
    last_score: int | None = None
    quiz_attempts_count: int = 0


@dataclass(frozen=True)
class TrainingInboxItem:
    document_id: str
    version: int
    title: str
    status: str
    owner_user_id: str | None
    released_at: datetime | None
    read_confirmed: bool
    quiz_available: bool
    quiz_passed: bool
    source: AssignmentSource


@dataclass(frozen=True)
class TrainingDocumentRef:
    document_id: str
    version: int
    title: str
    owner_user_id: str | None
    released_at: datetime | None = None
    department: str | None = None
    site: str | None = None
    regulatory_scope: str | None = None


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrainingCommentRecord:
    comment_id: str
    document_id: str
    version: int
    document_title_snapshot: str
    user_id: str
    username_snapshot: str
    comment_text: str
    status: CommentStatus
    created_at: datetime
    updated_at: datetime
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    inactive_by: str | None = None
    inactive_at: datetime | None = None
    inactive_note: str | None = None


@dataclass(frozen=True)
class TrainingCommentListItem:
    comment_id: str
    document_id: str
    version: int
    document_title_snapshot: str
    user_id: str
    username_snapshot: str
    comment_text: str
    status: CommentStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# Reporting / Export
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrainingStatistics:
    total_users: int
    total_assignments: int
    completed: int
    open: int
    failed: int


@dataclass(frozen=True)
class TrainingAuditLogItem:
    log_id: str
    action: str
    actor_user_id: str
    timestamp: datetime
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TrainingMatrixExportResult:
    export_id: str
    row_count: int
    exported_at: datetime
    rows: list[dict[str, object]] = field(default_factory=list)
