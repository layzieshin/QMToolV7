from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.documents.docx_to_pdf import (
    _convert_with_word_com,
    _disable_docx2pdf_progress,
    _redact_error_message,
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


def _install_win32com_mocks(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    monkeypatch.setitem(sys.modules, "win32com", MagicMock())
    monkeypatch.setitem(sys.modules, "win32com.client", MagicMock())
    import win32com.client  # type: ignore[import]

    dispatch_ex = MagicMock()
    dispatch = MagicMock()
    monkeypatch.setattr(win32com.client, "DispatchEx", dispatch_ex)
    monkeypatch.setattr(win32com.client, "Dispatch", dispatch)
    return dispatch_ex, dispatch


def test_convert_with_word_com_uses_dispatch_ex(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    dispatch_ex, dispatch = _install_win32com_mocks(monkeypatch)
    word = MagicMock()
    doc = MagicMock()
    doc.Revisions.Count = 0
    word.Documents.Open.return_value = doc
    dispatch_ex.return_value = word

    def _export(_output: str, *_args: object, **_kwargs: object) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4\n")

    doc.ExportAsFixedFormat.side_effect = _export

    _convert_with_word_com(source, target)

    dispatch_ex.assert_called_once_with("Word.Application")
    dispatch.assert_not_called()
    word.Quit.assert_called_once()
    doc.Close.assert_called_once_with(False)


def test_convert_with_word_com_success_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    dispatch_ex, _dispatch = _install_win32com_mocks(monkeypatch)
    word = MagicMock()
    doc = MagicMock()
    doc.Revisions.Count = 2
    word.Documents.Open.return_value = doc
    dispatch_ex.return_value = word

    def _export(_output: str, *_args: object, **_kwargs: object) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"%PDF-1.4\n")

    doc.ExportAsFixedFormat.side_effect = _export

    _convert_with_word_com(source, target)

    doc.Revisions.AcceptAll.assert_called_once()
    word.Quit.assert_called_once()
    doc.Close.assert_called_once_with(False)
    assert target.is_file()


def test_convert_with_word_com_open_failure_quits_owned_instance_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    dispatch_ex, _dispatch = _install_win32com_mocks(monkeypatch)
    word = MagicMock()
    word.Documents.Open.side_effect = RuntimeError("open failed")
    dispatch_ex.return_value = word

    with pytest.raises(RuntimeError, match="open failed"):
        _convert_with_word_com(source, target)

    word.Quit.assert_called_once()
    word.Documents.Open.assert_called_once()


def test_convert_with_word_com_export_failure_closes_doc_and_quits(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    dispatch_ex, _dispatch = _install_win32com_mocks(monkeypatch)
    word = MagicMock()
    doc = MagicMock()
    doc.Revisions.Count = 0
    doc.ExportAsFixedFormat.side_effect = RuntimeError("export failed")
    word.Documents.Open.return_value = doc
    dispatch_ex.return_value = word

    with pytest.raises(RuntimeError, match="export failed"):
        _convert_with_word_com(source, target)

    doc.Close.assert_called_once_with(False)
    word.Quit.assert_called_once()


def test_convert_with_word_com_dispatch_failure_does_not_quit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"

    dispatch_ex, _dispatch = _install_win32com_mocks(monkeypatch)
    dispatch_ex.side_effect = RuntimeError("dispatch failed")

    with pytest.raises(RuntimeError, match="dispatch failed"):
        _convert_with_word_com(source, target)

    dispatch_ex.assert_called_once_with("Word.Application")


def test_redact_error_message_strips_paths_and_com_repr() -> None:
    exc = RuntimeError(r"failed at C:\Users\secret\file.docx with <COMObject Word.Application>")
    message = _redact_error_message(exc)
    assert r"C:\Users\secret\file.docx" not in message
    assert "<path>" in message
    assert "<COMObject>" in message
    assert "RuntimeError" in message


def test_convert_docx_to_pdf_redacts_com_and_fallback_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("os.name", "nt")
    source = tmp_path / "in.docx"
    source.write_bytes(b"docx")
    target = tmp_path / "out.pdf"
    secret = str(source.resolve())

    monkeypatch.setitem(sys.modules, "pythoncom", MagicMock())
    import pythoncom  # type: ignore[import]

    monkeypatch.setattr(pythoncom, "CoInitialize", lambda: None)
    monkeypatch.setattr(pythoncom, "CoUninitialize", lambda: None)
    monkeypatch.setattr(
        "modules.documents.docx_to_pdf._convert_with_word_com",
        MagicMock(side_effect=RuntimeError(f"COM failed at {secret}")),
    )
    monkeypatch.setattr(
        "modules.documents.docx_to_pdf._convert_with_docx2pdf",
        MagicMock(side_effect=RuntimeError(f"fallback failed at {secret}")),
    )

    with pytest.raises(ValidationError, match="DOCX-zu-PDF fehlgeschlagen") as exc_info:
        convert_docx_to_pdf(source, target)

    message = str(exc_info.value)
    assert secret not in message
    assert "<path>" in message
