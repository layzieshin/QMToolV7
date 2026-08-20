"""DOCX to PDF conversion for the documents module (Windows + Word COM)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .errors import ValidationError

_STDIO_PATCHED = False
_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_COM_OBJECT_RE = re.compile(r"<COMObject[^>]*>")


def _redact_error_message(exc: BaseException) -> str:
    """Return a user-safe summary without full paths or raw COM representations."""
    name = type(exc).__name__
    text = str(exc).strip()
    if not text:
        return name
    text = _PATH_RE.sub("<path>", text)
    text = _COM_OBJECT_RE.sub("<COMObject>", text)
    if len(text) > 160:
        text = text[:157] + "..."
    return f"{name}: {text}"


def docx_conversion_available() -> bool:
    """True when this host can run DOCX→PDF conversion (Windows + Word COM or docx2pdf)."""
    if os.name != "nt":
        return False
    try:
        import win32com.client  # type: ignore[import]  # noqa: F401
    except ImportError:
        pass
    else:
        return True
    try:
        import docx2pdf  # type: ignore[import]  # noqa: F401
    except ImportError:
        return False
    return True


def prepare_frozen_stdio() -> None:
    """Redirect missing stdout/stderr (PyInstaller --windowed) so tqdm/docx2pdf do not crash."""
    global _STDIO_PATCHED
    if _STDIO_PATCHED:
        return
    devnull = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stdout is None:
        sys.stdout = devnull
    if sys.stderr is None:
        sys.stderr = devnull
    _STDIO_PATCHED = True


def _disable_docx2pdf_progress() -> None:
    try:
        from functools import partialmethod

        from tqdm import tqdm

        tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)  # type: ignore[method-assign]
    except Exception:  # noqa: BLE001
        return


def _convert_with_word_com(source: Path, target: Path) -> None:
    import win32com.client  # type: ignore[import]

    source_resolved = source.resolve()
    target_resolved = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False
        doc = word.Documents.Open(str(source_resolved))
        if doc.Revisions.Count > 0:
            doc.Revisions.AcceptAll()
        doc.ExportAsFixedFormat(
            str(target_resolved),
            17,
            False,
            0,
            0,
            1,
            1,
            0,
            True,
            True,
            0,
            True,
            True,
            False,
        )
    finally:
        if doc is not None:
            try:
                doc.Close(False)
            except Exception:  # noqa: BLE001
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001
                pass


def _convert_with_docx2pdf(source: Path, target: Path) -> None:
    prepare_frozen_stdio()
    _disable_docx2pdf_progress()
    try:
        from docx2pdf import convert  # type: ignore[import]
    except ImportError as exc:
        raise ValidationError(
            "docx2pdf ist nicht verfügbar. Bitte pywin32/Microsoft Word installieren "
            "oder pip install docx2pdf ausführen."
        ) from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    convert(str(source.resolve()), str(target.resolve()))


def convert_docx_to_pdf(source: Path, target: Path) -> None:
    """Convert DOCX to PDF using Word COM (preferred) or docx2pdf fallback."""
    if os.name != "nt":
        raise ValidationError("DOCX-zu-PDF wird nur unter Windows unterstützt")

    source_path = Path(source)
    target_path = Path(target)
    if not source_path.is_file():
        raise ValidationError(f"DOCX-Quelldatei nicht gefunden: {source_path.name}")

    com_initialized = False
    try:
        import pythoncom  # type: ignore[import]

        pythoncom.CoInitialize()
        com_initialized = True
    except ImportError:
        pass

    try:
        try:
            _convert_with_word_com(source_path, target_path)
        except ImportError:
            _convert_with_docx2pdf(source_path, target_path)
        except Exception as word_exc:
            try:
                _convert_with_docx2pdf(source_path, target_path)
            except Exception as fallback_exc:
                raise ValidationError(
                    "DOCX-zu-PDF fehlgeschlagen. Microsoft Word ist erforderlich "
                    f"(COM: {_redact_error_message(word_exc)}; "
                    f"Fallback: {_redact_error_message(fallback_exc)})"
                ) from fallback_exc
    finally:
        if com_initialized:
            try:
                import pythoncom  # type: ignore[import]

                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass

    if not target_path.is_file() or target_path.stat().st_size == 0:
        raise ValidationError(f"DOCX-zu-PDF erzeugte keine gültige Ausgabedatei: {target_path}")
