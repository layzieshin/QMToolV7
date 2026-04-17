from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import cast

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTransform,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput
from modules.signature.layout_math import compute_target_height, resolve_label_pdf_anchor
from .pdf_rendering import get_page_count, pixmap_to_qpixmap, render_page


def compute_label_local_position(
    *,
    position: str,
    sig_height: float,
    pixel_size: int,
    scale: float,
    rel_x: float | None,
    rel_y: float | None,
    offset_above: float,
    offset_below: float,
    x_offset: float,
) -> QPointF:
    pdf_x, pdf_y = resolve_label_pdf_anchor(
        placement_x=0.0,
        placement_y=0.0,
        signature_height=sig_height,
        position=cast("Literal['above', 'below', 'off']", position),
        offset_above=offset_above,
        offset_below=offset_below,
        x_offset=x_offset,
        rel_x=rel_x,
        rel_y=rel_y,
    )
    local_x = pdf_x * scale
    local_y = (sig_height - pdf_y) * scale - float(pixel_size)
    return QPointF(local_x, local_y)


class _ZoomableView(QGraphicsView):
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


class _DraggableSignatureItem(QGraphicsPixmapItem):
    """Signatur-Hauptobjekt; alle Textlabels hängen als Kinder daran."""

    def __init__(self, pixmap: QPixmap, on_moved, constrain_position=None) -> None:
        super().__init__(pixmap)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._on_moved = on_moved
        self._constrain_position = constrain_position
        # 100% larger hitbox: 50% extension per side.
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


class SignaturePlacementDialog(QDialog):
    def __init__(
        self,
        *,
        input_pdf: Path,
        placement: SignaturePlacementInput,
        layout: LabelLayoutInput | None = None,
        signature_pixmap: QPixmap | None = None,
        template_save_callback=None,
        template_list_provider=None,
        template_load_callback=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Platzierungsvorschau")

        self._input_pdf = input_pdf
        self._signature_pixmap = signature_pixmap
        self._layout = layout or LabelLayoutInput()
        self._template_save_callback = template_save_callback
        self._template_list_provider = template_list_provider
        self._template_load_callback = template_load_callback
        self._signature_aspect: float | None = None
        if signature_pixmap is not None and not signature_pixmap.isNull() and signature_pixmap.width() > 0:
            self._signature_aspect = float(signature_pixmap.height()) / float(signature_pixmap.width())
        self._current_scale: float = 1.0
        self._pix_width: float = 0.0
        self._pix_height: float = 0.0
        self._target_height: float = 0.0
        self._sig_scene_w: float = 0.0
        self._sig_scene_h: float = 0.0
        self._pdf_page_width: float = 0.0
        self._pdf_page_height: float = 0.0
        self._sig_item: _DraggableSignatureItem | None = None
        self._fit_scale: float = 0.0
        self._updating_from_drag = False
        self._updating_from_render = False
        self._options_visible = False

        self._page = QSpinBox()
        page_count = self._read_page_count(input_pdf)
        self._page.setMinimum(0)
        self._page.setMaximum(max(0, page_count - 1))
        self._page.setValue(min(max(0, placement.page_index), max(0, page_count - 1)))
        self._page.setFixedWidth(70)

        self._x = QLineEdit(str(placement.x))
        self._y = QLineEdit(str(placement.y))
        self._width = QLineEdit(str(placement.target_width))
        for widget in (self._x, self._y, self._width):
            widget.setFixedWidth(80)

        self._render_error = QLabel("")
        self._render_error.setWordWrap(True)

        self._scene = QGraphicsScene(self)
        self._view = _ZoomableView(self)
        self._view.setScene(self._scene)
        self._view.setMinimumSize(860, 620)
        self._view.setBackgroundBrush(QBrush(QColor("#e6e6e6")))

        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(25, 500)
        self._zoom_slider.setValue(100)
        self._zoom_slider.setFixedWidth(160)
        self._zoom_pct = QLabel("100%")
        self._zoom_pct.setFixedWidth(48)
        self._view._zoom_slider = self._zoom_slider
        self._view._click_callback = self._place_signature_at_scene_pos

        btn_fit = QPushButton("Einpassen")
        btn_fit.clicked.connect(self._fit_view)

        zoom_bar = QHBoxLayout()
        zoom_bar.setSpacing(6)
        zoom_bar.addWidget(QLabel("Zoom:"))
        zoom_bar.addWidget(self._zoom_slider)
        zoom_bar.addWidget(self._zoom_pct)
        zoom_bar.addWidget(btn_fit)
        zoom_bar.addStretch(1)

        self._options_panel = self._build_options_panel()
        self._options_panel.setVisible(False)

        self._toggle_btn = QPushButton("▶")
        self._toggle_btn.setFixedWidth(26)
        self._toggle_btn.setToolTip("Optionen ein-/ausblenden")
        self._toggle_btn.clicked.connect(self._toggle_options)

        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        left_layout.addWidget(self._view, stretch=1)
        left_layout.addLayout(zoom_bar)
        left_widget = QWidget()
        left_widget.setLayout(left_layout)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(4)
        content_row.addWidget(left_widget, stretch=1)
        content_row.addWidget(self._toggle_btn)
        content_row.addWidget(self._options_panel)

        hint = QLabel(
            "Ctrl+Scroll = Zoom • Doppelklick in die Seite = Signaturblock platzieren • Ziehen = Signatur, Name und Datum gemeinsam verschieben"
        )
        hint.setWordWrap(True)

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 8, 8, 8)
        main.setSpacing(6)
        main.addWidget(QLabel(f"📄 {input_pdf.name}"))
        main.addWidget(self._render_error)
        main.addLayout(content_row, stretch=1)
        main.addWidget(hint)
        main.addWidget(buttons)

        self._zoom_slider.valueChanged.connect(self._on_zoom_slider)
        self._page.valueChanged.connect(lambda _v: self._render_page_with_overlay())
        for widget in (self._x, self._y, self._width):
            widget.textChanged.connect(lambda _v: self._on_text_changed())

        self._populate_options_from_layout(self._layout)
        self._render_page_with_overlay()

    def _build_options_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(320)

        self._save_template_name = QLineEdit()
        self._save_template_name.setPlaceholderText("Vorlagenname")
        btn_save_template = QPushButton("Signaturposition als Vorlage speichern")
        btn_save_template.clicked.connect(self._save_template)
        self._template_select = QComboBox()
        self._template_select.addItem("Preset auswaehlen", "")
        btn_load_template = QPushButton("Preset laden")
        btn_load_template.clicked.connect(self._apply_selected_template)
        self._reload_templates()

        self._opt_show_name = QCheckBox("Name anzeigen")
        self._opt_name_pos = QComboBox()
        self._opt_name_pos.addItems(["above", "below", "off"])
        self._opt_name_font_size = QLineEdit("12")
        self._opt_name_font_size.setFixedWidth(52)
        self._opt_name_rel_x = QLineEdit()
        self._opt_name_rel_x.setPlaceholderText("auto")
        self._opt_name_rel_x.setFixedWidth(60)
        self._opt_name_rel_x_slider = QSlider(Qt.Orientation.Horizontal)
        self._opt_name_rel_x_slider.setRange(-300, 300)
        self._opt_name_rel_x_slider.setFixedWidth(120)
        self._opt_name_rel_y = QLineEdit()
        self._opt_name_rel_y.setPlaceholderText("auto")
        self._opt_name_rel_y.setFixedWidth(60)
        self._opt_name_rel_y_slider = QSlider(Qt.Orientation.Horizontal)
        self._opt_name_rel_y_slider.setRange(-300, 300)
        self._opt_name_rel_y_slider.setFixedWidth(120)

        self._opt_show_date = QCheckBox("Datum anzeigen")
        self._opt_date_pos = QComboBox()
        self._opt_date_pos.addItems(["above", "below", "off"])
        self._opt_date_font_size = QLineEdit("12")
        self._opt_date_font_size.setFixedWidth(52)
        self._opt_date_rel_x = QLineEdit()
        self._opt_date_rel_x.setPlaceholderText("auto")
        self._opt_date_rel_x.setFixedWidth(60)
        self._opt_date_rel_x_slider = QSlider(Qt.Orientation.Horizontal)
        self._opt_date_rel_x_slider.setRange(-300, 300)
        self._opt_date_rel_x_slider.setFixedWidth(120)
        self._opt_date_rel_y = QLineEdit()
        self._opt_date_rel_y.setPlaceholderText("auto")
        self._opt_date_rel_y.setFixedWidth(60)
        self._opt_date_rel_y_slider = QSlider(Qt.Orientation.Horizontal)
        self._opt_date_rel_y_slider.setRange(-300, 300)
        self._opt_date_rel_y_slider.setFixedWidth(120)

        self._opt_color_hex = QLineEdit("#000000")
        self._opt_color_hex.setFixedWidth(90)
        btn_color = QPushButton("…")
        btn_color.setFixedWidth(30)
        btn_color.clicked.connect(self._pick_color)

        btn_update = QPushButton("Vorschau aktualisieren")
        btn_update.clicked.connect(self._render_page_with_overlay)

        form = QFormLayout(panel)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(4)

        form.addRow(QLabel("── Signatur ──"))
        form.addRow("Seite", self._page)
        form.addRow("X", self._x)
        form.addRow("Y", self._y)
        form.addRow("Breite", self._width)

        form.addRow(QLabel("── Name ──"))
        form.addRow(self._opt_show_name)
        form.addRow("Position", self._opt_name_pos)
        form.addRow("Schriftgröße", self._opt_name_font_size)
        name_values = QHBoxLayout()
        name_values.addWidget(QLabel("X:"))
        name_values.addWidget(self._opt_name_rel_x)
        name_values.addWidget(QLabel("Y:"))
        name_values.addWidget(self._opt_name_rel_y)
        form.addRow("Rel. Pos.", name_values)
        form.addRow("Slider X", self._opt_name_rel_x_slider)
        form.addRow("Slider Y", self._opt_name_rel_y_slider)

        form.addRow(QLabel("── Datum ──"))
        form.addRow(self._opt_show_date)
        form.addRow("Position", self._opt_date_pos)
        form.addRow("Schriftgröße", self._opt_date_font_size)
        date_values = QHBoxLayout()
        date_values.addWidget(QLabel("X:"))
        date_values.addWidget(self._opt_date_rel_x)
        date_values.addWidget(QLabel("Y:"))
        date_values.addWidget(self._opt_date_rel_y)
        form.addRow("Rel. Pos.", date_values)
        form.addRow("Slider X", self._opt_date_rel_x_slider)
        form.addRow("Slider Y", self._opt_date_rel_y_slider)

        form.addRow(QLabel("── Allgemein ──"))
        color_row = QHBoxLayout()
        color_row.addWidget(self._opt_color_hex)
        color_row.addWidget(btn_color)
        form.addRow("Farbe", color_row)
        preset_row = QHBoxLayout()
        preset_row.addWidget(self._template_select)
        preset_row.addWidget(btn_load_template)
        form.addRow("Preset", preset_row)
        form.addRow("Vorlagenname", self._save_template_name)
        form.addRow(btn_save_template)
        form.addRow(btn_update)

        for widget in (self._opt_show_name, self._opt_show_date):
            widget.toggled.connect(lambda _v: self._render_page_with_overlay())
        for widget in (self._opt_name_pos, self._opt_date_pos):
            widget.currentTextChanged.connect(lambda _v: self._render_page_with_overlay())
        for widget in (
            self._opt_name_font_size,
            self._opt_date_font_size,
            self._opt_name_rel_x,
            self._opt_name_rel_y,
            self._opt_date_rel_x,
            self._opt_date_rel_y,
            self._opt_color_hex,
        ):
            widget.textChanged.connect(lambda _v: self._render_page_with_overlay())
        self._bind_rel_slider(self._opt_name_rel_x, self._opt_name_rel_x_slider)
        self._bind_rel_slider(self._opt_name_rel_y, self._opt_name_rel_y_slider)
        self._bind_rel_slider(self._opt_date_rel_x, self._opt_date_rel_x_slider)
        self._bind_rel_slider(self._opt_date_rel_y, self._opt_date_rel_y_slider)

        return panel

    def _populate_options_from_layout(self, layout: LabelLayoutInput) -> None:
        self._opt_show_name.setChecked(layout.show_name)
        self._opt_show_date.setChecked(layout.show_date)
        for combo, value in ((self._opt_name_pos, layout.name_position), (self._opt_date_pos, layout.date_position)):
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._opt_name_font_size.setText(str(layout.name_font_size))
        self._opt_date_font_size.setText(str(layout.date_font_size))
        self._opt_color_hex.setText(layout.color_hex or "#000000")
        self._opt_name_rel_x.setText("" if layout.name_rel_x is None else str(layout.name_rel_x))
        self._opt_name_rel_y.setText("" if layout.name_rel_y is None else str(layout.name_rel_y))
        self._opt_date_rel_x.setText("" if layout.date_rel_x is None else str(layout.date_rel_x))
        self._opt_date_rel_y.setText("" if layout.date_rel_y is None else str(layout.date_rel_y))
        self._sync_slider_from_edit(self._opt_name_rel_x, self._opt_name_rel_x_slider)
        self._sync_slider_from_edit(self._opt_name_rel_y, self._opt_name_rel_y_slider)
        self._sync_slider_from_edit(self._opt_date_rel_x, self._opt_date_rel_x_slider)
        self._sync_slider_from_edit(self._opt_date_rel_y, self._opt_date_rel_y_slider)

    def _bind_rel_slider(self, edit: QLineEdit, slider: QSlider) -> None:
        slider.valueChanged.connect(lambda value: self._on_rel_slider_changed(edit, value))
        edit.textChanged.connect(lambda _v: self._sync_slider_from_edit(edit, slider))

    def _on_rel_slider_changed(self, edit: QLineEdit, value: int) -> None:
        edit.blockSignals(True)
        try:
            edit.setText(str(value))
        finally:
            edit.blockSignals(False)
        self._render_page_with_overlay()

    def _sync_slider_from_edit(self, edit: QLineEdit, slider: QSlider) -> None:
        raw = edit.text().strip()
        target = 0 if raw == "" else self._safe_slider_int(raw)
        slider.blockSignals(True)
        try:
            slider.setValue(target)
        finally:
            slider.blockSignals(False)

    @staticmethod
    def _safe_slider_int(raw: str) -> int:
        try:
            return max(-300, min(300, int(float(raw))))
        except Exception:
            return 0

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._opt_color_hex.text()), self)
        if color.isValid():
            self._opt_color_hex.setText(color.name())
            self._render_page_with_overlay()

    def _toggle_options(self) -> None:
        self._options_visible = not self._options_visible
        self._options_panel.setVisible(self._options_visible)
        self._toggle_btn.setText("◀" if self._options_visible else "▶")

    def _save_template(self) -> None:
        if self._template_save_callback is None:
            QMessageBox.information(self, "Vorlage speichern", "Speichern ist in diesem Kontext nicht verfügbar.")
            return
        try:
            self._template_save_callback(
                self._save_template_name.text().strip(),
                self.placement(),
                self.layout_result(),
            )
            QMessageBox.information(
                self,
                "Vorlage gespeichert",
                f"Vorlage '{self._save_template_name.text().strip()}' wurde gespeichert.",
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Vorlage speichern", str(exc))

    def _reload_templates(self) -> None:
        if not callable(self._template_list_provider):
            return
        self._template_select.clear()
        self._template_select.addItem("Preset auswaehlen", "")
        try:
            rows = self._template_list_provider()
            if not isinstance(rows, Iterable):
                return
            for template_id, name in rows:
                self._template_select.addItem(name, template_id)
        except Exception:
            self._template_select.clear()
            self._template_select.addItem("Preset auswaehlen", "")

    def _apply_selected_template(self) -> None:
        template_id = self._template_select.currentData()
        if not isinstance(template_id, str) or not template_id.strip():
            return
        if not callable(self._template_load_callback):
            return
        try:
            result = self._template_load_callback(template_id)
            if not isinstance(result, tuple) or len(result) != 2:
                return
            placement, layout = result
            self._page.setValue(int(placement.page_index))
            self._x.setText(str(placement.x))
            self._y.setText(str(placement.y))
            self._width.setText(str(placement.target_width))
            self._layout = layout
            self._populate_options_from_layout(layout)
            self._render_page_with_overlay()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Preset laden", str(exc))

    def _fit_view(self) -> None:
        if self._pix_width > 0 and self._pix_height > 0:
            self._view.fitInView(
                QRectF(0, 0, self._pix_width, self._pix_height),
                Qt.AspectRatioMode.KeepAspectRatio,
            )
            transform = self._view.transform()
            self._fit_scale = transform.m11() if transform.m11() > 0 else 1.0
            self._zoom_slider.blockSignals(True)
            self._zoom_slider.setValue(100)
            self._zoom_slider.blockSignals(False)
            self._zoom_pct.setText("100%")

    def _on_zoom_slider(self, value: int) -> None:
        self._zoom_pct.setText(f"{value}%")
        if self._fit_scale > 0:
            effective = self._fit_scale * (value / 100.0)
            self._view.setTransform(QTransform().scale(effective, effective))

    def _read_page_count(self, input_pdf: Path) -> int:
        try:
            return max(1, int(get_page_count(input_pdf)))
        except Exception:
            try:
                reader_mod = importlib.import_module("pypdf")
                PdfReader = getattr(reader_mod, "PdfReader")
                return len(PdfReader(str(input_pdf)).pages)
            except Exception:
                return 1

    def _safe_float(self, raw: str, default: float = 0.0) -> float:
        try:
            return float(raw.strip() or str(default))
        except ValueError:
            return default

    def _clamp_pdf_xy(
        self,
        x: float,
        y: float,
        target_width: float,
        target_height: float,
    ) -> tuple[float, float]:
        page_w = self._pdf_page_width if self._pdf_page_width > 0 else (
            self._pix_width / self._current_scale if self._current_scale > 0 else 0.0
        )
        page_h = self._pdf_page_height if self._pdf_page_height > 0 else (
            self._pix_height / self._current_scale if self._current_scale > 0 else 0.0
        )
        max_x = max(0.0, page_w - target_width)
        max_y = max(0.0, page_h - target_height)
        return (max(0.0, min(x, max_x)), max(0.0, min(y, max_y)))

    def _clamp_scene_pos(self, pos: QPointF) -> QPointF:
        max_x = max(0.0, self._pix_width - self._sig_scene_w)
        max_y = max(0.0, self._pix_height - self._sig_scene_h)
        return QPointF(
            max(0.0, min(pos.x(), max_x)),
            max(0.0, min(pos.y(), max_y)),
        )

    def _on_text_changed(self) -> None:
        if self._updating_from_drag:
            return
        self._render_page_with_overlay()

    def _place_signature_at_scene_pos(self, scene_pos: QPointF) -> None:
        if self._current_scale <= 0 or self._pix_width <= 0 or self._pix_height <= 0:
            return
        target_width = max(1.0, self._safe_float(self._width.text(), 120.0))
        target_height = compute_target_height(target_width, signature_aspect=self._signature_aspect)
        pdf_x = (scene_pos.x() / self._current_scale) - (target_width / 2.0)
        pdf_y = ((self._pix_height - scene_pos.y()) / self._current_scale) - (target_height / 2.0)
        pdf_x, pdf_y = self._clamp_pdf_xy(pdf_x, pdf_y, target_width, target_height)
        self._updating_from_drag = True
        try:
            self._x.setText(f"{pdf_x:.1f}")
            self._y.setText(f"{pdf_y:.1f}")
        finally:
            self._updating_from_drag = False
        self._render_page_with_overlay()

    def _on_sig_dragged(self) -> None:
        if self._sig_item is None or self._current_scale == 0 or self._updating_from_render:
            return
        pos = self._sig_item.pos()
        pdf_x = pos.x() / self._current_scale
        pdf_y = (self._pix_height - pos.y()) / self._current_scale - self._target_height
        self._updating_from_drag = True
        try:
            self._x.setText(f"{max(0.0, pdf_x):.1f}")
            self._y.setText(f"{max(0.0, pdf_y):.1f}")
        finally:
            self._updating_from_drag = False

    def _render_page_with_overlay(self) -> None:
        self._updating_from_render = True
        old_zoom = self._zoom_slider.value()
        first_render = self._fit_scale == 0.0

        self._scene.clear()
        self._sig_item = None
        self._render_error.clear()
        try:
            fitz = importlib.import_module("fitz")
            with fitz.open(str(self._input_pdf)) as doc:
                page_index = int(self._page.value())
                if page_index < 0 or page_index >= doc.page_count:
                    raise RuntimeError(f"Ungültiger Seitenindex {page_index}")
                page = doc.load_page(page_index)
                pix = render_page(self._input_pdf, page_index, zoom=1.5)
                pdf_pixmap = pixmap_to_qpixmap(pix)
                self._scene.addPixmap(pdf_pixmap)
                self._scene.addRect(
                    QRectF(0, 0, pix.width, pix.height),
                    QPen(QColor("#7a7a7a"), 2),
                )
                self._scene.setSceneRect(QRectF(0, 0, pix.width, pix.height))
                self._pix_width = float(pix.width)
                self._pix_height = float(pix.height)
                self._pdf_page_width = float(page.rect.width)
                self._pdf_page_height = float(page.rect.height)

                x = self._safe_float(self._x.text(), 0.0)
                y = self._safe_float(self._y.text(), 0.0)
                target_width = max(1.0, self._safe_float(self._width.text(), 120.0))
                target_height = compute_target_height(target_width, signature_aspect=self._signature_aspect)

                page_w = float(page.rect.width)
                scale = pix.width / page_w if page_w > 0 else 1.0
                self._current_scale = scale
                self._target_height = target_height

                clamped_x, clamped_y = self._clamp_pdf_xy(x, y, target_width, target_height)
                if abs(clamped_x - x) > 0.05 or abs(clamped_y - y) > 0.05:
                    self._updating_from_drag = True
                    try:
                        self._x.setText(f"{clamped_x:.1f}")
                        self._y.setText(f"{clamped_y:.1f}")
                    finally:
                        self._updating_from_drag = False
                    self._render_error.setText("Hinweis: Position wurde auf die sichtbare Seitengrenze begrenzt.")
                x, y = clamped_x, clamped_y

                sx = x * scale
                sw = target_width * scale
                sh = target_height * scale
                sy = pix.height - (y + target_height) * scale
                self._sig_scene_w = sw
                self._sig_scene_h = sh

                if self._signature_pixmap is not None and not self._signature_pixmap.isNull():
                    overlay_px = self._signature_pixmap.scaled(
                        max(1, int(sw)),
                        max(1, int(sh)),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                else:
                    overlay_px = QPixmap(max(1, int(sw)), max(1, int(sh)))
                    overlay_px.fill(QColor(255, 255, 255, 0))
                    painter = QPainter(overlay_px)
                    painter.setPen(QPen(QColor("#cc0000"), 2, Qt.PenStyle.DashLine))
                    painter.drawRect(1, 1, max(1, overlay_px.width() - 2), max(1, overlay_px.height() - 2))
                    painter.end()

                overlay_item: _DraggableSignatureItem = _DraggableSignatureItem(
                    overlay_px,
                    self._on_sig_dragged,
                    constrain_position=self._clamp_scene_pos,
                )
                self._sig_item = overlay_item
                overlay_item.setPos(QPointF(sx, sy))
                self._scene.addItem(overlay_item)

                color = QColor(self._opt_color_hex.text())
                if not color.isValid():
                    color = QColor("black")

                if self._opt_show_name.isChecked() and self._opt_name_pos.currentText() != "off":
                    self._add_text_item(
                        text_parent=overlay_item,
                        text=(self._layout.name_text or "").strip(),
                        placement_x=x,
                        placement_y=y,
                        target_h=target_height,
                        pix_h=float(pix.height),
                        position=self._opt_name_pos.currentText(),
                        font_size_pt=max(6, int(self._opt_name_font_size.text() or "12")),
                        color=color,
                        scale=scale,
                        rel_x_raw=self._opt_name_rel_x.text().strip(),
                        rel_y_raw=self._opt_name_rel_y.text().strip(),
                        offset_above=self._layout.name_above,
                        offset_below=self._layout.name_below,
                        x_offset=self._layout.x_offset,
                    )

                if self._opt_show_date.isChecked() and self._opt_date_pos.currentText() != "off":
                    self._add_text_item(
                        text_parent=overlay_item,
                        text=(self._layout.date_text or "").strip(),
                        placement_x=x,
                        placement_y=y,
                        target_h=target_height,
                        pix_h=float(pix.height),
                        position=self._opt_date_pos.currentText(),
                        font_size_pt=max(6, int(self._opt_date_font_size.text() or "12")),
                        color=color,
                        scale=scale,
                        rel_x_raw=self._opt_date_rel_x.text().strip(),
                        rel_y_raw=self._opt_date_rel_y.text().strip(),
                        offset_above=self._layout.date_above,
                        offset_below=self._layout.date_below,
                        x_offset=self._layout.x_offset,
                    )

                if first_render:
                    self._fit_view()
                else:
                    effective = self._fit_scale * (old_zoom / 100.0)
                    self._view.setTransform(QTransform().scale(effective, effective))

        except Exception as exc:  # noqa: BLE001
            self._render_error.setText(f"Vorschau nicht verfügbar: {exc}")
        finally:
            self._updating_from_render = False

    def _add_text_item(
        self,
        *,
        text_parent: _DraggableSignatureItem,
        text: str,
        placement_x: float,
        placement_y: float,
        target_h: float,
        pix_h: float,
        position: str,
        font_size_pt: int,
        color: QColor,
        scale: float,
        rel_x_raw: str,
        rel_y_raw: str,
        offset_above: float,
        offset_below: float,
        x_offset: float,
    ) -> None:
        if not text:
            return
        item = QGraphicsSimpleTextItem(text, text_parent)
        pixel_size = max(6, int(font_size_pt * scale * 0.85))
        font = QFont()
        font.setPixelSize(pixel_size)
        item.setFont(font)
        item.setBrush(QBrush(color))

        rel_x: float | None = None
        rel_y: float | None = None
        if rel_x_raw:
            try:
                rel_x = float(rel_x_raw)
            except ValueError:
                rel_x = None
        if rel_y_raw:
            try:
                rel_y = float(rel_y_raw)
            except ValueError:
                rel_y = None

        pdf_x, pdf_y = resolve_label_pdf_anchor(
            placement_x=placement_x,
            placement_y=placement_y,
            signature_height=target_h,
            position=cast("Literal['above', 'below', 'off']", position),
            offset_above=offset_above,
            offset_below=offset_below,
            x_offset=x_offset,
            rel_x=rel_x,
            rel_y=rel_y,
        )
        scene_x = pdf_x * scale
        baseline_scene_y = pix_h - (pdf_y * scale)
        scene_y = baseline_scene_y - pixel_size
        item.setPos(QPointF(scene_x - text_parent.pos().x(), scene_y - text_parent.pos().y()))

    def placement(self) -> SignaturePlacementInput:
        width = self._safe_float(self._width.text(), 120.0)
        height = compute_target_height(width, signature_aspect=self._signature_aspect)
        x, y = self._clamp_pdf_xy(
            self._safe_float(self._x.text(), 0.0),
            self._safe_float(self._y.text(), 0.0),
            width,
            height,
        )
        return SignaturePlacementInput(
            page_index=int(self._page.value()),
            x=x,
            y=y,
            target_width=width,
        )

    def layout_result(self) -> LabelLayoutInput:
        def _float_or_none(raw: str) -> float | None:
            value = raw.strip()
            return float(value) if value else None

        return LabelLayoutInput(
            show_signature=self._layout.show_signature,
            show_name=self._opt_show_name.isChecked(),
            show_date=self._opt_show_date.isChecked(),
            name_text=self._layout.name_text,
            date_text=self._layout.date_text,
            name_position=self._opt_name_pos.currentText(),  # type: ignore[arg-type]
            date_position=self._opt_date_pos.currentText(),  # type: ignore[arg-type]
            name_font_size=max(6, int(self._opt_name_font_size.text() or "12")),
            date_font_size=max(6, int(self._opt_date_font_size.text() or "12")),
            color_hex=self._opt_color_hex.text() or "#000000",
            name_above=self._layout.name_above,
            name_below=self._layout.name_below,
            date_above=self._layout.date_above,
            date_below=self._layout.date_below,
            x_offset=self._layout.x_offset,
            name_rel_x=_float_or_none(self._opt_name_rel_x.text()),
            name_rel_y=_float_or_none(self._opt_name_rel_y.text()),
            date_rel_x=_float_or_none(self._opt_date_rel_x.text()),
            date_rel_y=_float_or_none(self._opt_date_rel_y.text()),
        )
