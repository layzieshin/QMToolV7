from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class _CanvasWidget(QWidget):
    def __init__(self, width: int = 600, height: int = 220) -> None:
        super().__init__()
        self.setFixedSize(width, height)
        self._image = QImage(width, height, QImage.Format.Format_ARGB32)
        self._image.fill(Qt.GlobalColor.transparent)
        self._history: list[QImage] = []
        self._last_point: QPoint | None = None
        self._eraser = False
        self._stroke_width = 3
        self._antialiasing = True

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.drawImage(0, 0, self._image)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._history.append(self._image.copy())
        self._last_point = event.position().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._last_point is None:
            return
        painter = QPainter(self._image)
        if self._antialiasing:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("white") if self._eraser else QColor("black")
        pen = QPen(color, self._stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        new_point = event.position().toPoint()
        painter.drawLine(self._last_point, new_point)
        self._last_point = new_point
        self.update()

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:  # noqa: N802
        self._last_point = None

    def set_eraser(self, enabled: bool) -> None:
        self._eraser = enabled

    def set_stroke_width(self, value: int) -> None:
        self._stroke_width = max(1, value)

    def set_antialiasing(self, enabled: bool) -> None:
        self._antialiasing = enabled

    def clear(self) -> None:
        self._history.append(self._image.copy())
        self._image.fill(Qt.GlobalColor.transparent)
        self.update()

    def undo(self) -> None:
        if not self._history:
            return
        self._image = self._history.pop()
        self.update()

    def save_png(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._image.save(str(path), "PNG")
        return path

    def png_bytes(self) -> bytes:
        image = self._image
        from PyQt6.QtCore import QBuffer, QIODevice

        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(buffer.data())


class SignatureCanvasDialog(QDialog):
    """Dialog for drawing and saving handwritten signature PNG."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signatur zeichnen")
        self._canvas = _CanvasWidget()
        self._saved_path: Path | None = None
        self._saved_bytes: bytes | None = None
        width_slider = QSlider(Qt.Orientation.Horizontal)
        width_slider.setMinimum(1)
        width_slider.setMaximum(20)
        width_slider.setValue(3)
        width_slider.valueChanged.connect(self._canvas.set_stroke_width)

        row = QHBoxLayout()
        eraser_btn = QPushButton("Radierer")
        eraser_btn.setCheckable(True)
        eraser_btn.toggled.connect(self._canvas.set_eraser)
        undo_btn = QPushButton("Undo")
        undo_btn.clicked.connect(self._canvas.undo)
        clear_btn = QPushButton("Leeren")
        clear_btn.clicked.connect(self._canvas.clear)
        aa_btn = QPushButton("Anti-Aliasing")
        aa_btn.setCheckable(True)
        aa_btn.setChecked(True)
        aa_btn.toggled.connect(self._canvas.set_antialiasing)
        use_btn = QPushButton("Als aktive Signatur übernehmen")
        use_btn.clicked.connect(self._accept_canvas)
        save_btn = QPushButton("Als PNG exportieren")
        save_btn.clicked.connect(self._save_as)
        row.addWidget(QLabel("Strichstärke"))
        row.addWidget(width_slider)
        row.addWidget(eraser_btn)
        row.addWidget(undo_btn)
        row.addWidget(clear_btn)
        row.addWidget(aa_btn)
        row.addWidget(use_btn)
        row.addWidget(save_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._canvas)
        layout.addWidget(buttons)

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Signatur speichern", "", "PNG (*.png)")
        if not path:
            return
        self._saved_path = self._canvas.save_png(Path(path))
        self._saved_bytes = self._canvas.png_bytes()

    def _accept_canvas(self) -> None:
        self._saved_bytes = self._canvas.png_bytes()
        self.accept()

    def saved_path(self) -> Path | None:
        return self._saved_path

    def signature_bytes(self) -> bytes | None:
        return self._saved_bytes
