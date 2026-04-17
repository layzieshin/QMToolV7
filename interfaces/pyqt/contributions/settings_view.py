"""Settings contribution: tab shell, standalone Signatur-Dialog, Registry-Eintrag."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from interfaces.pyqt.contributions.common import normalize_role
from interfaces.pyqt.contributions.settings_sections import (
    LicenseManagementWidget,
    ModuleSettingsWidget,
    PlannedOptionsWidget,
    ProfileWidget,
    SignatureSettingsWidget,
    TrainingSettingsWidget,
    WorkflowProfilesWidget,
)
from interfaces.pyqt.contributions.users_view import UsersAdminWidget
from interfaces.pyqt.registry.contribution import QtModuleContribution
from modules.usermanagement.role_policies import is_effective_qmb
from qm_platform.runtime.container import RuntimeContainer


class SettingsAdminWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._um = container.get_port("usermanagement_service")
        self._tabs = QTabWidget()
        self._sections: list[tuple[str, QWidget]] = []
        self._populate_sections()

        layout = QVBoxLayout(self)
        header = QLabel(
            "Einstellungen als zentraler Bereich mit horizontalen Reitern und rollenabhängigen Inhalten."
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(self._tabs, stretch=1)

    def _populate_sections(self) -> None:
        user = self._um.get_current_user()
        role = normalize_role(user.role) if user is not None else ""
        has_qmb = is_effective_qmb(user) if user is not None else False

        self._add_section("Profil / Mein Benutzer", ProfileWidget(self._container))
        self._add_section("Signatur", SignatureSettingsWidget(self._container))
        if role == "ADMIN" or has_qmb:
            self._add_section("Benutzerverwaltung", UsersAdminWidget(self._container))
            self._add_section("Lizenzverwaltung", LicenseManagementWidget(self._container))
            self._add_section("Schulung", TrainingSettingsWidget(self._container))
        if role == "ADMIN":
            self._add_section("Workflow-Profile", WorkflowProfilesWidget(self._container))
            self._add_section("Modul-Einstellungen", ModuleSettingsWidget(self._container))
            self._add_section("Geplante Optionen", PlannedOptionsWidget())

    def _add_section(self, title: str, widget: QWidget) -> None:
        self._sections.append((title, widget))
        self._tabs.addTab(widget, title)


class SignatureSettingsDialog(QDialog):
    """Öffentlicher Dialog, der das Signatur-Einstellungs-Panel standalone öffnet."""

    def __init__(self, container: RuntimeContainer, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Signatur verwalten")
        self.resize(820, 700)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(SignatureSettingsWidget(container))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(scroll, stretch=1)
        layout.addWidget(buttons)


def _build(container: RuntimeContainer) -> QWidget:
    return SettingsAdminWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="platform.settings_admin",
            module_id="settings",
            title="Einstellungen",
            sort_order=50,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
