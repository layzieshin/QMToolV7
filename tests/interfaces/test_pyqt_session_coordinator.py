"""J04-M0-P0: SessionCoordinator prefers backend_session_api."""
from __future__ import annotations

from dataclasses import dataclass

from interfaces.pyqt.shell.session_coordinator import SessionCoordinator


@dataclass
class _LocalUser:
    username: str
    user_id: str = "local-1"


class _LocalUm:
    def __init__(self) -> None:
        self.logged_in = False
        self.logout_calls = 0

    def login(self, username: str, password: str):
        self.logged_in = True
        return _LocalUser(username=username)

    def get_current_user(self):
        return _LocalUser(username="local") if self.logged_in else None

    def logout(self) -> None:
        self.logout_calls += 1
        self.logged_in = False


class _BackendSession:
    def __init__(self) -> None:
        self._user = None
        self.logout_calls = 0
        self.clear_calls = 0

    def login(self, username: str, password: str):
        self._user = _LocalUser(username=f"backend:{username}", user_id="be-1")
        return self._user

    def current_user(self):
        return self._user

    def logout(self) -> None:
        self.logout_calls += 1
        self._user = None

    def clear(self) -> None:
        self.clear_calls += 1
        self._user = None

    def change_password(self, new_password: str):
        assert new_password
        return self._user


def test_coordinator_uses_backend_when_bound() -> None:
    um = _LocalUm()
    backend = _BackendSession()
    coord = SessionCoordinator(um, backend_session=backend)
    assert coord.uses_backend_session is True
    user = coord.login("bob", "secret")
    assert user.username == "backend:bob"
    assert coord.current_user().user_id == "be-1"
    assert um.logged_in is False
    coord.force_logged_out()
    assert backend.logout_calls == 1
    assert um.logout_calls == 0


def test_coordinator_falls_back_to_local_um() -> None:
    um = _LocalUm()
    coord = SessionCoordinator(um)
    assert coord.uses_backend_session is False
    user = coord.login("alice", "x")
    assert user.username == "alice"
    coord.force_logged_out()
    assert um.logout_calls == 1


def test_change_password_delegates_to_backend() -> None:
    backend = _BackendSession()
    backend.login("admin", "admin")
    coord = SessionCoordinator(_LocalUm(), backend_session=backend)
    assert coord.change_password("newpass01") is backend.current_user()
