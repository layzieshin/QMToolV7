"""Management review section."""
from __future__ import annotations

from datetime import UTC, datetime

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
)

from interfaces.pyqt.contributions.incident_management_sections.base import BaseIncidentArea
from qm_platform.runtime.container import RuntimeContainer


class ManagementReviewSection(BaseIncidentArea):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__(container, title="Managementbewertung")
        form = QFormLayout()
        self._period_start = QDateEdit()
        self._period_start.setCalendarPopup(True)
        self._period_start.setDate(QDate.currentDate().addMonths(-1))
        self._period_end = QDateEdit()
        self._period_end.setCalendarPopup(True)
        self._period_end.setDate(QDate.currentDate())
        self._batch_id = QLineEdit()
        form.addRow("Zeitraum von", self._period_start)
        form.addRow("Zeitraum bis", self._period_end)
        form.addRow("Batch-ID", self._batch_id)
        self.layout().addLayout(form)

        row = QHBoxLayout()
        create_btn = QPushButton("Bewertung anlegen")
        create_btn.clicked.connect(self._on_create)
        discuss_btn = QPushButton("In Diskussion")
        discuss_btn.clicked.connect(self._on_discuss)
        ack_btn = QPushButton("Kenntnisnahme")
        ack_btn.clicked.connect(self._on_ack)
        report_btn = QPushButton("Bericht erzeugen")
        report_btn.clicked.connect(self._on_report)
        row.addWidget(create_btn)
        row.addWidget(discuss_btn)
        row.addWidget(ack_btn)
        row.addWidget(report_btn)
        self.layout().addLayout(row)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self.layout().addWidget(self._output, stretch=1)

        self._status = QLabel("")
        self.layout().addWidget(self._status)

    def reload(self) -> None:
        self._status.setText("Bereit")

    def _to_datetime(self, date_edit: QDateEdit, *, end_of_day: bool = False) -> datetime:
        date = date_edit.date()
        if end_of_day:
            return datetime(date.year(), date.month(), date.day(), 23, 59, 59, tzinfo=UTC)
        return datetime(date.year(), date.month(), date.day(), 0, 0, 0, tzinfo=UTC)

    def _batch_id_value(self) -> str:
        return self._batch_id.text().strip()

    def _on_create(self) -> None:
        try:
            batch = self._api().create_management_review(
                self._to_datetime(self._period_start),
                self._to_datetime(self._period_end, end_of_day=True),
            )
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Anlegen fehlgeschlagen", exc)
            return
        self._batch_id.setText(batch.batch_id)
        self._output.setPlainText(
            f"Batch {batch.batch_id}\nStatus: {batch.status.value}\n"
            f"Zeitraum: {self._presenter.format_datetime(batch.period_start)} - "
            f"{self._presenter.format_datetime(batch.period_end)}"
        )
        self._status.setText("Managementbewertung angelegt.")

    def _on_discuss(self) -> None:
        batch_id = self._batch_id_value()
        if not batch_id:
            self.show_info(self, "Diskussion", "Batch-ID erforderlich.")
            return
        try:
            batch = self._api().mark_management_review_in_discussion(batch_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Diskussion fehlgeschlagen", exc)
            return
        self._status.setText(f"Batch {batch.batch_id} in Diskussion ({batch.status.value}).")

    def _on_ack(self) -> None:
        batch_id = self._batch_id_value()
        if not batch_id:
            self.show_info(self, "Kenntnisnahme", "Batch-ID erforderlich.")
            return
        try:
            items = self._api().acknowledge_management_review_items(batch_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Kenntnisnahme fehlgeschlagen", exc)
            return
        self._output.setPlainText("\n".join(f"{item.incident_id}: {item.status.value}" for item in items))
        self._status.setText(f"{len(items)} Positionen bestaetigt.")

    def _on_report(self) -> None:
        batch_id = self._batch_id_value()
        if not batch_id:
            self.show_info(self, "Bericht", "Batch-ID erforderlich.")
            return
        try:
            report = self._api().generate_management_review_report(batch_id)
        except Exception as exc:  # noqa: BLE001
            self.show_error(self, "Bericht fehlgeschlagen", exc)
            return
        self._output.setPlainText(
            f"Bericht {report.filename}\nSpeicher: {report.storage_key}\n"
            f"Groesse: {report.size_bytes} Bytes"
        )
        self._status.setText("Managementbewertungsbericht erzeugt.")
