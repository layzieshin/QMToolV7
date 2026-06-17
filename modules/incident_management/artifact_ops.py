"""Artifact attachment operations."""
from __future__ import annotations

from pathlib import Path

from . import authorization as auth
from . import eventing
from .contracts import (
    ArtifactType,
    IncidentArtifact,
    IncidentTimelineEntry,
    TimelineEntryType,
    ValidationError,
)
from .sqlite_repository import SQLiteIncidentRepository
from .storage import IncidentArtifactStorage


def attach_artifact(
    *,
    repo: SQLiteIncidentRepository,
    storage: IncidentArtifactStorage,
    event_bus: object | None,
    audit_logger: object | None,
    user: object,
    incident_id: str,
    source_path: Path,
    artifact_type: ArtifactType = ArtifactType.ATTACHMENT,
    metadata: dict[str, str] | None = None,
) -> IncidentArtifact:
    auth.require_authenticated(user)
    repo.get_incident(incident_id)
    path = Path(source_path)
    if not path.is_file():
        raise ValidationError(f"source file not found: {path}")
    now = eventing.utcnow()
    stored = storage.store_file_copy(
        source_path=path,
        incident_id=incident_id,
        artifact_type=artifact_type.value,
    )
    artifact = IncidentArtifact(
        artifact_id=eventing.new_id(),
        incident_id=incident_id,
        artifact_type=artifact_type,
        storage_key=stored.storage_key,
        original_filename=path.name,
        mime_type=stored.mime_type,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        metadata=metadata or {},
        created_at=now,
    )
    repo.add_artifact(artifact)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.ARTIFACT_ATTACHED,
        artifact_id=artifact.artifact_id,
        artifact_type=artifact_type.value,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.ARTIFACT_ATTACHED,
            actor_user_id=auth.user_id(user),
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    eventing.emit_audit(
        audit_logger,
        action="incident.artifact.add",
        actor=auth.user_id(user),
        target=incident_id,
        result="ok",
    )
    eventing.publish_event(
        event_bus,
        "domain.incident_management.artifact.attached.v1",
        actor_user_id=auth.user_id(user),
        payload={
            "incident_id": incident_id,
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact_type.value,
            "uploaded_by": auth.user_id(user),
            "occurred_at": now.isoformat(),
        },
    )
    return artifact


def register_generated_artifact(
    *,
    repo: SQLiteIncidentRepository,
    storage: IncidentArtifactStorage,
    incident_id: str,
    filename: str,
    data: bytes,
    artifact_type: ArtifactType,
    actor_user_id: str | None,
    metadata: dict[str, str] | None = None,
) -> IncidentArtifact:
    now = eventing.utcnow()
    stored = storage.write_bytes(
        incident_id=incident_id,
        artifact_type=artifact_type.value,
        filename=filename,
        data=data,
    )
    artifact = IncidentArtifact(
        artifact_id=eventing.new_id(),
        incident_id=incident_id,
        artifact_type=artifact_type,
        storage_key=stored.storage_key,
        original_filename=filename,
        mime_type=stored.mime_type,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        metadata=metadata or {},
        created_at=now,
    )
    repo.add_artifact(artifact)
    summary, details = eventing.timeline_summary(
        TimelineEntryType.REPORT_GENERATED,
        artifact_id=artifact.artifact_id,
    )
    repo.add_timeline_entry(
        IncidentTimelineEntry(
            entry_id=eventing.new_id(),
            incident_id=incident_id,
            entry_type=TimelineEntryType.REPORT_GENERATED,
            actor_user_id=actor_user_id,
            summary=summary,
            details=details,
            created_at=now,
        )
    )
    return artifact
