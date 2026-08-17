from __future__ import annotations

from interfaces.pyqt.logging_adapter import get_logger


class SessionCoordinator:
    """PyQt session boundary.

    When ``backend_session`` is provided (J04-M0 product path), identity and
    authentication go exclusively through ``/auth/*``. Local Usermanagement
    login and ``current_user.json`` are not used for the product session.
    """

    def __init__(
        self,
        usermanagement_service: object,
        *,
        backend_session: object | None = None,
    ) -> None:
        self._um = usermanagement_service
        self._backend = backend_session
        self._log = get_logger(__name__)

    @property
    def uses_backend_session(self) -> bool:
        return self._backend is not None

    def force_logged_out(self) -> None:
        if self._backend is not None:
            try:
                self._backend.logout()
            except Exception:  # noqa: BLE001
                self._log.exception("Backend logout during force_logged_out failed")
                try:
                    self._backend.clear()
                except Exception:  # noqa: BLE001
                    self._log.exception("Backend session clear failed")
            return
        try:
            self._um.logout()
        except Exception:  # noqa: BLE001
            self._log.exception("Logout during force_logged_out failed")

    def current_user(self):
        if self._backend is not None:
            try:
                return self._backend.current_user()
            except Exception:  # noqa: BLE001
                self._log.exception("Reading backend current user failed")
                return None
        try:
            return self._um.get_current_user()
        except Exception:  # noqa: BLE001
            self._log.exception("Reading current user failed")
            return None

    def login(self, username: str, password: str):
        if self._backend is not None:
            return self._backend.login(username, password)
        return self._um.login(username, password)

    def change_password(self, new_password: str):
        if self._backend is not None:
            return self._backend.change_password(new_password)
        raise RuntimeError("local password change must use usermanagement_service directly")
