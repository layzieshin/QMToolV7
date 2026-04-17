from __future__ import annotations

from datetime import datetime, timezone

from interfaces.pyqt.presenters.documents_detail_presenter import DocumentsDetailPresenter


def test_format_dt_renders_local_from_utc() -> None:
    value = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    rendered = DocumentsDetailPresenter.format_dt(value)
    assert rendered != "-"
    assert ":" in rendered
