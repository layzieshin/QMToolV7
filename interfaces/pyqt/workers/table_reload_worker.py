from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass(frozen=True)
class TableReloadResult:
    rows: list[object]
    scope: str
    status_filter: str
    advanced_filters: dict[str, object]


class TableReloadWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, loader: Callable[[], TableReloadResult]) -> None:
        super().__init__()
        self._loader = loader

    def run(self) -> None:
        try:
            result = self._loader()
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
