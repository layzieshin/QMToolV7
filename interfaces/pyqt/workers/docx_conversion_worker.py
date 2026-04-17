from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal


class DocxConversionWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, converter, docx_path: Path) -> None:
        super().__init__()
        self._converter = converter
        self._docx_path = docx_path

    def run(self) -> None:
        try:
            output = self._converter(self._docx_path)
            if output is None:
                raise RuntimeError("DOCX-zu-PDF Konvertierung lieferte kein Ergebnis")
            self.finished.emit(output)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
