from __future__ import annotations

from pathlib import Path

from interfaces.pyqt.workers.docx_conversion_worker import DocxConversionWorker


def test_docx_conversion_worker_emits_finished(tmp_path: Path) -> None:
    output_path = tmp_path / "out.pdf"
    output_path.write_bytes(b"pdf")
    events: dict[str, object] = {}

    worker = DocxConversionWorker(lambda _docx: output_path, tmp_path / "input.docx")
    worker.finished.connect(lambda path: events.setdefault("path", path))
    worker.failed.connect(lambda err: events.setdefault("error", err))
    worker.run()

    assert events.get("path") == output_path
    assert "error" not in events


def test_docx_conversion_worker_emits_failed_on_exception(tmp_path: Path) -> None:
    events: dict[str, object] = {}

    def _raise(_docx: Path) -> Path:
        raise RuntimeError("boom")

    worker = DocxConversionWorker(_raise, tmp_path / "input.docx")
    worker.finished.connect(lambda path: events.setdefault("path", path))
    worker.failed.connect(lambda err: events.setdefault("error", err))
    worker.run()

    assert "path" not in events
    assert "boom" in str(events.get("error"))
