from __future__ import annotations

from interfaces.pyqt.logging_adapter import get_logger


class SessionCoordinator:
    def __init__(self, usermanagement_service: object) -> None:
        self._um = usermanagement_service
        self._log = get_logger(__name__)

    def force_logged_out(self) -> None:
        try:
            self._um.logout()
        except Exception:  # noqa: BLE001
            self._log.exception("Logout during force_logged_out failed")

    def current_user(self):
        try:
            return self._um.get_current_user()
        except Exception:  # noqa: BLE001
            self._log.exception("Reading current user failed")
            return None

    def login(self, username: str, password: str):
        return self._um.login(username, password)
