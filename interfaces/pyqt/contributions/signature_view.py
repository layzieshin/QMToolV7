from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.widgets.signature_sign_wizard import SignatureSignWizard
from qm_platform.runtime.container import RuntimeContainer


class SignatureWorkspace(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._api = container.get_port("signature_api")
        self._um = container.get_port("usermanagement_service")
        self._audit = container.get_port("audit_logger") if container.has_port("audit_logger") else None
        self._settings = container.get_port("settings_service") if container.has_port("settings_service") else None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        self._btn_sign = QPushButton("Dokument signieren")
        self._btn_sign.clicked.connect(self._open_sign_wizard)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_sign)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)
        outer.addStretch(1)

    def _open_sign_wizard(self) -> None:
        wizard = SignatureSignWizard(
            signature_api=self._api,
            usermanagement_service=self._um,
            settings_service=self._settings,
            audit_logger=self._audit,
            manage_signature_callback=self._open_manage,
            parent=self,
        )
        if wizard.exec() == wizard.DialogCode.Accepted:
            QMessageBox.information(self, "Signieren", f"Signieren abgeschlossen:\n{wizard.result_payload()}")

    def _open_manage(self) -> None:
        from interfaces.pyqt.contributions.settings_view import SignatureSettingsDialog
        dialog = SignatureSettingsDialog(self._container, parent=self)
        dialog.exec()


def _build(container: RuntimeContainer) -> QWidget:
    return SignatureWorkspace(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="signature.workspace",
            module_id="signature",
            title="Signatur",
            sort_order=30,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin", "QMB", "User"),
        )
    ]
