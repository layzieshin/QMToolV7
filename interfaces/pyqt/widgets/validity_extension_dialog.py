from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from modules.documents.contracts import ValidityExtensionOutcome


@dataclass(frozen=True)
class ValidityExtensionRequest:
    duration_days: int
    reason: str
    review_outcome: ValidityExtensionOutcome


class ValidityExtensionDialog(QDialog):
    def __init__(
        self,
        *,
        valid_from: datetime | None,
        valid_until: datetime | None,
        next_review_at: datetime | None,
        extension_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gueltigkeit verlaengern")
        self.setMinimumWidth(560)
        self._base_date = valid_until or datetime.now(timezone.utc)

        layout = QVBoxLayout(self)
        summary = QFormLayout()
        summary.addRow("Gueltig ab", QLabel(self._fmt(valid_from)))
        summary.addRow("Gueltig bis", QLabel(self._fmt(valid_until)))
        summary.addRow("Naechste Pruefung", QLabel(self._fmt(next_review_at)))
        summary.addRow("Verlaengerungen", QLabel(f"{extension_count}/3"))
        layout.addLayout(summary)

        duration_box = QGroupBox("Neue Dauer")
        duration_layout = QVBoxLayout(duration_box)
        self._duration_group = QButtonGroup(self)
        self._preset_6 = QRadioButton("6 Monate (183 Tage)")
        self._preset_12 = QRadioButton("12 Monate (365 Tage)")
        self._preset_24 = QRadioButton("24 Monate (730 Tage)")
        self._custom = QRadioButton("Benutzerdefiniert bis Datum")
        self._preset_12.setChecked(True)
        for idx, btn in enumerate((self._preset_6, self._preset_12, self._preset_24, self._custom), start=1):
            self._duration_group.addButton(btn, idx)
            duration_layout.addWidget(btn)
        today = QDate.currentDate()
        default_target = self._base_date.date()
        default_qdate = QDate(default_target.year, default_target.month, default_target.day).addDays(365)
        self._custom_date = QDateEdit(default_qdate)
        self._custom_date.setCalendarPopup(True)
        self._custom_date.setMinimumDate(today)
        self._custom_date.setEnabled(False)
        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Datum"))
        custom_row.addWidget(self._custom_date)
        duration_layout.addLayout(custom_row)
        self._custom.toggled.connect(self._custom_date.setEnabled)
        layout.addWidget(duration_box)

        self._reason = QPlainTextEdit()
        self._reason.setPlaceholderText("Begruendung fuer die Verlaengerung (Pflichtfeld)")
        self._reason.setMinimumHeight(90)
        layout.addWidget(QLabel("Begruendung"))
        layout.addWidget(self._reason)

        outcome_box = QGroupBox("Review-Entscheidung")
        outcome_layout = QVBoxLayout(outcome_box)
        self._outcome_group = QButtonGroup(self)
        self._outcome_unchanged = QRadioButton("Unveraendert freigegeben")
        self._outcome_editorial = QRadioButton("Kleine redaktionelle Aenderung")
        self._outcome_new_version = QRadioButton("Neue Version notwendig")
        self._outcome_unchanged.setChecked(True)
        for idx, btn in enumerate((self._outcome_unchanged, self._outcome_editorial, self._outcome_new_version), start=1):
            self._outcome_group.addButton(btn, idx)
            outcome_layout.addWidget(btn)
        layout.addWidget(outcome_box)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self._outcome_new_version.toggled.connect(self._update_state)
        self._update_state()

    def payload(self) -> ValidityExtensionRequest:
        duration_days = self._compute_duration_days()
        reason = self._reason.toPlainText().strip()
        outcome = self._selected_outcome()
        return ValidityExtensionRequest(duration_days=duration_days, reason=reason, review_outcome=outcome)

    def _on_accept(self) -> None:
        reason = self._reason.toPlainText().strip()
        if len(reason) < 10:
            self._hint.setText("Begruendung muss mindestens 10 Zeichen lang sein.")
            return
        if self._selected_outcome() == ValidityExtensionOutcome.NEW_VERSION_REQUIRED:
            self._hint.setText("Keine Verlaengerung moeglich - bitte neuen Versionsworkflow starten.")
            return
        if self._compute_duration_days() <= 0:
            self._hint.setText("Die ausgewaehlte Dauer muss in der Zukunft liegen.")
            return
        self.accept()

    def _compute_duration_days(self) -> int:
        if self._preset_6.isChecked():
            return 183
        if self._preset_12.isChecked():
            return 365
        if self._preset_24.isChecked():
            return 730
        target = self._custom_date.date().toPyDate()
        delta = target - self._base_date.date()
        return int(delta.days)

    def _selected_outcome(self) -> ValidityExtensionOutcome:
        if self._outcome_editorial.isChecked():
            return ValidityExtensionOutcome.EDITORIAL
        if self._outcome_new_version.isChecked():
            return ValidityExtensionOutcome.NEW_VERSION_REQUIRED
        return ValidityExtensionOutcome.UNCHANGED

    def _update_state(self) -> None:
        blocked = self._outcome_new_version.isChecked()
        ok_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(not blocked)
        if blocked:
            self._hint.setText("Keine Verlaengerung moeglich - bitte neuen Versionsworkflow starten.")
        else:
            self._hint.setText("")

    @staticmethod
    def _fmt(value: datetime | None) -> str:
        if value is None:
            return "-"
        return value.strftime("%Y-%m-%d")
