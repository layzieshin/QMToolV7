from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.widgets.debug_panel import DebugPanel
from qm_platform.runtime.container import RuntimeContainer


class AdminDebugWidget(QWidget):
    def __init__(self, container: RuntimeContainer) -> None:
        super().__init__()
        self._container = container
        self._out = DebugPanel()

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Admin/Debug bündelt technische Rohdaten (Runtime, Pfade, Ports, Lizenz), "
            "damit Fachoberflächen schlank bleiben."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        reload_btn = QPushButton("Debug-Daten aktualisieren")
        reload_btn.clicked.connect(self._reload)
        layout.addWidget(reload_btn)
        layout.addWidget(self._out, stretch=1)
        self._reload()

    def _reload(self) -> None:
        app_home = Path(self._container.get_port("app_home"))
        license_service = self._container.get_port("license_service")
        payload = {
            "app_home": str(app_home),
            "ports": sorted(list(getattr(self._container, "_ports", {}).keys())),
            "license_validation": license_service.validate(),
            "has_ports": {
                "event_bus": self._container.has_port("event_bus"),
                "audit_logger": self._container.has_port("audit_logger"),
                "settings_service": self._container.has_port("settings_service"),
            },
        }
        self._out.set_payload(payload)


def _build(container: RuntimeContainer) -> QWidget:
    return AdminDebugWidget(container)


def contributions() -> list[QtModuleContribution]:
    return [
        QtModuleContribution(
            contribution_id="platform.admin_debug",
            module_id="platform",
            title="Admin/Debug",
            sort_order=70,
            factory=_build,
            requires_login=True,
            allowed_roles=("Admin",),
        )
    ]
