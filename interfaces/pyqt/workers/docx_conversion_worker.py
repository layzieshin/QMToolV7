from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, pyqtSignal


class DocxConversionWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[], object]) -> None:
        super().__init__()
        self._task = task

    def run(self) -> None:
        try:
            output = self._task()
            if output is None:
                raise RuntimeError("DOCX-zu-PDF Konvertierung lieferte kein Ergebnis")
            self.finished.emit(output)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
