"""Training / quiz module settings (extracted from settings_view.py)."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from qm_platform.runtime.container import RuntimeContainer


class TrainingSettingsWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._settings = container.get_port("settings_service")
        self._um = container.get_port("usermanagement_service")

        self._questions = QSpinBox()
        self._questions.setRange(1, 100)
        self._min_correct = QSpinBox()
        self._min_correct.setRange(1, 100)
        self._cooldown = QSpinBox()
        self._cooldown.setRange(0, 86400)
        self._shuffle = QPushButton()
        self._shuffle.setCheckable(True)
        self._reread = QPushButton()
        self._reread.setCheckable(True)
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)
        self._out.setMaximumHeight(100)

        form = QFormLayout()
        form.addRow("Fragen pro Quiz", self._questions)
        form.addRow("Mindestens richtige Antworten", self._min_correct)
        form.addRow("Cooldown nach Fehlversuch (Sekunden)", self._cooldown)
        form.addRow("Antworten mischen", self._shuffle)
        form.addRow("Nach Fehlversuch erneutes Lesen erzwingen", self._reread)

        row = QHBoxLayout()
        btn_save = QPushButton("Speichern")
        btn_save.clicked.connect(self._save)
        btn_reload = QPushButton("Zuruecksetzen")
        btn_reload.clicked.connect(self._reload)
        row.addWidget(btn_save)
        row.addWidget(btn_reload)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(row)
        layout.addWidget(self._out)

        self._questions.valueChanged.connect(self._sync_min_bounds)
        self._shuffle.toggled.connect(lambda checked: self._apply_toggle_style(self._shuffle, checked))
        self._reread.toggled.connect(lambda checked: self._apply_toggle_style(self._reread, checked))
        self._reload()

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _sync_min_bounds(self) -> None:
        self._min_correct.setMaximum(self._questions.value())
        if self._min_correct.value() > self._questions.value():
            self._min_correct.setValue(self._questions.value())

    @staticmethod
    def _apply_toggle_style(button: QPushButton, active: bool) -> None:
        if active:
            button.setText("✓ aktiv")
            button.setStyleSheet("color: #1B8E3E;")
        else:
            button.setText("⊘ inaktiv")
            button.setStyleSheet("color: #C62828;")

    def _reload(self) -> None:
        cfg = self._settings.get_module_settings("training")
        questions = int(cfg.get("questions_per_quiz", 3) or 3)
        min_correct = int(cfg.get("min_correct_answers", questions) or questions)
        self._questions.setValue(max(1, questions))
        self._sync_min_bounds()
        self._min_correct.setValue(max(1, min(min_correct, self._questions.value())))
        self._cooldown.setValue(max(0, int(cfg.get("retry_cooldown_seconds", 0) or 0)))
        self._shuffle.setChecked(bool(cfg.get("shuffle_answers", True)))
        self._reread.setChecked(bool(cfg.get("force_reread_on_fail", False)))
        self._apply_toggle_style(self._shuffle, self._shuffle.isChecked())
        self._apply_toggle_style(self._reread, self._reread.isChecked())
        self._out.setPlainText("Schulungseinstellungen geladen.")

    def _save(self) -> None:
        try:
            self._require_privileged()
            payload = self._settings.get_module_settings("training")
            payload["questions_per_quiz"] = int(self._questions.value())
            payload["min_correct_answers"] = int(min(self._min_correct.value(), self._questions.value()))
            payload["retry_cooldown_seconds"] = int(self._cooldown.value())
            payload["shuffle_answers"] = bool(self._shuffle.isChecked())
            payload["force_reread_on_fail"] = bool(self._reread.isChecked())
            self._settings.set_module_settings("training", payload, acknowledge_governance_change=False)
            self._out.setPlainText("Schulungseinstellungen gespeichert.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Schulungseinstellungen", str(exc))
