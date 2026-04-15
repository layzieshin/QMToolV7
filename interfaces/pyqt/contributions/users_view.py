from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import as_json_text
from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.widgets.access_guards import require_admin_or_qmb
from interfaces.pyqt.widgets.users_admin_helpers import UsersAdminPresenter
from qm_platform.runtime.container import RuntimeContainer


class UsersAdminWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._um = container.get_port("usermanagement_service")
        self._presenter = UsersAdminPresenter()
        self._visible_users: list[object] = []
        self._search = QLineEdit()
        self._search.setPlaceholderText("Suche nach Loginname, User-ID, Vorname oder Nachname")
        self._role_filter = QComboBox()
        self._role_filter.addItems(["Alle", "Admin", "QMB", "User"])
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Loginname", "User-ID", "Vorname", "Nachname", "Rolle"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self._detail_user = QLineEdit()
        self._detail_user.setReadOnly(True)
        self._detail_user_id = QLineEdit()
        self._detail_user_id.setReadOnly(True)
        self._detail_first_name = QLineEdit()
        self._detail_first_name.setReadOnly(True)
        self._detail_last_name = QLineEdit()
        self._detail_last_name.setReadOnly(True)
        self._detail_role = QLineEdit()
        self._detail_role.setReadOnly(True)
        self._detail_department = QLineEdit()
        self._detail_scope = QLineEdit()
        self._detail_org_unit = QLineEdit()
        self._detail_new_role = QComboBox()
        self._detail_new_role.addItems(["(unverändert)", "Admin", "QMB", "User"])
        self._detail_is_active = QCheckBox("Benutzer aktiv")
        self._detail_is_active.setChecked(True)
        self._change_password = QLineEdit()
        self._change_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._change_password_confirm = QLineEdit()
        self._change_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)

        self._new_username = QLineEdit()
        self._new_password = QLineEdit()
        self._new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_role = QComboBox()
        self._new_role.addItems(["Admin", "QMB", "User"])
        self._out = QPlainTextEdit()
        self._out.setReadOnly(True)

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel("Benutzerverwaltung mit klarem Rollenmodell: Loginname, stabile User-ID, Vorname/Nachname."))

        filters = QHBoxLayout()
        filters.addWidget(self._search)
        filters.addWidget(self._role_filter)
        btn_refresh = QPushButton("Aktualisieren")
        btn_refresh.clicked.connect(self._reload)
        filters.addWidget(btn_refresh)
        outer.addLayout(filters)

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(self._table, stretch=1)

        create_box = QWidget()
        create_form = QFormLayout(create_box)
        create_form.addRow("Neuer Benutzername", self._new_username)
        create_form.addRow("Neues Passwort", self._new_password)
        create_form.addRow("Rolle", self._new_role)
        btn_create = QPushButton("Benutzer anlegen")
        btn_create.clicked.connect(self._create_user)
        create_form.addRow("", btn_create)
        left_layout.addWidget(create_box)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Detail / sensible Aktionen"))
        detail_form = QFormLayout()
        detail_form.addRow("Loginname", self._detail_user)
        detail_form.addRow("User-ID (stabil)", self._detail_user_id)
        detail_form.addRow("Vorname", self._detail_first_name)
        detail_form.addRow("Nachname", self._detail_last_name)
        detail_form.addRow("Rolle", self._detail_role)
        detail_form.addRow("Neue Rolle", self._detail_new_role)
        detail_form.addRow("Abteilung", self._detail_department)
        detail_form.addRow("Scope", self._detail_scope)
        detail_form.addRow("Organisationseinheit", self._detail_org_unit)
        detail_form.addRow("", self._detail_is_active)
        detail_form.addRow("Neues Passwort", self._change_password)
        detail_form.addRow("Neues Passwort (Bestätigung)", self._change_password_confirm)
        right_layout.addLayout(detail_form)
        btn_save_admin = QPushButton("Admin-Felder speichern")
        btn_save_admin.clicked.connect(self._save_admin_fields)
        right_layout.addWidget(btn_save_admin)
        btn_change = QPushButton("Passwort für Benutzer ändern")
        btn_change.clicked.connect(self._change_pw)
        right_layout.addWidget(btn_change)
        right_layout.addWidget(QLabel("Ergebnis"))
        right_layout.addWidget(self._out, stretch=1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter, stretch=1)

        self._search.textChanged.connect(lambda _text: self._render_table())
        self._role_filter.currentIndexChanged.connect(lambda _idx: self._render_table())
        self._table.itemSelectionChanged.connect(self._on_select)
        self._reload()

    def _append(self, title: str, payload: object) -> None:
        self._out.appendPlainText(f"{title}\n{as_json_text(payload)}\n")

    def _require_privileged(self) -> None:
        require_admin_or_qmb(self._um)

    def _reload(self) -> None:
        try:
            self._require_privileged()
            self._presenter.set_users(self._um.list_users())
            self._render_table()
            self._append("BENUTZER_GELADEN", {"count": len(self._visible_users)})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Benutzer", str(exc))

    def _render_table(self) -> None:
        search = self._search.text().strip()
        selected_role = self._role_filter.currentText()
        self._visible_users = self._presenter.filtered_users(search=search, selected_role=selected_role)
        self._table.setRowCount(len(self._visible_users))
        for idx, user in enumerate(self._visible_users):
            self._table.setItem(idx, 0, QTableWidgetItem(str(getattr(user, "username", ""))))
            self._table.setItem(idx, 1, QTableWidgetItem(str(getattr(user, "user_id", ""))))
            self._table.setItem(idx, 2, QTableWidgetItem(str(getattr(user, "first_name", "") or "")))
            self._table.setItem(idx, 3, QTableWidgetItem(str(getattr(user, "last_name", "") or "")))
            self._table.setItem(idx, 4, QTableWidgetItem(str(getattr(user, "role", ""))))
        self._table.resizeColumnsToContents()

    def _on_select(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._visible_users):
            return
        user = self._visible_users[row]
        self._detail_user.setText(str(getattr(user, "username", "")))
        self._detail_user_id.setText(str(getattr(user, "user_id", "")))
        self._detail_first_name.setText(str(getattr(user, "first_name", "") or ""))
        self._detail_last_name.setText(str(getattr(user, "last_name", "") or ""))
        self._detail_role.setText(str(getattr(user, "role", "")))
        self._detail_new_role.setCurrentIndex(0)
        self._detail_department.setText(str(getattr(user, "department", "") or ""))
        self._detail_scope.setText(str(getattr(user, "scope", "") or ""))
        self._detail_org_unit.setText(str(getattr(user, "organization_unit", "") or ""))
        self._detail_is_active.setChecked(bool(getattr(user, "is_active", True)))

    def _create_user(self) -> None:
        try:
            self._require_privileged()
            username = self._new_username.text().strip()
            role = self._new_role.currentText().strip()
            if not username:
                raise RuntimeError("Benutzername fehlt")
            confirmed = QMessageBox.question(
                self,
                "Benutzer anlegen",
                f"Sensibler Vorgang: Benutzer '{username}' mit Rolle '{role}' anlegen?",
            )
            if confirmed != QMessageBox.StandardButton.Yes:
                return
            created = self._um.create_user(
                username,
                self._new_password.text().strip(),
                role,
            )
            self._append("BENUTZER_ANGELEGT", created)
            self._reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Benutzer", str(exc))

    def _change_pw(self) -> None:
        try:
            self._require_privileged()
            username = self._detail_user.text().strip()
            if not username:
                raise RuntimeError("Bitte zuerst einen Benutzer in der Tabelle auswählen")
            new_password = self._change_password.text().strip()
            confirm_password = self._change_password_confirm.text().strip()
            if new_password != confirm_password:
                raise RuntimeError("Passwort und Bestätigung stimmen nicht überein")
            confirmed = QMessageBox.question(
                self,
                "Passwort ändern",
                f"Sensibler Vorgang: Passwort für '{username}' ändern?",
            )
            if confirmed != QMessageBox.StandardButton.Yes:
                return
            self._um.change_password(username, new_password)
            self._append("PASSWORT_GEAENDERT", {"username": username})
            self._change_password.clear()
            self._change_password_confirm.clear()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Benutzer", str(exc))

    def _save_admin_fields(self) -> None:
        try:
            self._require_privileged()
            username = self._detail_user.text().strip()
            if not username:
                raise RuntimeError("Bitte zuerst einen Benutzer in der Tabelle auswählen")
            role = self._detail_new_role.currentText().strip()
            selected_role = None if role == "(unverändert)" else role
            updated = self._um.update_user_admin_fields(
                username,
                department=self._detail_department.text().strip() or None,
                scope=self._detail_scope.text().strip() or None,
                organization_unit=self._detail_org_unit.text().strip() or None,
                role=selected_role,
                is_active=self._detail_is_active.isChecked(),
            )
            self._append("BENUTZER_ADMINFELDER_GESPEICHERT", updated)
            self._reload()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Benutzer", str(exc))


def _build(container: RuntimeContainer) -> QWidget:
    return UsersAdminWidget(container)


def contributions() -> list[QtModuleContribution]:
    return []
