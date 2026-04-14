from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RegisterState(str, Enum):
    VALID = "VALID"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    INVALID = "INVALID"
    ARCHIVED = "ARCHIVED"


class ReleaseEvidenceMode(str, Enum):
    WORKFLOW = "WORKFLOW"
    REGISTRY_NOTE = "REGISTRY_NOTE"


@dataclass(frozen=True)
class RegistryEntry:
    document_id: str
    active_version: int | None
    release_note: str | None
    release_evidence_mode: ReleaseEvidenceMode
    register_state: RegisterState
    is_findable: bool
    valid_from: datetime | None
    valid_until: datetime | None
    last_update_event_id: str
    last_update_at: datetime
