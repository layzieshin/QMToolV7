from __future__ import annotations


class SessionCoordinator:
    def __init__(self, usermanagement_service: object) -> None:
        self._um = usermanagement_service

    def force_logged_out(self) -> None:
        try:
            self._um.logout()
        except Exception:
            pass

    def current_user(self):
        try:
            return self._um.get_current_user()
        except Exception:
            return None

    def login(self, username: str, password: str):
        return self._um.login(username, password)
