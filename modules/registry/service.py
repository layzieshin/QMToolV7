from __future__ import annotations

from datetime import datetime, timezone

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import RegistryEntry, RegisterState, ReleaseEvidenceMode
from .repository import RegistryRepository


class RegistryService:
    def __init__(self, repository: RegistryRepository) -> None:
        self._repository = repository

    def get_entry(self, document_id: str) -> RegistryEntry | None:
        return self._repository.get(document_id)

    def list_entries(self) -> list[RegistryEntry]:
        return self._repository.list_entries()

    def apply_documents_state(
        self,
        *,
        document_id: str,
        version: int,
        status: str,
        release_evidence_mode: ReleaseEvidenceMode | str = ReleaseEvidenceMode.WORKFLOW,
        release_note: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        event: EventEnvelope | None = None,
    ) -> RegistryEntry:
        mode = (
            release_evidence_mode
            if isinstance(release_evidence_mode, ReleaseEvidenceMode)
            else ReleaseEvidenceMode(str(release_evidence_mode))
        )
        current = self._repository.get(document_id)
        register_state, is_findable = self._map_register_state(status)
        active_version = current.active_version if current else None

        if status == "APPROVED":
            active_version = version
        elif status == "ARCHIVED" and active_version == version:
            active_version = None
            is_findable = False

        update_event_id = event.event_id if event is not None else f"state-sync:{document_id}:{version}:{status}"
        update_at = self._parse_event_time(event.occurred_at_utc) if event is not None else datetime.now(timezone.utc)
        entry = RegistryEntry(
            document_id=document_id,
            active_version=active_version,
            release_note=release_note if release_note is not None else (current.release_note if current else None),
            # Keep registry projection aligned with the latest workflow profile semantics.
            release_evidence_mode=mode,
            register_state=register_state,
            is_findable=is_findable,
            valid_from=valid_from if valid_from is not None else (current.valid_from if current else None),
            valid_until=valid_until if valid_until is not None else (current.valid_until if current else None),
            last_update_event_id=update_event_id,
            last_update_at=update_at,
        )
        self._repository.upsert(entry)
        return entry

    @staticmethod
    def _parse_event_time(raw: str) -> datetime:
        value = datetime.fromisoformat(raw)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @staticmethod
    def _map_register_state(status: str) -> tuple[RegisterState, bool]:
        if status == "APPROVED":
            return RegisterState.VALID, True
        if status == "IN_REVIEW":
            return RegisterState.IN_REVIEW, True
        if status == "IN_PROGRESS":
            return RegisterState.IN_PROGRESS, True
        if status == "ARCHIVED":
            return RegisterState.ARCHIVED, False
        return RegisterState.INVALID, True
