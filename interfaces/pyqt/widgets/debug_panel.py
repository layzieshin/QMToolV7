from __future__ import annotations

from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from interfaces.pyqt.contributions.common import as_json_text


class DebugPanel(QWidget):
    """Technical payload/exception viewer for admin/debug contexts."""

    def __init__(self) -> None:
        super().__init__()
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._out, stretch=1)

    def set_payload(self, payload: object) -> None:
        self._out.setPlainText(as_json_text(payload))

    def append_payload(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")
