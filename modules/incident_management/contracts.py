"""Public contracts for incident_management module."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class IncidentError(Exception):
    """Base error for incident_management."""


class ValidationError(IncidentError):
    """Invalid input or state transition."""


class AuthorizationError(IncidentError):
    """Role or permission denied."""


class NotFoundError(IncidentError):
    """Entity not found."""


class IncidentStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    QMB_REVIEW = "QMB_REVIEW"
    INQUIRY_OPEN = "INQUIRY_OPEN"
    INQUIRY_ANSWERED = "INQUIRY_ANSWERED"
    ASSESSED = "ASSESSED"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"
    ROOT_CAUSE_REQUIRED = "ROOT_CAUSE_REQUIRED"
    ROOT_CAUSE_IN_PROGRESS = "ROOT_CAUSE_IN_PROGRESS"
    CAPA_REQUIRED = "CAPA_REQUIRED"
    CAPA_PLANNING = "CAPA_PLANNING"
    ACTIONS_IN_PROGRESS = "ACTIONS_IN_PROGRESS"
    FOLLOW_UP = "FOLLOW_UP"
    EFFECTIVENESS_PLANNED = "EFFECTIVENESS_PLANNED"
    EFFECTIVENESS_REVIEW = "EFFECTIVENESS_REVIEW"
    CLOSURE_REVIEW = "CLOSURE_REVIEW"
    LEADERSHIP_ACK_REQUIRED = "LEADERSHIP_ACK_REQUIRED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class IncidentClassification(str, Enum):
    OBSERVATION = "OBSERVATION"
    ERROR = "ERROR"
    DEVIATION = "DEVIATION"
    NEAR_MISS = "NEAR_MISS"
    RISK = "RISK"


class IncidentCriticality(str, Enum):
    NON_CRITICAL = "NON_CRITICAL"
    CRITICAL = "CRITICAL"


class CapaStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ActionType(str, Enum):
    IMMEDIATE_ACTION = "IMMEDIATE_ACTION"
    CORRECTIVE_ACTION = "CORRECTIVE_ACTION"
    PREVENTIVE_ACTION = "PREVENTIVE_ACTION"


class ActionStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class ArtifactType(str, Enum):
    ATTACHMENT = "ATTACHMENT"
    CASE_REPORT_PDF = "CASE_REPORT_PDF"


class TimelineEntryType(str, Enum):
    SUBMITTED = "SUBMITTED"
    INQUIRY_OPENED = "INQUIRY_OPENED"
    INQUIRY_ANSWERED = "INQUIRY_ANSWERED"
    ASSESSED = "ASSESSED"
    ACTION_CREATED = "ACTION_CREATED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    CAPA_STARTED = "CAPA_STARTED"
    CAPA_UPDATED = "CAPA_UPDATED"
    RCA_CREATED = "RCA_CREATED"
    EFFECTIVENESS_PLANNED = "EFFECTIVENESS_PLANNED"
    EFFECTIVENESS_REVIEWED = "EFFECTIVENESS_REVIEWED"
    LEADERSHIP_FORWARDED = "LEADERSHIP_FORWARDED"
    LEADERSHIP_ACKNOWLEDGED = "LEADERSHIP_ACKNOWLEDGED"
    GROUPED = "GROUPED"
    ARTIFACT_ATTACHED = "ARTIFACT_ATTACHED"
    REPORT_GENERATED = "REPORT_GENERATED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    STATUS_CHANGED = "STATUS_CHANGED"
    MANAGEMENT_REVIEW_CREATED = "MANAGEMENT_REVIEW_CREATED"
    MANAGEMENT_REVIEW_IN_DISCUSSION = "MANAGEMENT_REVIEW_IN_DISCUSSION"
    MANAGEMENT_REVIEW_ACKNOWLEDGED = "MANAGEMENT_REVIEW_ACKNOWLEDGED"


class ManagementReviewItemStatus(str, Enum):
    INCLUDED = "included"
    IN_DISCUSSION = "in_discussion"
    ACKNOWLEDGED = "acknowledged"


class ManagementReviewBatchStatus(str, Enum):
    OPEN = "open"
    IN_DISCUSSION = "in_discussion"
    COMPLETED = "completed"


class InquiryStatus(str, Enum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"


class LeadershipAckStatus(str, Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class ModuleInternalRole(str, Enum):
    LEITUNG = "Leitung"


class EffectivenessReviewStatus(str, Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class IncidentSubmission:
    title: str
    description: str
    category: str
    reported_at: datetime
    labels: tuple[str, ...] = ()
    area: str | None = None
    process_name: str | None = None
    device: str | None = None


@dataclass(frozen=True)
class IncidentAssessmentInput:
    """QMB assessment payload from adapters (CLI/GUI).

    Explicit adapter inputs: classification, is_critical, criticality_reason,
    is_repeated, capa_required (manual flag), capa_reason, root_cause_required
    (explicit flag), VA flags, group_id.

    Service-derived fields persisted on IncidentCase: capa_required (effective),
    root_cause_required (effective), leadership_required, status.
    """

    classification: IncidentClassification
    is_critical: bool
    criticality_reason: str | None
    is_repeated: bool
    capa_required: bool
    capa_reason: str | None
    root_cause_required: bool
    group_id: str | None = None
    patient_safety_relevant: bool = False
    formal_deviation: bool = False
    system_risk_relevant: bool = False
    result_correctness_issue: bool = False
    escalation_required: bool = False


@dataclass(frozen=True)
class IncidentCase:
    incident_id: str
    status: IncidentStatus
    reporter_user_id: str
    reported_at: datetime
    title: str
    description: str
    category: str
    labels: tuple[str, ...]
    area: str | None
    process_name: str | None
    device: str | None
    classification: IncidentClassification | None
    is_critical: bool | None
    criticality_reason: str | None
    is_repeated: bool | None
    capa_required: bool | None
    capa_reason: str | None
    root_cause_required: bool | None
    group_id: str | None
    leadership_required: bool
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    archived_at: datetime | None = None


@dataclass(frozen=True)
class IncidentInquiry:
    inquiry_id: str
    incident_id: str
    question: str
    answer: str | None
    asked_by_user_id: str
    answered_by_user_id: str | None
    asked_at: datetime
    answered_at: datetime | None
    status: InquiryStatus


@dataclass(frozen=True)
class IncidentAction:
    action_id: str
    incident_id: str
    action_type: ActionType
    status: ActionStatus
    description: str
    owner_user_id: str | None
    due_at: datetime | None
    completed_at: datetime | None
    completed_by_user_id: str | None
    created_at: datetime


@dataclass(frozen=True)
class IncidentCapa:
    capa_id: str
    incident_id: str
    status: CapaStatus
    trigger_reason: str | None
    goal: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RootCauseAnalysis:
    rca_id: str
    incident_id: str
    immediate_event: str | None
    trigger: str | None
    root_causes: str | None
    similar_prior: str | None
    systemic_weakness: str | None
    future_risk: str | None
    method: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class EffectivenessReview:
    review_id: str
    incident_id: str
    planned_at: datetime
    criteria: str
    completed_at: datetime | None
    completed_by_user_id: str | None
    result: str | None
    effective: bool | None
    notes: str | None
    status: EffectivenessReviewStatus
    created_at: datetime


@dataclass(frozen=True)
class IncidentArtifact:
    artifact_id: str
    incident_id: str
    artifact_type: ArtifactType
    storage_key: str
    original_filename: str
    mime_type: str | None
    sha256: str | None
    size_bytes: int | None
    metadata: dict[str, str]
    created_at: datetime


@dataclass(frozen=True)
class IncidentGroup:
    group_id: str
    name: str
    description: str | None
    created_by_user_id: str
    created_at: datetime


@dataclass(frozen=True)
class LeadershipAcknowledgement:
    ack_id: str
    incident_id: str
    forwarded_by_user_id: str
    forwarded_at: datetime
    leadership_user_id: str
    comment: str | None
    acknowledged_at: datetime | None
    status: LeadershipAckStatus


@dataclass(frozen=True)
class ManagementReviewBatch:
    batch_id: str
    period_start: datetime
    period_end: datetime
    status: ManagementReviewBatchStatus
    created_by_user_id: str
    created_at: datetime
    report_storage_key: str | None = None


@dataclass(frozen=True)
class ManagementReviewItem:
    item_id: str
    batch_id: str
    incident_id: str
    status: ManagementReviewItemStatus
    acknowledged_at: datetime | None = None
    acknowledged_by_user_id: str | None = None


@dataclass(frozen=True)
class IncidentTimelineEntry:
    entry_id: str
    incident_id: str
    entry_type: TimelineEntryType
    actor_user_id: str | None
    summary: str
    details: dict[str, str]
    created_at: datetime


@dataclass(frozen=True)
class ModuleRoleAssignment:
    assignment_id: str
    user_id: str
    role_name: ModuleInternalRole
    assigned_by_user_id: str
    assigned_at: datetime


@dataclass(frozen=True)
class ReportResult:
    report_id: str
    filename: str
    storage_key: str | None
    mime_type: str
    size_bytes: int
    report_template_id: str = "default"


@dataclass(frozen=True)
class ManagementReviewReport:
    report_id: str
    batch_id: str
    filename: str
    storage_key: str
    mime_type: str
    size_bytes: int
    generated_at: datetime


@dataclass(frozen=True)
class IncidentListFilter:
    status: IncidentStatus | None = None
    category: str | None = None
    reporter_user_id: str | None = None
    from_reported_at: datetime | None = None
    to_reported_at: datetime | None = None


@dataclass(frozen=True)
class SimilarIncidentQuery:
    incident_id: str | None = None
    category: str | None = None
    labels: tuple[str, ...] = ()
    area: str | None = None
    process_name: str | None = None
    device: str | None = None
    from_reported_at: datetime | None = None
    to_reported_at: datetime | None = None
    limit: int = 20
