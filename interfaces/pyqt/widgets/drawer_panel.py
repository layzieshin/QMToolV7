from __future__ import annotations

from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class DrawerPanel(QWidget):
    """Simple collapsible right drawer container."""

    def __init__(self, title: str = "Details") -> None:
        super().__init__()
        self._toggle = QPushButton(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.toggled.connect(self.setVisible)
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        outer = QVBoxLayout(self)
        outer.addLayout(self._content_layout)
        self.setVisible(False)

    def set_content_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def toggle_button(self) -> QPushButton:
        return self._toggle
