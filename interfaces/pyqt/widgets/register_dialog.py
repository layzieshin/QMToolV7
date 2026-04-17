from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class RegisterDialog(QDialog):
    def __init__(self, usermanagement_service, parent=None) -> None:
        super().__init__(parent)
        self._um = usermanagement_service
        self.setWindowTitle("Neu registrieren")
        self._username = QLineEdit()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_confirm = QLineEdit()
        self._password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._first_name = QLineEdit()
        self._last_name = QLineEdit()
        self._email = QLineEdit()
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self._register)
        self._buttons.rejected.connect(self.reject)
        form = QFormLayout()
        form.addRow("Benutzername", self._username)
        form.addRow("Passwort", self._password)
        form.addRow("Passwort bestätigen", self._password_confirm)
        form.addRow("Vorname", self._first_name)
        form.addRow("Nachname", self._last_name)
        form.addRow("E-Mail", self._email)
        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(self._buttons)

    def _register(self) -> None:
        try:
            username = self._username.text().strip()
            password = self._password.text()
            if password != self._password_confirm.text():
                raise RuntimeError("Passwort und Bestätigung stimmen nicht überein.")
            self._um.self_register(
                username,
                password,
                first_name=self._first_name.text().strip() or None,
                last_name=self._last_name.text().strip() or None,
                email=self._email.text().strip() or None,
            )
            QMessageBox.information(
                self,
                "Registrierung",
                "Registrierung eingegangen. Ein Administrator muss Ihr Konto freischalten.",
            )
            self.accept()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Registrierung fehlgeschlagen", str(exc))

