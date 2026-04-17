"""Zoom/pan graphics view and draggable signature pixmap for placement dialog."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainterPath, QPixmap
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsView, QSlider


class ZoomablePlacementView(QGraphicsView):
    """QGraphicsView that supports Ctrl+scroll zoom and double-click-to-place."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._zoom_slider: QSlider | None = None
        self._click_callback = None
        self._pan_active = False
        self._pan_last_pos = None
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if self._zoom_slider is not None:
                step = 12 if event.angleDelta().y() > 0 else -12
                self._zoom_slider.setValue(
                    max(
                        self._zoom_slider.minimum(),
                        min(self._zoom_slider.maximum(), self._zoom_slider.value() + step),
                    )
                )
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.RightButton:
            self._pan_active = True
            self._pan_last_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._click_callback is not None:
            self._click_callback(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._pan_active and self._pan_last_pos is not None:
            current = event.position().toPoint()
            delta = current - self._pan_last_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_last_pos = current
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.RightButton and self._pan_active:
            self._pan_active = False
            self._pan_last_pos = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DraggableSignaturePixmapItem(QGraphicsPixmapItem):
    """Signatur-Hauptobjekt; alle Textlabels hängen als Kinder daran."""

    def __init__(self, pixmap: QPixmap, on_moved, constrain_position=None) -> None:
        super().__init__(pixmap)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._on_moved = on_moved
        self._constrain_position = constrain_position
        self._hit_pad_x = max(6.0, float(pixmap.width()) * 0.5)
        self._hit_pad_y = max(6.0, float(pixmap.height()) * 0.5)

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return super().boundingRect().adjusted(
            -self._hit_pad_x,
            -self._hit_pad_y,
            self._hit_pad_x,
            self._hit_pad_y,
        )

    def shape(self) -> QPainterPath:  # type: ignore[override]
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def itemChange(self, change, value):  # type: ignore[override]
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self._constrain_position is not None
            and isinstance(value, QPointF)
        ):
            return self._constrain_position(value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._on_moved()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        self.setCursor(Qt.CursorShape.CrossCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.unsetCursor()
        super().hoverLeaveEvent(event)
