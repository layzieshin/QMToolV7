"""Main window for the internal license issuer GUI."""
from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from qm_platform.runtime import bootstrap as runtime_bootstrap

from tools.internal_license_issuer.issuer import _load_private_key
from tools.internal_license_issuer.service import IssueLicenseRequest, issue_license, verify_signed_payload
from tools.internal_license_issuer.validators import suggest_next_customer_id
from tools.license_issuer_gui.presets import PRESETS, preset_by_id
from tools.license_issuer_gui.settings_store import IssuerSettings


class LicenseIssuerMainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._settings = IssuerSettings.load()
        self._module_checks: dict[str, QCheckBox] = {}
        self._known_tags = runtime_bootstrap.core_license_tags()
        self._build_ui()
        self._load_settings_into_form()
        self._apply_preset(self._settings.last_preset_id or "trial_30")

    def _build_ui(self) -> None:
        self.setWindowTitle("QM-Tool License Issuer (intern)")
        self.setMinimumWidth(640)
        root = QVBoxLayout(self)

        settings_box = QGroupBox("Einstellungen")
        settings_form = QFormLayout(settings_box)
        self._private_key = QLineEdit()
        browse_key = QPushButton("Private Key …")
        browse_key.clicked.connect(self._browse_private_key)
        test_key = QPushButton("Key testen")
        test_key.clicked.connect(self._test_private_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self._private_key, 1)
        key_row.addWidget(browse_key)
        key_row.addWidget(test_key)
        settings_form.addRow("Private Key PEM", key_row)

        self._output_dir = QLineEdit()
        browse_out = QPushButton("Ordner …")
        browse_out.clicked.connect(self._browse_output_dir)
        out_row = QHBoxLayout()
        out_row.addWidget(self._output_dir, 1)
        out_row.addWidget(browse_out)
        settings_form.addRow("Ausgabeordner", out_row)
        root.addWidget(settings_box)

        issue_box = QGroupBox("Neue Lizenz")
        issue_form = QFormLayout(issue_box)
        self._preset = QComboBox()
        for preset in PRESETS:
            self._preset.addItem(preset.label, preset.preset_id)
        self._preset.currentIndexChanged.connect(self._on_preset_changed)
        issue_form.addRow("Vorlage", self._preset)

        self._issued_to = QLineEdit()
        self._customer_id = QLineEdit()
        self._machine_id = QLineEdit()
        paste_machine = QPushButton("Aus Zwischenablage")
        paste_machine.clicked.connect(self._paste_machine_id)
        machine_row = QHBoxLayout()
        machine_row.addWidget(self._machine_id, 1)
        machine_row.addWidget(paste_machine)
        issue_form.addRow("Ausgestellt an", self._issued_to)
        issue_form.addRow("Kunden-ID", self._customer_id)
        issue_form.addRow("Maschinen-ID", machine_row)
        issue_form.addRow(
            "",
            QLabel("Kunde kopiert die ID unter QM-Tool → Einstellungen → Lizenzverwaltung."),
        )

        modules_box = QWidget()
        modules_layout = QVBoxLayout(modules_box)
        modules_layout.setContentsMargins(0, 0, 0, 0)
        for tag in self._known_tags:
            check = QCheckBox(tag)
            check.setChecked(True)
            self._module_checks[tag] = check
            modules_layout.addWidget(check)
        issue_form.addRow("Module", modules_box)

        self._expires_at = QLineEdit()
        issue_form.addRow("Ablauf (Trial, ISO UTC)", self._expires_at)

        advanced_box = QGroupBox("Erweitert")
        advanced_box.setCheckable(True)
        advanced_box.setChecked(False)
        advanced_form = QFormLayout(advanced_box)
        self._license_id = QLineEdit()
        self._key_id = QLineEdit("prod-key")
        advanced_form.addRow("License ID (optional)", self._license_id)
        advanced_form.addRow("Key ID", self._key_id)
        issue_form.addRow(advanced_box)

        btn_row = QHBoxLayout()
        preview_btn = QPushButton("Vorschau JSON")
        preview_btn.clicked.connect(self._preview_json)
        create_btn = QPushButton("Lizenz erstellen")
        create_btn.clicked.connect(self._create_license)
        copy_btn = QPushButton("Code kopieren")
        copy_btn.clicked.connect(self._copy_code)
        btn_row.addWidget(preview_btn)
        btn_row.addWidget(create_btn)
        btn_row.addWidget(copy_btn)
        issue_form.addRow(btn_row)

        self._result = QPlainTextEdit()
        self._result.setReadOnly(True)
        self._result.setMaximumHeight(120)
        issue_form.addRow("Ergebnis", self._result)
        root.addWidget(issue_box)

        save_settings = QPushButton("Einstellungen speichern")
        save_settings.clicked.connect(self._save_settings)
        root.addWidget(save_settings)

        self._last_code = ""

    def _load_settings_into_form(self) -> None:
        self._private_key.setText(self._settings.private_key_pem)
        self._output_dir.setText(self._settings.output_dir)
        self._issued_to.setText(self._settings.last_issued_to)
        suggested = suggest_next_customer_id(self._settings.last_customer_id or None)
        self._customer_id.setText(suggested)

    def _selected_modules(self) -> list[str]:
        return sorted(tag for tag, check in self._module_checks.items() if check.isChecked())

    def _license_type_from_form(self) -> str:
        preset = preset_by_id(str(self._preset.currentData()))
        if preset and preset.license_type:
            return preset.license_type
        return "trial"

    def _build_request(self, *, output_dir: Path | None) -> IssueLicenseRequest:
        private_path = Path(self._private_key.text().strip())
        env_key = os.environ.get("QMT_LICENSE_ISSUER_KEY", "").strip()
        if not private_path.is_file() and env_key:
            private_path = Path(env_key)
        license_type = self._license_type_from_form()
        expires = self._expires_at.text().strip() or None
        if license_type == "full":
            expires = None
        license_id = self._license_id.text().strip() or None
        return IssueLicenseRequest(
            license_type=license_type,
            customer_id=self._customer_id.text().strip(),
            issued_to=self._issued_to.text().strip(),
            machine_id=self._machine_id.text().strip(),
            enabled_modules=self._selected_modules(),
            private_key_pem=private_path,
            key_id=self._key_id.text().strip() or "prod-key",
            license_id=license_id,
            expires_at=expires,
            output_dir=output_dir,
            known_module_tags=set(self._known_tags),
        )

    def _browse_private_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Private Key PEM", "", "PEM (*.pem);;All (*)")
        if path:
            self._private_key.setText(path)

    def _browse_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Ausgabeordner")
        if path:
            self._output_dir.setText(path)

    def _paste_machine_id(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if text:
            self._machine_id.setText(text.split()[0])

    def _test_private_key(self) -> None:
        try:
            path = Path(self._private_key.text().strip() or os.environ.get("QMT_LICENSE_ISSUER_KEY", ""))
            key = _load_private_key(path)
            public_pem = key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii")
            dummy = issue_license(
                IssueLicenseRequest(
                    license_type="full",
                    customer_id="KEY-TEST",
                    issued_to="Key Test",
                    machine_id="qmt-0123456789abcdef",
                    enabled_modules=[self._known_tags[0]],
                    private_key_pem=path,
                    key_id=self._key_id.text().strip() or "prod-key",
                    known_module_tags=set(self._known_tags),
                )
            )
            if not verify_signed_payload(dummy.payload, public_key_pem=public_pem):
                raise RuntimeError("verify failed")
            QMessageBox.information(self, "Key Test", "Private Key ist gültig und Signatur/Verify OK.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Key Test", f"Key-Test fehlgeschlagen:\n{exc}")

    def _on_preset_changed(self) -> None:
        preset_id = str(self._preset.currentData())
        self._apply_preset(preset_id)

    def _apply_preset(self, preset_id: str) -> None:
        preset = preset_by_id(preset_id)
        if preset is None:
            return
        if preset.expires_at is not None:
            self._expires_at.setText(preset.expires_at)
        elif preset.license_type == "full":
            self._expires_at.clear()
        if preset.enabled_modules is not None:
            for tag, check in self._module_checks.items():
                check.setChecked(tag in preset.enabled_modules)

    def _preview_json(self) -> None:
        try:
            result = issue_license(self._build_request(output_dir=None))
            self._last_code = result.license_code
            self._result.setPlainText(json.dumps(result.payload, indent=2, ensure_ascii=True))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Vorschau", str(exc))

    def _create_license(self) -> None:
        try:
            out_dir = Path(self._output_dir.text().strip()) if self._output_dir.text().strip() else None
            if out_dir is None:
                raise ValueError("Ausgabeordner ist erforderlich")
            result = issue_license(self._build_request(output_dir=out_dir))
            self._last_code = result.license_code
            lines = [
                f"JSON: {result.license_json_path}",
                f"Code: {result.license_code_path}",
            ]
            self._result.setPlainText("\n".join(lines))
            self._settings.last_customer_id = self._customer_id.text().strip()
            self._settings.last_issued_to = self._issued_to.text().strip()
            self._settings.last_preset_id = str(self._preset.currentData())
            self._settings.append_issue_log(
                {
                    "customer_id": result.payload.get("customer_id"),
                    "machine_id": result.payload.get("machine_id"),
                    "license_id": result.payload.get("license_id"),
                    "enabled_modules": result.payload.get("enabled_modules"),
                    "license_json": str(result.license_json_path),
                }
            )
            self._save_settings()
            QMessageBox.information(self, "Lizenz erstellt", "\n".join(lines))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Fehler", str(exc))

    def _copy_code(self) -> None:
        if not self._last_code:
            try:
                result = issue_license(self._build_request(output_dir=None))
                self._last_code = result.license_code
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "Code", str(exc))
                return
        QGuiApplication.clipboard().setText(self._last_code)
        self._result.setPlainText("Lizenzcode in Zwischenablage kopiert.")

    def _save_settings(self) -> None:
        self._settings.private_key_pem = self._private_key.text().strip()
        self._settings.output_dir = self._output_dir.text().strip()
        path = self._settings.save()
        self._result.appendPlainText(f"\nEinstellungen gespeichert: {path}")


def run_app() -> int:
    app = QApplication([])
    window = LicenseIssuerMainWindow()
    window.show()
    return int(app.exec())
