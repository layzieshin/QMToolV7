from __future__ import annotations

from PyQt6.QtCore import QSettings


class ShellPreferences:
    def __init__(self) -> None:
        self._settings = QSettings("QMTool", "QMToolV7")

    def load_admin_debug_toggle(self) -> bool:
        return bool(self._settings.value("shell/show_admin_debug", True, type=bool))

    def save_admin_debug_toggle(self, enabled: bool) -> None:
        self._settings.setValue("shell/show_admin_debug", enabled)
