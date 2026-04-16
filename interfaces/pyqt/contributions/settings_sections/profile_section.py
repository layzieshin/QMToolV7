"""Profile / My User section (extracted from settings_view.py)."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.presenters.settings_presenter import SettingsProfilePresenter
from qm_platform.runtime.container import RuntimeContainer


class ProfileWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._um = container.get_port("usermanagement_service")
        self._presenter = SettingsProfilePresenter()
        self._session_user = None
        self._username = QLineEdit()
        self._username.setReadOnly(True)
        self._user_id = QLineEdit()
        self._user_id.setReadOnly(True)
        self._role = QLineEdit()
        self._role.setReadOnly(True)
        self._first_name = QLineEdit()
        self._last_name = QLineEdit()
        self._email = QLineEdit()
        self._department = QLineEdit()
        self._department.setReadOnly(True)
        self._current_password = QLineEdit()
        self._current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_password = QLineEdit()
        self._confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        refresh = QPushButton("Neu laden")
        refresh.clicked.connect(self._reload)
        save = QPushButton("Alle Änderungen speichern")
        save.clicked.connect(self._save_all)

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Profil / Mein Benutzer als Ein-Formular-Ansicht mit Sektionen Konto, Organisation und Sicherheit."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        konto = QFormLayout()
        konto.addRow("Loginname", self._username)
        konto.addRow("User-ID (stabil)", self._user_id)
        konto.addRow("Rolle", self._role)
        layout.addWidget(QLabel("Konto"))
        layout.addLayout(konto)

        org = QFormLayout()
        org.addRow("Vorname", self._first_name)
        org.addRow("Nachname", self._last_name)
        org.addRow("E-Mail", self._email)
        org.addRow("Abteilung", self._department)
        layout.addWidget(QLabel("Organisation"))
        layout.addLayout(org)

        sec = QFormLayout()
        sec.addRow("Aktuelles Passwort", self._current_password)
        sec.addRow("Neues Passwort", self._new_password)
        sec.addRow("Neues Passwort (Bestätigung)", self._confirm_password)
        layout.addWidget(QLabel("Sicherheit"))
        layout.addLayout(sec)

        row = QHBoxLayout()
        row.addWidget(refresh)
        row.addWidget(save)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(QLabel("Ergebnis"))
        layout.addWidget(self._out, stretch=1)
        self._reload()

    def _reload(self) -> None:
        self._session_user = self._um.get_current_user()
        if self._session_user is None:
            self._out.setPlainText("Anmeldung erforderlich.")
            return
        self._username.setText(self._session_user.username)
        self._user_id.setText(self._session_user.user_id)
        self._role.setText(self._session_user.role)
        first = (getattr(self._session_user, "first_name", None) or "").strip()
        last = (getattr(self._session_user, "last_name", None) or "").strip()
        if not first and not last:
            legacy = (getattr(self._session_user, "display_name", None) or "").strip()
            if "," in legacy:
                first, last = [p.strip() for p in legacy.split(",", 1)]
            elif legacy:
                parts = legacy.split()
                first = parts[0]
                last = " ".join(parts[1:]) if len(parts) > 1 else ""
        self._first_name.setText(first)
        self._last_name.setText(last)
        self._email.setText(self._session_user.email or "")
        self._department.setText(self._session_user.department or "")
        self._out.setPlainText(self._presenter.describe_session(self._session_user))

    def _save_all(self) -> None:
        try:
            if self._session_user is None:
                raise RuntimeError("Anmeldung erforderlich")
            current_pw = self._current_password.text().strip()
            new_pw = self._new_password.text().strip()
            confirm_pw = self._confirm_password.text().strip()
            first_name = self._first_name.text().strip() or None
            last_name = self._last_name.text().strip() or None
            email = self._email.text().strip() or None

            profile_changed = (
                (getattr(self._session_user, "first_name", None) or None) != first_name
                or (getattr(self._session_user, "last_name", None) or None) != last_name
                or (self._session_user.email or None) != email
            )
            pw_changed = bool(current_pw or new_pw or confirm_pw)

            if not profile_changed and not pw_changed:
                self._out.setPlainText("Keine Änderungen erkannt.")
                return

            if profile_changed:
                self._um.update_user_profile(
                    self._session_user.username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                )

            if pw_changed:
                if not current_pw:
                    raise RuntimeError("Aktuelles Passwort erforderlich")
                if not new_pw:
                    raise RuntimeError("Neues Passwort erforderlich")
                if new_pw != confirm_pw:
                    raise RuntimeError("Neues Passwort und Bestätigung stimmen nicht überein")
                auth_fn = getattr(self._um, "authenticate", None)
                if not callable(auth_fn):
                    raise RuntimeError("Passwortvalidierung nicht verfügbar")
                auth = auth_fn(self._session_user.username, current_pw)
                if auth is None:
                    raise RuntimeError("Aktuelles Passwort ist nicht korrekt")
                self._um.change_password(self._session_user.username, new_pw)
            self._current_password.clear()
            self._new_password.clear()
            self._confirm_password.clear()
            self._reload()
            self._out.setPlainText(
                self._presenter.save_result(
                    username=self._session_user.username,
                    profile_changed=profile_changed,
                    password_changed=pw_changed,
                )
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Profil", str(exc))

