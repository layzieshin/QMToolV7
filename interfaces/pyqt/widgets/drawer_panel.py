from __future__ import annotations

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter, QVBoxLayout, QWidget


class VerticalFlowButton(QPushButton):
    """Button with text rotated 90° clockwise (reads top-to-bottom)."""

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QStylePainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        text = option.text
        option.text = ""
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        if not text:
            return
        painter.save()
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(90)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        rect = QRect(-text_w // 2, -text_h // 2, text_w, text_h)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        base = super().sizeHint()
        # Swap width/height so the button is narrow but tall
        return QSize(base.height(), base.width())


class DrawerPanel(QWidget):
    """Simple collapsible right drawer container."""

    def __init__(self, title: str = "Details") -> None:
        super().__init__()
        self._syncing = False
        self._toggle = VerticalFlowButton(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(False)
        self._toggle.toggled.connect(self.set_open)
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        outer = QVBoxLayout(self)
        outer.addLayout(self._content_layout)
        self.setVisible(False)

    def set_content_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def toggle_button(self) -> QPushButton:
        return self._toggle

    def set_open(self, open_state: bool) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            if self._toggle.isChecked() != open_state:
                self._toggle.setChecked(open_state)
            super().setVisible(open_state)
        finally:
            self._syncing = False

    def is_open(self) -> bool:
        return self.isVisible()

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        self.set_open(bool(visible))

