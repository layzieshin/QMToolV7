from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import DocumentReadReceipt, PdfReadProgress, TrackedPdfReadSession
from .repository import DocumentsRepository


class PdfReadTrackingService:
    def __init__(self, repository: DocumentsRepository, event_bus: object | None = None) -> None:
        self._repository = repository
        self._event_bus = event_bus

    def start(
        self,
        *,
        user_id: str,
        document_id: str,
        version: int,
        artifact_id: str | None,
        total_pages: int,
        source: str,
        min_seconds_per_page: int = 10,
    ) -> TrackedPdfReadSession:
        now = datetime.now(timezone.utc)
        session = TrackedPdfReadSession(
            session_id=uuid4().hex,
            user_id=user_id,
            document_id=document_id,
            version=version,
            artifact_id=artifact_id,
            total_pages=total_pages,
            min_seconds_per_page=min_seconds_per_page,
            source=source,
            opened_at=now,
        )
        self._repository.create_pdf_read_session(session)
        self._publish("domain.documents.read.session.started.v1", {"session_id": session.session_id})
        return session

    def record_page_dwell(self, session_id: str, *, page_number: int, dwell_seconds: int) -> PdfReadProgress:
        progress = self._repository.get_pdf_read_progress(session_id)
        current = 0 if progress is None else int(progress.page_seconds.get(page_number, 0))
        updated = max(0, current + max(0, dwell_seconds))
        threshold = 10
        self._repository.update_pdf_read_page_progress(session_id, page_number, updated, updated >= threshold)
        return self._repository.get_pdf_read_progress(session_id) or PdfReadProgress(
            session_id=session_id,
            total_pages=0,
            completed_pages=(),
            missing_pages=(),
            page_seconds={},
            is_complete=False,
        )

    def get_progress(self, session_id: str) -> PdfReadProgress:
        return self._repository.get_pdf_read_progress(session_id) or PdfReadProgress(
            session_id=session_id,
            total_pages=0,
            completed_pages=(),
            missing_pages=(),
            page_seconds={},
            is_complete=False,
        )

    def finalize(self, session_id: str, *, source: str) -> DocumentReadReceipt | None:
        progress = self._repository.get_pdf_read_progress(session_id)
        session = self._repository.get_pdf_read_session(session_id)
        now = datetime.now(timezone.utc)
        if progress is None or session is None or not progress.is_complete:
            self._repository.complete_pdf_read_session(
                session_id, completed_at=now.isoformat(), completion_result="INCOMPLETE"
            )
            self._publish("domain.documents.read.session.incomplete.v1", {"session_id": session_id, "source": source})
            return None
        self._repository.complete_pdf_read_session(
            session_id, completed_at=now.isoformat(), completion_result="COMPLETE"
        )
        receipt = DocumentReadReceipt(
            receipt_id=uuid4().hex,
            user_id=session.user_id,
            document_id=session.document_id,
            version=session.version,
            confirmed_at=now,
            source=source,
        )
        self._repository.create_read_receipt(receipt)
        self._publish("domain.documents.read.session.completed.v1", {"session_id": session_id, "source": source})
        return receipt

    def _publish(self, name: str, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if callable(publish):
            publish(EventEnvelope.create(name=name, module_id="documents", payload=payload))
