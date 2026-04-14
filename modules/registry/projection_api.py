from __future__ import annotations

from datetime import datetime

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import RegistryEntry, ReleaseEvidenceMode
from .service import RegistryService


class RegistryProjectionApi:
    def __init__(
        self,
        service: RegistryService,
        *,
        event_bus: object | None = None,
        logger: object | None = None,
    ) -> None:
        self._service = service
        self._event_bus = event_bus
        self._logger = logger

    def apply_documents_projection(
        self,
        *,
        source_module_id: str,
        document_id: str,
        version: int,
        status: str,
        release_evidence_mode: ReleaseEvidenceMode = ReleaseEvidenceMode.WORKFLOW,
        release_note: str | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        event: EventEnvelope | None = None,
    ) -> RegistryEntry:
        if source_module_id != "documents":
            self._publish_projection_rejected(
                source_module_id=source_module_id,
                document_id=document_id,
                version=version,
                status=status,
            )
            raise PermissionError("registry projection updates are only allowed from documents module")
        return self._service.apply_documents_state(
            document_id=document_id,
            version=version,
            status=status,
            release_evidence_mode=release_evidence_mode,
            release_note=release_note,
            valid_from=valid_from,
            valid_until=valid_until,
            event=event,
        )

    def _publish_projection_rejected(
        self,
        *,
        source_module_id: str,
        document_id: str,
        version: int,
        status: str,
    ) -> None:
        if self._logger is not None:
            warning = getattr(self._logger, "warning", None)
            if callable(warning):
                warning(
                    "registry",
                    "projection update rejected",
                    {
                        "source_module_id": source_module_id,
                        "document_id": document_id,
                        "version": version,
                        "status": status,
                    },
                )
        if self._event_bus is not None:
            publish = getattr(self._event_bus, "publish", None)
            if callable(publish):
                publish(
                    EventEnvelope.create(
                        name="domain.registry.projection.rejected.v1",
                        module_id="registry",
                        actor_user_id=source_module_id,
                        payload={
                            "source_module_id": source_module_id,
                            "document_id": document_id,
                            "version": version,
                            "status": status,
                        },
                    )
                )
