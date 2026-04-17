from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QMessageBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QDateEdit,
)

from interfaces.pyqt.contributions.common import as_json_text, normalize_role
from interfaces.pyqt.presenters.formatting import format_local
from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.widgets.audit_log_helpers import build_admin_checks, build_doc_history, build_technical_rows
from interfaces.pyqt.widgets.table_helpers import configure_readonly_table, fill_table
from qm_platform.runtime.container import RuntimeContainer
from modules.usermanagement.role_policies import is_effective_qmb


class AuditLogsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._registry = container.get_port("registry_api")
        self._docs = container.get_port("documents_service")
        self._pool = container.get_port("documents_pool_api")
        self._license = container.get_port("license_service")
        self._settings = container.get_port("settings_service")

        self._doc_id = QLineEdit()
        self._version = QLineEdit("1")
        self._functional_table = QTableWidget(0, 6)
        configure_readonly_table(
            self._functional_table,
            ["Zeit", "Aktion", "Benutzer", "Ziel", "Ergebnis", "Begruendung"],
        )
        self._functional_action_filter = QLineEdit()
        self._functional_action_filter.setPlaceholderText("Aktion enthält")
        self._functional_actor_filter = QLineEdit()
        self._functional_actor_filter.setPlaceholderText("Benutzer enthält")
        self._functional_target_filter = QLineEdit()
        self._functional_target_filter.setPlaceholderText("Ziel/Dokument-ID enthält")
        self._functional_result_filter = QLineEdit()
        self._functional_result_filter.setPlaceholderText("Ergebnis enthält")
        self._functional_rows: list[tuple[str, str, str, str, str, str]] = []
        self._functional_from = QDateEdit()
        self._functional_to = QDateEdit()
        self._setup_date_editors(self._functional_from, self._functional_to)

        self._tech_table = QTableWidget(0, 4)
        configure_readonly_table(self._tech_table, ["Zeit", "Level", "Modul", "Nachricht"])
        self._tech_level_filter = QLineEdit()
        self._tech_level_filter.setPlaceholderText("Level filtern (z.B. ERROR)")
        self._tech_module_filter = QLineEdit()
        self._tech_module_filter.setPlaceholderText("Modul filtern")
        self._tech_message_filter = QLineEdit()
        self._tech_message_filter.setPlaceholderText("Nachricht enthält")
        self._tech_rows: list[tuple[str, str, str, str]] = []
        self._tech_from = QDateEdit()
        self._tech_to = QDateEdit()
        self._setup_date_editors(self._tech_from, self._tech_to)
        self._ops = QPlainTextEdit()
        self._ops.setReadOnly(True)
        self._backup_banner = QLabel("")
        self._backup_banner.setWordWrap(True)
        self._backup_banner.setStyleSheet("padding: 6px; border: 1px solid #d4a017; background: #fff4cc;")
        self._backup_banner.setVisible(False)
        self._btn_backup = QPushButton("Backup erstellen")
        self._btn_backup.clicked.connect(self._create_backup)
        current_user = self._container.get_port("usermanagement_service").get_current_user()
        is_admin = bool(current_user) and (
            normalize_role(getattr(current_user, "role", None)) == "ADMIN" or is_effective_qmb(current_user)
        )
        self._btn_backup.setVisible(bool(self._container.has_port("log_backup_service")) and is_admin)

        tabs = QTabWidget()
        tabs.addTab(self._build_functional_tab(), "Fachliche Historie")
        tabs.addTab(self._build_technical_tab(), "Technische Logs")
        tabs.addTab(self._build_ops_tab(), "Admin Checks")

        layout = QVBoxLayout(self)
        note = QLabel(
            "Audit & Logs kombiniert fachliche Historie mit technischen Software-Logs. "
            "Nur fuer Admin/QMB sichtbar."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        backup_row = QHBoxLayout()
        backup_row.addWidget(self._backup_banner, stretch=1)
        backup_row.addWidget(self._btn_backup)
        layout.addLayout(backup_row)
        layout.addWidget(tabs, stretch=1)
        self._reload_functional()
        self._reload_technical()
        self._run_admin_checks()
        self._refresh_backup_banner()

    def _build_functional_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.addRow("Dokument-ID", self._doc_id)
        form.addRow("Version", self._version)
        form.addRow("Von", self._functional_from)
        form.addRow("Bis", self._functional_to)
        form.addRow("Aktion", self._functional_action_filter)
        form.addRow("Benutzer", self._functional_actor_filter)
        form.addRow("Ziel", self._functional_target_filter)
        form.addRow("Ergebnis", self._functional_result_filter)
        layout.addLayout(form)
        row = QHBoxLayout()
        btn_summary = QPushButton("Audit-Historie laden")
        btn_summary.clicked.connect(self._reload_functional)
        btn_doc = QPushButton("Dokumenthistorie laden")
        btn_doc.clicked.connect(self._load_doc_history)
        btn_filter = QPushButton("Filter anwenden")
        btn_filter.clicked.connect(self._apply_functional_filters)
        btn_export_csv = QPushButton("Export CSV")
        btn_export_csv.clicked.connect(self._export_audit_csv)
        btn_export_pdf = QPushButton("Export PDF")
        btn_export_pdf.clicked.connect(self._export_audit_pdf)
        row.addWidget(btn_summary)
        row.addWidget(btn_doc)
        row.addWidget(btn_filter)
        row.addWidget(btn_export_csv)
        row.addWidget(btn_export_pdf)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self._functional_table, stretch=1)
        return tab

    def _build_technical_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        filter_form = QFormLayout()
        filter_form.addRow("Von", self._tech_from)
        filter_form.addRow("Bis", self._tech_to)
        filter_form.addRow("Level", self._tech_level_filter)
        filter_form.addRow("Modul", self._tech_module_filter)
        filter_form.addRow("Nachricht", self._tech_message_filter)
        layout.addLayout(filter_form)
        row = QHBoxLayout()
        btn = QPushButton("Technische Logs aktualisieren")
        btn.clicked.connect(self._reload_technical)
        btn_filter = QPushButton("Filter anwenden")
        btn_filter.clicked.connect(self._apply_tech_filters)
        btn_export_csv = QPushButton("Export CSV")
        btn_export_csv.clicked.connect(self._export_tech_csv)
        btn_export_pdf = QPushButton("Export PDF")
        btn_export_pdf.clicked.connect(self._export_tech_pdf)
        row.addWidget(btn)
        row.addWidget(btn_filter)
        row.addWidget(btn_export_csv)
        row.addWidget(btn_export_pdf)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self._tech_table, stretch=1)
        return tab

    def _build_ops_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        btn = QPushButton("Admin Checks ausfuehren (Health/License)")
        btn.clicked.connect(self._run_admin_checks)
        layout.addWidget(btn)
        layout.addWidget(self._ops, stretch=1)
        return tab

    def _reload_functional(self) -> None:
        if self._container.has_port("log_query_service"):
            query_service = self._container.get_port("log_query_service")
            date_from, date_to = self._date_range_utc(self._functional_from, self._functional_to)
            self._functional_rows = [
                (
                format_local(entry.get("timestamp_utc", "")),
                    str(entry.get("action", "")),
                    str(entry.get("actor", "")),
                    str(entry.get("target", "")),
                    str(entry.get("result", "")),
                    str(entry.get("reason", "")),
                )
                for entry in query_service.query_audit(limit=600, date_from=date_from, date_to=date_to)
            ]
        else:
            self._functional_rows = [("", "INFO", "", "audit", "log_query_service fehlt", "")]
        self._apply_functional_filters()

    def _load_doc_history(self) -> None:
        doc_id = self._doc_id.text().strip()
        if not doc_id:
            return
        version = int(self._version.text().strip() or "1")
        payload = build_doc_history(self._registry, self._pool, self._docs, doc_id, version)
        state = payload.get("state")
        self._functional_rows = [
            (
                format_local(getattr(state, "last_event_at", "")),
                str(getattr(state, "last_event_id", "")),
                str(getattr(state, "last_actor_user_id", "")),
                f"{doc_id}:v{version}",
                str(getattr(state, "status", "")),
                "",
            )
        ]
        self._apply_functional_filters()

    def _apply_functional_filters(self) -> None:
        action = self._functional_action_filter.text().strip().lower()
        actor = self._functional_actor_filter.text().strip().lower()
        target = self._functional_target_filter.text().strip().lower()
        result = self._functional_result_filter.text().strip().lower()
        filtered = []
        for row in self._functional_rows:
            if action and action not in row[1].lower():
                continue
            if actor and actor not in row[2].lower():
                continue
            if target and target not in row[3].lower():
                continue
            if result and result not in row[4].lower():
                continue
            filtered.append(row)
        fill_table(self._functional_table, filtered)

    def _reload_technical(self) -> None:
        rows: list[tuple[str, str, str, str]]
        if self._container.has_port("log_query_service"):
            query_service = self._container.get_port("log_query_service")
            date_from, date_to = self._date_range_utc(self._tech_from, self._tech_to)
            rows = []
            for entry in query_service.query_technical_logs(limit=400, date_from=date_from, date_to=date_to):
                rows.append(
                    (
                        format_local(entry.get("timestamp_utc", "")),
                        str(entry.get("level", "INFO")),
                        str(entry.get("module", "platform")),
                        str(entry.get("message", "")),
                    )
                )
            for entry in query_service.query_audit(limit=200, date_from=date_from, date_to=date_to):
                rows.append(
                    (
                        format_local(entry.get("timestamp_utc", "")),
                        "AUDIT",
                        "audit",
                        str(entry.get("action", "")),
                    )
                )
        else:
            app_home = self._container.get_port("app_home")
            rows = build_technical_rows(app_home)
        self._tech_rows = rows
        self._apply_tech_filters()

    def _apply_tech_filters(self) -> None:
        level = self._tech_level_filter.text().strip().lower()
        module = self._tech_module_filter.text().strip().lower()
        message = self._tech_message_filter.text().strip().lower()
        filtered: list[tuple[str, str, str, str]] = []
        for row in self._tech_rows:
            if level and level not in row[1].lower():
                continue
            if module and module not in row[2].lower():
                continue
            if message and message not in row[3].lower():
                continue
            filtered.append(row)
        fill_table(self._tech_table, filtered)

    def _export_tech_csv(self) -> None:
        if not self._container.has_port("log_query_service"):
            self._ops.setPlainText("Export nicht verfügbar: log_query_service fehlt.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV Export", "", "CSV (*.csv)")
        if not path:
            return
        service = self._container.get_port("log_query_service")
        date_from, date_to = self._date_range_utc(self._tech_from, self._tech_to)
        output = service.export_logs_csv(Path(path), date_from=date_from, date_to=date_to)
        self._ops.setPlainText(f"CSV exportiert: {output}")

    def _export_tech_pdf(self) -> None:
        if not self._container.has_port("log_query_service"):
            self._ops.setPlainText("Export nicht verfügbar: log_query_service fehlt.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "PDF Export", "", "PDF (*.pdf)")
        if not path:
            return
        service = self._container.get_port("log_query_service")
        date_from, date_to = self._date_range_utc(self._tech_from, self._tech_to)
        output = service.export_logs_pdf(Path(path), date_from=date_from, date_to=date_to)
        self._ops.setPlainText(f"PDF exportiert: {output}")

    def _export_audit_csv(self) -> None:
        if not self._container.has_port("log_query_service"):
            self._ops.setPlainText("Export nicht verfügbar: log_query_service fehlt.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Audit CSV Export", "", "CSV (*.csv)")
        if not path:
            return
        service = self._container.get_port("log_query_service")
        date_from, date_to = self._date_range_utc(self._functional_from, self._functional_to)
        output = service.export_audit_csv(Path(path), date_from=date_from, date_to=date_to)
        self._ops.setPlainText(f"Audit-CSV exportiert: {output}")

    def _export_audit_pdf(self) -> None:
        if not self._container.has_port("log_query_service"):
            self._ops.setPlainText("Export nicht verfügbar: log_query_service fehlt.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Audit PDF Export", "", "PDF (*.pdf)")
        if not path:
            return
        service = self._container.get_port("log_query_service")
        date_from, date_to = self._date_range_utc(self._functional_from, self._functional_to)
        output = service.export_audit_pdf(Path(path), date_from=date_from, date_to=date_to)
        self._ops.setPlainText(f"Audit-PDF exportiert: {output}")

    def _run_admin_checks(self) -> None:
        checks = build_admin_checks(self._container, self._license, self._settings)
        self._ops.setPlainText(as_json_text(checks))

    @staticmethod
    def _setup_date_editors(from_editor: QDateEdit, to_editor: QDateEdit) -> None:
        today = QDate.currentDate()
        from_editor.setCalendarPopup(True)
        to_editor.setCalendarPopup(True)
        from_editor.setDisplayFormat("dd.MM.yyyy")
        to_editor.setDisplayFormat("dd.MM.yyyy")
        from_editor.setDate(today.addDays(-7))
        to_editor.setDate(today)

    @staticmethod
    def _date_range_utc(from_editor: QDateEdit, to_editor: QDateEdit) -> tuple[datetime, datetime]:
        from_date = from_editor.date().toPyDate()
        to_date = to_editor.date().toPyDate()
        if to_date < from_date:
            from_date, to_date = to_date, from_date
            from_editor.setDate(QDate(from_date.year, from_date.month, from_date.day))
            to_editor.setDate(QDate(to_date.year, to_date.month, to_date.day))
        start_local = datetime.combine(from_date, time.min).astimezone()
        end_local = datetime.combine(to_date + timedelta(days=1), time.min).astimezone()
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

    def _create_backup(self) -> None:
        if not self._container.has_port("log_backup_service"):
            self._ops.setPlainText("Backup nicht verfuegbar: log_backup_service fehlt.")
            return
        try:
            service = self._container.get_port("log_backup_service")
            result = service.create_backup()
            self._ops.setPlainText(
                f"Backup erstellt: {result.zip_path}\n"
                f"Audit-Zeilen: {result.audit_lines}\n"
                f"Technische Zeilen: {result.platform_lines}\n"
                f"Cutoff UTC: {result.cutoff_utc.isoformat()}"
            )
            self._refresh_backup_banner()
            QMessageBox.information(self, "Logs-Backup", f"Backup erstellt:\n{result.zip_path}")
        except Exception as exc:  # noqa: BLE001
            self._ops.setPlainText(f"Backup fehlgeschlagen: {exc}")
            QMessageBox.warning(self, "Logs-Backup", str(exc))

    def _refresh_backup_banner(self) -> None:
        if not self._container.has_port("backup_reminder_service"):
            self._backup_banner.setVisible(False)
            return
        status = self._container.get_port("backup_reminder_service").status()
        if not status.is_overdue:
            self._backup_banner.setVisible(False)
            return
        days = status.days_since_last_backup if status.days_since_last_backup is not None else "?"
        self._backup_banner.setText(
            f"Letztes Logs-Backup vor {days} Tagen. Bitte Backup erstellen."
        )
        self._backup_banner.setVisible(True)


def _build(container: RuntimeContainer) -> QWidget:
    return AuditLogsWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="platform.audit_logs",
            module_id="platform",
            title="Audit & Logs",
            sort_order=60,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB"),
        )
    ]
