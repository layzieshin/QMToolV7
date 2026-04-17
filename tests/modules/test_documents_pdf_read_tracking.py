from __future__ import annotations

from pathlib import Path

from modules.documents.pdf_read_tracking_service import PdfReadTrackingService
from modules.documents.sqlite_repository import SQLiteDocumentsRepository


def test_pdf_read_tracking_completes_after_all_pages(tmp_path: Path) -> None:
    repo = SQLiteDocumentsRepository(tmp_path / "docs.db", Path("modules/documents/schema.sql"))
    service = PdfReadTrackingService(repo)
    session = service.start(
        user_id="u1",
        document_id="VA-1",
        version=1,
        artifact_id=None,
        total_pages=2,
        source="test",
        min_seconds_per_page=10,
    )
    service.record_page_dwell(session.session_id, page_number=1, dwell_seconds=10)
    service.record_page_dwell(session.session_id, page_number=2, dwell_seconds=10)
    receipt = service.finalize(session.session_id, source="test")
    assert receipt is not None
    assert receipt.document_id == "VA-1"
