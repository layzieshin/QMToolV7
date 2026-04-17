"""Options side panel: templates, name/date layout controls."""
from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QWidget,
)

from modules.signature.contracts import LabelLayoutInput


class SignaturePlacementOptionsMixin:
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
        except Exception:  # noqa: BLE001
            self._log.exception("Reloading signature templates failed")
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
