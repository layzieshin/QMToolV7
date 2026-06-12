"""License Management section (import + status; no license issuing)."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import as_json_text
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from qm_platform.licensing.machine_id import get_machine_id, get_machine_id_source
from qm_platform.runtime import bootstrap as runtime_bootstrap
from qm_platform.runtime.container import RuntimeContainer


class LicenseManagementWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._license = container.get_port("license_service")
        self._um = container.get_port("usermanagement_service")
        self._audit = container.get_port("audit_logger")

        self._machine_id_label = QLabel()
        self._machine_hint = QLabel(
            "Diese Maschinen-ID wird zur Ausstellung der Lizenz benötigt. "
            "Bitte an den Hersteller senden, zusammen mit den gewünschten Modulen."
        )
        self._machine_hint.setWordWrap(True)
        self._status_label = QLabel()
        self._license_path = QLineEdit()
        self._license_code = QPlainTextEdit()
        self._status_table = QTableWidget(0, 4)
        self._status_table.setHorizontalHeaderLabels(["Modul", "Tag", "Status", "Sperrgrund"])
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Lizenzverwaltung: Maschinen-ID anzeigen, Lizenzdatei oder Lizenzcode importieren. "
            "Die App startet auch ohne gültige Lizenz; lizenzpflichtige Module bleiben gesperrt. "
            "Nach Import ist ein Neustart empfohlen, damit alle Module neu geladen werden."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        machine_box = QGroupBox("Maschinen-ID")
        machine_layout = QVBoxLayout(machine_box)
        machine_layout.addWidget(self._machine_hint)
        machine_layout.addWidget(self._machine_id_label)
        copy_row = QHBoxLayout()
        btn_copy = QPushButton("Maschinen-ID kopieren")
        btn_copy.clicked.connect(self._copy_machine_id)
        copy_row.addWidget(btn_copy)
        copy_row.addStretch(1)
        machine_layout.addLayout(copy_row)
        layout.addWidget(machine_box)

        status_box = QGroupBox("Lizenzstatus")
        status_form = QFormLayout(status_box)
        status_form.addRow("Status", self._status_label)
        layout.addWidget(status_box)

        file_box = QGroupBox("Lizenzdatei importieren")
        file_layout = QVBoxLayout(file_box)
        form = QFormLayout()
        form.addRow("Zieldatei", self._license_path)
        file_layout.addLayout(form)
        file_actions = QHBoxLayout()
        btn_browse = QPushButton("Datei wählen…")
        btn_browse.clicked.connect(self._browse_license_file)
        btn_import_file = QPushButton("Datei importieren")
        btn_import_file.clicked.connect(self._import_license_file)
        file_actions.addWidget(btn_browse)
        file_actions.addWidget(btn_import_file)
        file_actions.addStretch(1)
        file_layout.addLayout(file_actions)
        layout.addWidget(file_box)

        code_box = QGroupBox("Lizenzcode importieren")
        code_layout = QVBoxLayout(code_box)
        code_layout.addWidget(QLabel("Lizenzcode (Format QMT1.…):"))
        self._license_code.setMaximumHeight(100)
        code_layout.addWidget(self._license_code)
        btn_import_code = QPushButton("Code importieren")
        btn_import_code.clicked.connect(self._import_license_code)
        code_layout.addWidget(btn_import_code)
        layout.addWidget(code_box)

        layout.addWidget(QLabel("Modulstatus"))
        layout.addWidget(self._status_table, stretch=1)
        layout.addWidget(self._out, stretch=1)

        self._refresh_machine_id()
        self._license_path.setText(str(self._license.license_file))
        self._render_status()

    def _refresh_machine_id(self) -> None:
        mid = get_machine_id()
        source = get_machine_id_source()
        self._machine_id_label.setText(f"{mid}  (Quelle: {source})")

    def _copy_machine_id(self) -> None:
        QGuiApplication.clipboard().setText(get_machine_id())
        self._append("MASCHINEN_ID_KOPIERT", {"machine_id": get_machine_id()})

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _browse_license_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Lizenzdatei wählen", "", "JSON (*.json);;Alle Dateien (*)")
        if path:
            self._license_path.setText(path)

    def _import_license_file(self) -> None:
        try:
            self._require_privileged()
            source = Path(self._license_path.text().strip() or self._license.license_file)
            if source == self._license.license_file and source.exists():
                payload = self._license.reload()
            else:
                payload = self._license.import_file(source)
            self._audit.emit(
                action="license.import.file",
                actor="gui-admin",
                target=str(self._license.license_file),
                result="ok",
            )
            self._append("LIZENZ_IMPORTIERT", {"source": str(source), "license_id": payload.get("license_id")})
            self._render_status()
            QMessageBox.information(self, "Lizenzverwaltung", "Lizenzdatei erfolgreich importiert.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Lizenzverwaltung", str(exc))

    def _import_license_code(self) -> None:
        try:
            self._require_privileged()
            code = self._license_code.toPlainText().strip()
            payload = self._license.import_code(code)
            self._audit.emit(
                action="license.import.code",
                actor="gui-admin",
                target=str(self._license.license_file),
                result="ok",
            )
            self._append("LIZENZ_CODE_IMPORTIERT", {"license_id": payload.get("license_id")})
            self._render_status()
            QMessageBox.information(self, "Lizenzverwaltung", "Lizenzcode erfolgreich importiert.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Lizenzverwaltung", str(exc))

    def _render_status(self) -> None:
        licensed = runtime_bootstrap.core_licensed_modules()
        known = set(runtime_bootstrap.core_license_tags())
        report = self._license.get_status_report(licensed_modules=licensed, known_tags=known)

        if report.valid:
            status = "gültig"
        elif report.present:
            status = "ungültig / unvollständig"
        else:
            status = "keine Lizenz"
        parts = [f"Basislizenz: {status}"]
        if report.license_type:
            parts.append(f"Typ: {report.license_type}")
        if report.issued_to:
            parts.append(f"Kunde: {report.issued_to}")
        if report.expires_at:
            parts.append(f"Ablauf: {report.expires_at}")
        elif report.license_type == "full" and report.valid:
            parts.append("Ablauf: unbefristet")
        if report.errors:
            parts.append(f"Hinweise: {'; '.join(report.errors)}")
        self._status_label.setText(" | ".join(parts))

        rows = []
        for state in report.module_states:
            rows.append(
                (
                    state.module_id,
                    state.license_tag,
                    "freigeschaltet" if state.licensed else "gesperrt",
                    state.block_reason or "-",
                )
            )
        self._status_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                self._status_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
        self._status_table.resizeColumnsToContents()
        self._append("MODULSTATUS", {"rows": rows, "report_errors": report.errors})
