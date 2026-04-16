"""License Management section (extracted from settings_view.py)."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QFormLayout,
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
from qm_platform.runtime.container import RuntimeContainer


class LicenseManagementWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._license = container.get_port("license_service")
        self._um = container.get_port("usermanagement_service")
        self._license_path = QLineEdit()
        self._license_text = QPlainTextEdit()
        self._status_table = QTableWidget(0, 3)
        self._status_table.setHorizontalHeaderLabels(["Modul", "Status", "Hinweis"])
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Lizenzverwaltung (GUI-only): Lizenzdatei laden/speichern und Modulstatus sichtbar machen. "
            "Eine Runtime-Recovery bei fehlender Lizenz wird hier nicht durchgeführt."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        form.addRow("Lizenzdatei", self._license_path)
        layout.addLayout(form)
        actions = QHBoxLayout()
        btn_reload = QPushButton("Lizenz laden")
        btn_reload.clicked.connect(self._load_license)
        btn_save = QPushButton("Lizenz speichern")
        btn_save.clicked.connect(self._save_license)
        btn_status = QPushButton("Modulstatus aktualisieren")
        btn_status.clicked.connect(self._render_status)
        actions.addWidget(btn_reload)
        actions.addWidget(btn_save)
        actions.addWidget(btn_status)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(self._license_text, stretch=1)
        layout.addWidget(self._status_table, stretch=1)
        layout.addWidget(self._out, stretch=1)
        self._load_license()
        self._render_status()

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _license_file(self) -> Path:
        raw = self._license_path.text().strip()
        if raw:
            return Path(raw)
        return Path(self._license.license_file)

    def _load_license(self) -> None:
        try:
            path = Path(self._license.license_file)
            self._license_path.setText(str(path))
            self._license_text.setPlainText(path.read_text(encoding="utf-8"))
            self._append("LIZENZ_GELADEN", {"path": str(path)})
        except Exception as exc:  # noqa: BLE001
            self._append("ERROR", {"message": str(exc)})

    def _save_license(self) -> None:
        try:
            self._require_privileged()
            path = self._license_file()
            parsed = json.loads(self._license_text.toPlainText().strip() or "{}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(parsed, indent=2, ensure_ascii=True), encoding="utf-8")
            self._append("LIZENZ_GESPEICHERT", {"path": str(path)})
            self._render_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Lizenzverwaltung", str(exc))

    def _render_status(self) -> None:
        modules = [
            ("signature", "signature", []),
            ("documents", "documents", ["signature"]),
            ("training", None, []),
            ("registry", None, []),
            ("usermanagement", None, []),
        ]
        rows = []
        for module_id, tag, depends_on in modules:
            if tag is None:
                rows.append((module_id, "verfügbar", "keine Lizenzpflicht"))
                continue
            try:
                allowed = bool(self._license.is_module_allowed(tag))
            except Exception as exc:  # noqa: BLE001
                rows.append((module_id, "lizenz fehlt", f"prüfen fehlgeschlagen: {exc}"))
                continue
            if allowed:
                rows.append((module_id, "verfügbar", f"abhängig von: {', '.join(depends_on) if depends_on else '-'}"))
            else:
                rows.append((module_id, "lizenz fehlt", f"Tag '{tag}' nicht freigeschaltet"))
        for idx, (module_id, status, hint) in enumerate(rows):
            if status == "verfügbar":
                continue
            for dep_idx, (m2, s2, _h2) in enumerate(rows):
                if module_id in ("documents",) and m2 == "signature" and s2 != "verfügbar":
                    rows[idx] = (module_id, "abhängig blockiert", "Abhängigkeit 'signature' nicht verfügbar")
                    break
        self._status_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                self._status_table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        self._status_table.resizeColumnsToContents()
        self._append("MODULSTATUS", {"rows": rows})

