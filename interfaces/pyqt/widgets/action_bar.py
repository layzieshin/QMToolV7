from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ActionBar(QWidget):
    """Reusable action bar with simple visibility control."""

    def __init__(self) -> None:
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._buttons: dict[str, QPushButton] = {}
        self._layout.setContentsMargins(0, 0, 0, 0)

    def add_action(self, key: str, label: str, handler: Callable[[], None]) -> QPushButton:
        button = QPushButton(label)
        button.clicked.connect(handler)
        self._layout.addWidget(button)
        self._buttons[key] = button
        return button

    def finish(self) -> None:
        self._layout.addStretch(1)

    def buttons(self) -> dict[str, QPushButton]:
        return self._buttons

    def set_visible_enabled(self, *, visible: set[str], enabled: set[str]) -> None:
        for key, button in self._buttons.items():
            button.setVisible(key in visible)
            button.setEnabled(key in enabled)
