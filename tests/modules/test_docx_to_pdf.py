from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.documents.docx_to_pdf import (
    _disable_docx2pdf_progress,
    convert_docx_to_pdf,
    prepare_frozen_stdio,
)
from modules.documents.errors import ValidationError


def test_prepare_frozen_stdio_redirects_none_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    import modules.documents.docx_to_pdf as module

    monkeypatch.setattr(module, "_STDIO_PATCHED", False)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    prepare_frozen_stdio()

    assert sys.stdout is not None
    assert sys.stderr is not None
    assert hasattr(sys.stdout, "flush")
    assert hasattr(sys.stderr, "flush")


def test_prepare_frozen_stdio_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    import modules.documents.docx_to_pdf as module

    sentinel = object()
    monkeypatch.setattr(module, "_STDIO_PATCHED", True)
    monkeypatch.setattr(sys, "stdout", sentinel)
    monkeypatch.setattr(sys, "stderr", sentinel)

    prepare_frozen_stdio()

    assert sys.stdout is sentinel
    assert sys.stderr is sentinel


def test_disable_docx2pdf_progress_does_not_raise() -> None:
    _disable_docx2pdf_progress()


def test_convert_docx_to_pdf_rejects_non_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("os.name", "posix")
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    with pytest.raises(ValidationError, match="nur unter Windows"):
        convert_docx_to_pdf(source, target)


def test_convert_docx_to_pdf_rejects_missing_source(tmp_path: Path) -> None:
    target = tmp_path / "out.pdf"

    with pytest.raises(ValidationError, match="nicht gefunden"):
        convert_docx_to_pdf(tmp_path / "missing.docx", target)


def test_convert_docx_to_pdf_uses_word_com(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("os.name", "nt")
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    word = MagicMock()
    doc = MagicMock()
    doc.Revisions.Count = 0
    word.Documents.Open.return_value = doc

    monkeypatch.setitem(sys.modules, "win32com", MagicMock())
    monkeypatch.setitem(sys.modules, "win32com.client", MagicMock())
    import win32com.client  # type: ignore[import]

    monkeypatch.setattr(win32com.client, "Dispatch", lambda _name: word)

    def _fake_com_init() -> None:
        return None

    monkeypatch.setitem(sys.modules, "pythoncom", MagicMock())
    import pythoncom  # type: ignore[import]

    monkeypatch.setattr(pythoncom, "CoInitialize", _fake_com_init)
    monkeypatch.setattr(pythoncom, "CoUninitialize", lambda: None)

    def _write_pdf(src: Path, dst: Path) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        "modules.documents.docx_to_pdf._convert_with_word_com",
        _write_pdf,
    )

    convert_docx_to_pdf(source, target)
    assert target.is_file()
    assert target.stat().st_size > 0


def test_convert_docx_to_pdf_rejects_empty_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("os.name", "nt")
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    monkeypatch.setitem(sys.modules, "pythoncom", MagicMock())
    import pythoncom  # type: ignore[import]

    monkeypatch.setattr(pythoncom, "CoInitialize", lambda: None)
    monkeypatch.setattr(pythoncom, "CoUninitialize", lambda: None)
    monkeypatch.setattr(
        "modules.documents.docx_to_pdf._convert_with_word_com",
        lambda _src, dst: dst.write_bytes(b""),
    )

    with pytest.raises(ValidationError, match="keine gültige Ausgabedatei"):
        convert_docx_to_pdf(source, target)
