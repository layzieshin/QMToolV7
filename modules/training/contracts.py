from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
def utcnow() -> datetime:
    return datetime.now(timezone.utc)




class TrainingAssignmentStatus(str, Enum):
    ASSIGNED = "ASSIGNED"
    READ_CONFIRMED = "READ_CONFIRMED"
    QUIZ_PASSED = "QUIZ_PASSED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class TrainingCategory:
    category_id: str
    name: str
    description: str | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class TrainingAssignment:
    assignment_id: str
    user_id: str
    document_id: str
    version: int
    category_id: str
    status: TrainingAssignmentStatus
    active: bool
    read_confirmed_at: datetime | None = None
    quiz_passed_at: datetime | None = None
    last_score: int | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class TrainingComment:
    comment_id: str
    user_id: str
    document_id: str
    version: int
    comment_text: str
    created_at: datetime


@dataclass(frozen=True)
class QuizQuestion:
    question_id: str
    question_text: str
    options: tuple[str, ...]
    correct_index: int


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
class OpenTrainingAssignmentItem:
    assignment_id: str
    user_id: str
    document_id: str
    version: int
    status: TrainingAssignmentStatus
    active: bool
    read_confirmed_at: datetime | None
    quiz_passed_at: datetime | None
    last_score: int | None


@dataclass(frozen=True)
class TrainingOverviewItem:
    document_id: str
    version: int
    read_confirmed: bool
    quiz_available: bool
    quiz_passed: bool
    last_action_at: datetime | None


@dataclass(frozen=True)
class QuizCapableDocumentItem:
    document_id: str
    version: int
    title: str
    owner_user_id: str | None
