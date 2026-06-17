"""Base widget for incident_management workspace sections."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QMessageBox, QVBoxLayout, QWidget

from interfaces.pyqt.presenters.incident_management_presenter import IncidentManagementPresenter
from qm_platform.runtime.container import RuntimeContainer


class BaseIncidentArea(QWidget):
    def __init__(self, container: RuntimeContainer, *, title: str) -> None:
        super().__init__()
        self._container = container
        self._presenter = IncidentManagementPresenter()
        self._um = container.get_port("usermanagement_service")
        self._layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        self._layout.addWidget(heading)

    def layout(self) -> QVBoxLayout:  # noqa: A003
        return self._layout

    def _api(self):
        if not self._container.has_port("incident_management_api"):
            raise RuntimeError("incident_management_api not available")
        return self._container.get_port("incident_management_api")

    def _current_user(self):
        return self._um.get_current_user()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        """Override in subclasses."""

    @staticmethod
    def show_error(parent: QWidget, title: str, exc: BaseException) -> None:
        QMessageBox.warning(parent, title, str(exc))

    @staticmethod
    def show_info(parent: QWidget, title: str, message: str) -> None:
        QMessageBox.information(parent, title, message)
