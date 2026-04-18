"""Modal dialog to force password change after initial admin login."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class ForcePasswordChangeDialog(QDialog):
    def __init__(self, usermanagement_service, user, parent=None) -> None:
        super().__init__(parent)
        self._um = usermanagement_service
        self._username = str(getattr(user, "username", "")).strip()
        self.setWindowTitle("Passwort ändern erforderlich")
        self._current = QLineEdit()
        self._current.setEchoMode(QLineEdit.EchoMode.Password)
        self._new = QLineEdit()
        self._new.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Aktuelles Passwort", self._current)
        form.addRow("Neues Passwort", self._new)
        form.addRow("Neues Passwort (Bestätigung)", self._confirm)
        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(buttons)

    def _submit(self) -> None:
        try:
            current = self._current.text()
            new_pw = self._new.text().strip()
            if self._new.text() != self._confirm.text():
                raise RuntimeError("Neues Passwort und Bestätigung stimmen nicht überein.")
            if not new_pw:
                raise RuntimeError("Neues Passwort darf nicht leer sein.")
            if new_pw.lower() == "admin":
                raise RuntimeError("Das initiale Passwort 'admin' darf nicht erneut verwendet werden.")
            user = self._um.authenticate(self._username, current)
            if user is None:
                raise RuntimeError("Aktuelles Passwort ist falsch.")
            self._um.change_password(self._username, new_pw)
            self._um.login(self._username, new_pw)
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Passwort ändern", str(exc))
