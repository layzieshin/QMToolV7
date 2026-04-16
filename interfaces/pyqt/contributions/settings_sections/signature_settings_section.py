"""Signature Settings section (extracted from settings_view.py)."""
from __future__ import annotations

import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap

from interfaces.pyqt.contributions.common import as_json_text, normalize_role
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from interfaces.pyqt.widgets.signature_canvas_dialog import SignatureCanvasDialog
from interfaces.pyqt.widgets.signature_placement_dialog import SignaturePlacementDialog, compute_label_local_position
from modules.signature.contracts import LabelLayoutInput, SignaturePlacementInput
from qm_platform.runtime.container import RuntimeContainer


class SignatureSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._settings = container.get_port("settings_service")
        self._signature = container.get_port("signature_api")
        self._um = container.get_port("usermanagement_service")
        current_user = self._um.get_current_user()
        self._is_admin = normalize_role(current_user.role) == "ADMIN" if current_user is not None else False
        self._profiles_cache: dict[str, object] = {}
        self._current_profile_placement = SignaturePlacementInput(page_index=0, x=100.0, y=100.0, target_width=120.0)
        self._current_profile_layout = LabelLayoutInput()

        self._require_password = QCheckBox("Passwort für Signaturvorgänge erforderlich")
        self._default_mode = QComboBox()
        self._default_mode.addItems(["visual", "crypto", "both"])
        self._dry_run_off = QRadioButton("Scharf signieren (empfohlen — echte Signatur)")
        self._dry_run_on = QRadioButton("Testmodus aktiv (Dry-Run — keine echte Signatur erzeugt)")
        self._dry_run_off.setChecked(True)
        self._dry_run_group = QButtonGroup(self)
        self._dry_run_group.addButton(self._dry_run_off, 0)
        self._dry_run_group.addButton(self._dry_run_on, 1)
        self._templates_db = QLineEdit()
        self._assets_root = QLineEdit()
        self._master_key = QLineEdit()

        self._profile_name = QLineEdit("standard")
        self._profile_select = QComboBox()
        self._profiles_table = QTableWidget(0, 4)
        self._profiles_table.setHorizontalHeaderLabels(["Profil", "Seite", "Position", "Layout"])
        self._profiles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._profiles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._profiles_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._profiles_table.setAlternatingRowColors(True)
        self._profiles_table.setSortingEnabled(True)
        self._profiles_table.horizontalHeader().setStretchLastSection(True)
        self._active_asset = QLineEdit()
        self._active_asset.setReadOnly(True)
        self._replace_password = QLineEdit()
        self._replace_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._global_profile_select = QComboBox()
        self._global_profile_name = QLineEdit("global-standard")

        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview_canvas = QLabel()
        self._preview_canvas.setMinimumHeight(220)
        self._preview_sig_pixmap: QPixmap | None = None
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        self._global_settings_box = QWidget()
        global_box_layout = QVBoxLayout(self._global_settings_box)
        global_box_layout.setContentsMargins(0, 0, 0, 0)
        global_box_layout.addWidget(QLabel("Signatur-Einstellungen (global)"))
        global_form = QFormLayout()
        global_form.addRow("", self._require_password)
        global_form.addRow("Default-Modus", self._default_mode)
        global_form.addRow("Signiermodus", self._dry_run_off)
        global_form.addRow("", self._dry_run_on)
        global_form.addRow("templates_db_path", self._templates_db)
        global_form.addRow("assets_root", self._assets_root)
        global_form.addRow("master_key_path", self._master_key)
        global_box_layout.addLayout(global_form)
        global_btn = QHBoxLayout()
        btn_reload = QPushButton("Signatur-Settings laden")
        btn_reload.clicked.connect(self._load_settings)
        btn_save = QPushButton("Signatur-Settings speichern")
        btn_save.clicked.connect(self._save_settings)
        global_btn.addWidget(btn_reload)
        global_btn.addWidget(btn_save)
        global_btn.addStretch(1)
        global_box_layout.addLayout(global_btn)
        layout.addWidget(self._global_settings_box)

        layout.addWidget(QLabel("Signaturprofile"))
        profile_form = QFormLayout()
        profile_form.addRow("Profil wählen", self._profile_select)
        profile_form.addRow("Neuer Profilname", self._profile_name)
        profile_form.addRow("Aktive Asset-ID", self._active_asset)
        profile_form.addRow("Passwort (ersetzen/löschen)", self._replace_password)
        layout.addLayout(profile_form)
        layout.addWidget(self._profiles_table)
        profile_btn = QHBoxLayout()
        btn_create = QPushButton("Profil anlegen")
        btn_create.clicked.connect(self._create_profile_via_editor)
        btn_edit = QPushButton("Profil im Editor bearbeiten")
        btn_edit.clicked.connect(self._edit_profile_via_editor)
        btn_canvas = QPushButton("Signatur zeichnen")
        btn_canvas.clicked.connect(self._open_canvas)
        btn_import = QPushButton("Signatur importieren")
        btn_import.clicked.connect(self._import_and_set_active_signature)
        btn_delete = QPushButton("Profil löschen")
        btn_delete.clicked.connect(self._delete_profile)
        btn_clear_active = QPushButton("Aktive Signatur löschen")
        btn_clear_active.clicked.connect(self._clear_active_signature)
        profile_btn.addWidget(btn_create)
        profile_btn.addWidget(btn_edit)
        profile_btn.addWidget(btn_canvas)
        profile_btn.addWidget(btn_import)
        profile_btn.addWidget(btn_delete)
        profile_btn.addWidget(btn_clear_active)
        profile_btn.addStretch(1)
        layout.addLayout(profile_btn)

        self._global_templates_box = QWidget()
        global_tpl_layout = QVBoxLayout(self._global_templates_box)
        global_tpl_layout.setContentsMargins(0, 0, 0, 0)
        global_tpl_layout.addWidget(QLabel("Globale Templates (Admin)"))
        global_form = QFormLayout()
        global_form.addRow("Global wählen", self._global_profile_select)
        global_form.addRow("Neuer globaler Name", self._global_profile_name)
        global_tpl_layout.addLayout(global_form)
        global_btn = QHBoxLayout()
        btn_global_load = QPushButton("Globale laden")
        btn_global_load.clicked.connect(self._load_global_profiles)
        btn_global_create = QPushButton("Global anlegen")
        btn_global_create.clicked.connect(self._create_global_profile)
        btn_global_delete = QPushButton("Global löschen")
        btn_global_delete.clicked.connect(self._delete_global_profile)
        btn_global_copy = QPushButton("Global -> User kopieren")
        btn_global_copy.clicked.connect(self._copy_global_to_user)
        global_btn.addWidget(btn_global_load)
        global_btn.addWidget(btn_global_create)
        global_btn.addWidget(btn_global_delete)
        global_btn.addWidget(btn_global_copy)
        global_btn.addStretch(1)
        global_tpl_layout.addLayout(global_btn)
        layout.addWidget(self._global_templates_box)

        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self._preview_canvas)
        layout.addWidget(self._preview, stretch=1)
        self._debug_box = QWidget()
        debug_layout = QVBoxLayout(self._debug_box)
        debug_layout.setContentsMargins(0, 0, 0, 0)
        debug_layout.addWidget(QLabel("Ergebnis"))
        debug_layout.addWidget(self._out, stretch=1)
        layout.addWidget(self._debug_box)

        self._global_settings_box.setVisible(self._is_admin)
        self._global_templates_box.setVisible(self._is_admin)
        self._debug_box.setVisible(self._is_admin)

        self._profile_select.currentTextChanged.connect(lambda _text: self._apply_selected_profile())
        self._profiles_table.itemSelectionChanged.connect(self._on_profile_table_select)
        self._load_settings()
        self._load_profiles()
        if self._is_admin:
            self._load_global_profiles()
        self._refresh_active_signature()

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _load_settings(self) -> None:
        if not self._is_admin:
            return
        cfg = self._settings.get_module_settings("signature")
        self._require_password.setChecked(bool(cfg.get("require_password", True)))
        mode = str(cfg.get("default_mode", "visual"))
        idx = self._default_mode.findText(mode)
        if idx >= 0:
            self._default_mode.setCurrentIndex(idx)
        self._templates_db.setText(str(cfg.get("templates_db_path", "")))
        self._assets_root.setText(str(cfg.get("assets_root", "")))
        self._master_key.setText(str(cfg.get("master_key_path", "")))
        dry_run = bool(cfg.get("dry_run_enabled", False))
        self._dry_run_on.setChecked(dry_run)
        self._dry_run_off.setChecked(not dry_run)
        self._append("SIGNATUR_SETTINGS_GELADEN", cfg)

    def _save_settings(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Signatur-Einstellungen ändern.")
            self._require_privileged()
            payload = {
                "require_password": self._require_password.isChecked(),
                "default_mode": self._default_mode.currentText(),
                "dry_run_enabled": self._dry_run_on.isChecked(),
                "templates_db_path": self._templates_db.text().strip(),
                "assets_root": self._assets_root.text().strip(),
                "master_key_path": self._master_key.text().strip(),
            }
            self._settings.set_module_settings("signature", payload, acknowledge_governance_change=True)
            self._append("SIGNATUR_SETTINGS_GESPEICHERT", payload)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur-Einstellungen", str(exc))

    def _load_profiles(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            profiles = self._signature.list_user_signature_templates(user.user_id)
            self._profiles_cache = {p.template_id: p for p in profiles}
            self._profile_select.clear()
            self._profile_select.addItem("Neues Profil", "")
            for profile in profiles:
                self._profile_select.addItem(profile.name, profile.template_id)
            self._profiles_table.setSortingEnabled(False)
            self._profiles_table.setRowCount(len(profiles))
            for row, profile in enumerate(profiles):
                self._profiles_table.setItem(row, 0, QTableWidgetItem(profile.name))
                self._profiles_table.setItem(row, 1, QTableWidgetItem(str(profile.placement.page_index)))
                self._profiles_table.setItem(
                    row, 2,
                    QTableWidgetItem(f"x={profile.placement.x:.1f}, y={profile.placement.y:.1f}, w={profile.placement.target_width:.1f}"),
                )
                self._profiles_table.setItem(
                    row, 3,
                    QTableWidgetItem(f"Name:{'an' if profile.layout.show_name else 'aus'} | Datum:{'an' if profile.layout.show_date else 'aus'}"),
                )
                self._profiles_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, profile.template_id)
            self._profiles_table.resizeColumnsToContents()
            self._profiles_table.setSortingEnabled(True)
            self._profiles_table.sortItems(0, Qt.SortOrder.AscendingOrder)
            self._append("SIGNATUR_PROFILE_GELADEN", {"count": len(profiles)})
            self._refresh_active_signature()
            self._apply_selected_profile()
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _build_placement(self) -> SignaturePlacementInput:
        return self._current_profile_placement

    def _build_layout(self) -> LabelLayoutInput:
        return self._current_profile_layout

    def _create_profile_via_editor(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            profile_name = self._profile_name.text().strip()
            if not profile_name:
                raise RuntimeError("Bitte zuerst einen Profilnamen eingeben")
            pdf_path, _ = QFileDialog.getOpenFileName(self, "Vorschau-Dokument wählen", "", "PDF (*.pdf)")
            if not pdf_path:
                return
            dialog = SignaturePlacementDialog(
                input_pdf=Path(pdf_path),
                placement=self._current_profile_placement,
                layout=self._runtime_preview_layout(self._current_profile_layout),
                signature_pixmap=self._preview_sig_pixmap,
                parent=self,
            )
            dialog.showFullScreen()
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            self._current_profile_placement = dialog.placement()
            self._current_profile_layout = replace(
                dialog.layout_result(),
                name_text=self._current_profile_layout.name_text,
                date_text=self._current_profile_layout.date_text,
            )
            created = self._signature.create_user_signature_template(
                owner_user_id=user.user_id,
                name=profile_name,
                placement=self._build_placement(),
                layout=self._build_layout(),
                signature_asset_id=self._signature.get_active_signature_asset_id(user.user_id),
                scope="user",
            )
            self._append("SIGNATUR_PROFIL_ANGELEGT", created)
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _edit_profile_via_editor(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            template_id = str(self._profile_select.currentData() or "").strip()
            if not template_id:
                raise RuntimeError("Bitte zuerst ein bestehendes Profil auswählen")
            selected = self._profiles_cache.get(template_id)
            if selected is None:
                raise RuntimeError("Ausgewähltes Profil konnte nicht geladen werden")
            pdf_path, _ = QFileDialog.getOpenFileName(self, "Vorschau-Dokument wählen", "", "PDF (*.pdf)")
            if not pdf_path:
                return
            dialog = SignaturePlacementDialog(
                input_pdf=Path(pdf_path),
                placement=selected.placement,
                layout=self._runtime_preview_layout(selected.layout),
                signature_pixmap=self._preview_sig_pixmap,
                parent=self,
            )
            dialog.showFullScreen()
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            updated_name = self._profile_name.text().strip() or selected.name
            updated_layout = replace(
                dialog.layout_result(),
                name_text=selected.layout.name_text,
                date_text=selected.layout.date_text,
            )
            updated = self._signature.update_signature_template(
                template_id=template_id,
                owner_user_id=user.user_id,
                name=updated_name,
                placement=dialog.placement(),
                layout=updated_layout,
            )
            self._append("SIGNATUR_PROFIL_GEAENDERT", {"template_id": updated.template_id, "name": updated.name})
            self._load_profiles()
            idx = self._profile_select.findData(template_id)
            if idx >= 0:
                self._profile_select.setCurrentIndex(idx)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _delete_profile(self) -> None:
        try:
            template_id = str(self._profile_select.currentData() or "").strip()
            if not template_id:
                raise RuntimeError("Bitte zuerst ein bestehendes Profil auswählen")
            self._signature.delete_signature_template(template_id)
            self._append("SIGNATUR_PROFIL_GELOESCHT", {"template_id": template_id})
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signaturprofil", str(exc))

    def _on_profile_table_select(self) -> None:
        row = self._profiles_table.currentRow()
        if row < 0:
            return
        item = self._profiles_table.item(row, 0)
        if item is None:
            return
        template_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        idx = self._profile_select.findData(template_id)
        if idx >= 0:
            self._profile_select.setCurrentIndex(idx)

    def _apply_selected_profile(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                return
            selected_name = self._profile_select.currentText().strip()
            if not selected_name or selected_name == "Neues Profil":
                self._render_preview()
                return
            selected_id = str(self._profile_select.currentData() or "").strip()
            profiles = self._signature.list_user_signature_templates(user.user_id)
            selected = next((p for p in profiles if p.template_id == selected_id), None)
            if selected is None:
                return
            self._profile_name.setText(selected.name)
            self._current_profile_placement = selected.placement
            self._current_profile_layout = selected.layout
            self._render_preview()
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _render_preview(self) -> None:
        PREVIEW_W, PREVIEW_H = 520, 215
        pixmap = QPixmap(PREVIEW_W, PREVIEW_H)
        pixmap.fill(QColor("#e6e6e6"))
        painter = QPainter(pixmap)

        area_x, area_y = 20, 16
        area_w, area_h = 480, 180
        painter.fillRect(area_x, area_y, area_w, area_h, QColor("white"))
        painter.setPen(QPen(QColor("#7a7a7a"), 2))
        painter.drawRect(area_x, area_y, area_w, area_h)

        placement = self._current_profile_placement
        layout = self._runtime_preview_layout(self._current_profile_layout)

        scale = 1.0
        sig_w = max(1, int(placement.target_width * scale))
        sig_h = max(1, int(max(6.0, placement.target_width * 0.3) * scale))
        max_preview_width = int(area_w * 0.58)
        if sig_w > max_preview_width:
            scale = max_preview_width / max(1, sig_w)
            sig_w = max(1, int(placement.target_width * scale))
            sig_h = max(1, int(max(6.0, placement.target_width * 0.3) * scale))

        sig_x = area_x + max(12, int(area_w * 0.18))
        sig_y = area_y + max(18, int((area_h - sig_h) * 0.48))

        if self._preview_sig_pixmap is not None:
            painter.drawPixmap(sig_x, sig_y, sig_w, sig_h, self._preview_sig_pixmap)
        else:
            painter.fillRect(sig_x, sig_y, sig_w, sig_h, QColor(255, 255, 255, 0))
            painter.setPen(QPen(QColor("#cc0000"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(sig_x, sig_y, max(1, sig_w - 1), max(1, sig_h - 1))

        painter.setPen(QPen(QColor("#aaaaaa"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(sig_x, sig_y, sig_w, sig_h)

        name_pos = layout.name_position
        date_pos = layout.date_position
        name_fs = max(6, int(layout.name_font_size or 12))
        date_fs = max(6, int(layout.date_font_size or 12))
        color = QColor(layout.color_hex or "#000000")
        if not color.isValid():
            color = QColor("black")

        if layout.show_name and name_pos != "off":
            font = QFont()
            name_px = max(6, int(name_fs * scale * 0.85))
            font.setPixelSize(name_px)
            painter.setFont(font)
            painter.setPen(color)
            name_local = compute_label_local_position(
                position=name_pos, sig_height=float(sig_h), pixel_size=name_px, scale=scale,
                rel_x=layout.name_rel_x, rel_y=layout.name_rel_y,
                offset_above=layout.name_above, offset_below=layout.name_below, x_offset=layout.x_offset,
            )
            painter.drawText(int(sig_x + name_local.x()), int(sig_y + name_local.y() + name_px), layout.name_text or "")

        if layout.show_date and date_pos != "off":
            font = QFont()
            date_px = max(6, int(date_fs * scale * 0.85))
            font.setPixelSize(date_px)
            painter.setFont(font)
            painter.setPen(color)
            date_local = compute_label_local_position(
                position=date_pos, sig_height=float(sig_h), pixel_size=date_px, scale=scale,
                rel_x=layout.date_rel_x, rel_y=layout.date_rel_y,
                offset_above=layout.date_above, offset_below=layout.date_below, x_offset=layout.x_offset,
            )
            painter.drawText(int(sig_x + date_local.x()), int(sig_y + date_local.y() + date_px), layout.date_text or "")

        painter.end()
        self._preview_canvas.setPixmap(pixmap)

        self._preview.setPlainText(
            "\n".join([
                f"Profil: {self._profile_name.text().strip() or 'Neu'}",
                f"Gespeicherte Seite: {placement.page_index}",
                f"Gespeicherte Position: x={placement.x}, y={placement.y}",
                f"Signaturbreite: {placement.target_width}",
                f"Name: {'an' if layout.show_name else 'aus'} ({name_pos}, {name_fs}pt)",
                f"Datum: {'an' if layout.show_date else 'aus'} ({date_pos}, {date_fs}pt)",
                f"Name rel: x={layout.name_rel_x if layout.name_rel_x is not None else '-'}, y={layout.name_rel_y if layout.name_rel_y is not None else '-'}",
                f"Datum rel: x={layout.date_rel_x if layout.date_rel_x is not None else '-'}, y={layout.date_rel_y if layout.date_rel_y is not None else '-'}",
            ])
        )

    def _current_user_display_name(self) -> str:
        user = self._um.get_current_user()
        if user is None:
            return ""
        first = (getattr(user, "first_name", None) or "").strip()
        last = (getattr(user, "last_name", None) or "").strip()
        if first and last:
            return f"{first}, {last}"
        if first:
            return first
        if last:
            return last
        return (getattr(user, "display_name", None) or user.username or user.user_id).strip()

    def _runtime_preview_layout(self, layout: LabelLayoutInput) -> LabelLayoutInput:
        return replace(
            layout,
            name_text=self._current_user_display_name() if layout.show_name else layout.name_text,
            date_text=datetime.now().strftime("%Y-%m-%d %H:%M:%S") if layout.show_date else layout.date_text,
        )

    def _open_canvas(self) -> None:
        dialog = SignatureCanvasDialog(self)
        dialog.exec()
        user = self._um.get_current_user()
        if user is not None and dialog.signature_bytes() is not None:
            password = self._replace_password.text().strip() or None
            asset = self._signature.import_signature_asset_bytes_and_set_active(
                user.user_id, dialog.signature_bytes(), filename_hint="settings-canvas.png", password=password,
            )
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_AKTUALISIERT", {"asset_id": asset.asset_id})

    def _import_and_set_active_signature(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            path, _ = QFileDialog.getOpenFileName(self, "Signatur importieren", "", "Images (*.png *.gif)")
            if not path:
                return
            password = self._replace_password.text().strip() or None
            asset = self._signature.import_signature_asset_and_set_active(user.user_id, Path(path), password=password)
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_IMPORTIERT", {"asset_id": asset.asset_id})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur importieren", str(exc))

    def _refresh_active_signature(self) -> None:
        user = self._um.get_current_user()
        if user is None:
            self._active_asset.clear()
            self._preview_sig_pixmap = None
            self._render_preview()
            return
        asset_id = self._signature.get_active_signature_asset_id(user.user_id)
        self._active_asset.setText(asset_id or "-")
        self._preview_sig_pixmap = None
        if asset_id:
            try:
                tmp_path = Path(tempfile.mkdtemp(prefix="qmtool-prev-")) / "sig.png"
                exported = self._signature.export_active_signature(user.user_id, tmp_path)
                if exported.exists():
                    px = QPixmap(str(exported))
                    if not px.isNull():
                        self._preview_sig_pixmap = px
            except Exception:  # noqa: BLE001
                pass
        self._render_preview()

    def _set_active_signature_asset(self) -> None:
        QMessageBox.information(self, "Signatur aktiv", "Diese Aktion ist nicht mehr erforderlich.")

    def _export_active_signature(self) -> None:
        QMessageBox.information(self, "Signatur exportieren", "Diese Aktion wurde aus der Oberfläche entfernt.")

    def _clear_active_signature(self) -> None:
        try:
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            password = self._replace_password.text().strip() or None
            self._signature.clear_active_signature(user.user_id, password=password)
            self._refresh_active_signature()
            self._append("AKTIVE_SIGNATUR_GELOESCHT", {"user_id": user.user_id})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Signatur löschen", str(exc))

    def _load_global_profiles(self) -> None:
        try:
            if not self._is_admin:
                return
            self._global_profile_select.clear()
            self._global_profile_select.addItem("Global wählen", "")
            for profile in self._signature.list_global_signature_templates():
                self._global_profile_select.addItem(profile.name, profile.template_id)
            self._append("GLOBAL_PROFILE_GELADEN", {"count": self._global_profile_select.count() - 1})
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _create_global_profile(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Templates verwalten.")
            self._require_privileged()
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            created = self._signature.create_user_signature_template(
                owner_user_id=user.user_id,
                name=self._global_profile_name.text().strip(),
                placement=self._build_placement(),
                layout=self._build_layout(),
                signature_asset_id=self._active_asset.text().strip() if self._active_asset.text().strip() not in ("", "-") else None,
                scope="global",
            )
            self._append("GLOBAL_PROFIL_ANGELEGT", {"template_id": created.template_id, "name": created.name})
            self._load_global_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil", str(exc))

    def _delete_global_profile(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Templates verwalten.")
            self._require_privileged()
            template_id = self._global_profile_select.currentData()
            if not template_id:
                raise RuntimeError("Bitte globales Profil wählen")
            self._signature.delete_signature_template(str(template_id))
            self._append("GLOBAL_PROFIL_GELOESCHT", {"template_id": template_id})
            self._load_global_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil", str(exc))

    def _copy_global_to_user(self) -> None:
        try:
            if not self._is_admin:
                raise RuntimeError("Nur Admins dürfen globale Templates verwenden.")
            user = self._um.get_current_user()
            if user is None:
                raise RuntimeError("Anmeldung erforderlich")
            template_id = self._global_profile_select.currentData()
            if not template_id:
                raise RuntimeError("Bitte globales Profil wählen")
            copied = self._signature.copy_global_template_to_user(str(template_id), user.user_id)
            self._append("GLOBAL_NACH_USER_KOPIERT", {"template_id": copied.template_id, "name": copied.name})
            self._load_profiles()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Globales Profil kopieren", str(exc))

