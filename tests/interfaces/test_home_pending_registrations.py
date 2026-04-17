from __future__ import annotations

import unittest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None

from interfaces.pyqt.contributions.home_view import HomeDashboardWidget
from qm_platform.runtime.container import RuntimeContainer


class _User:
    def __init__(self, user_id: str, username: str, role: str, is_active: bool = True) -> None:
        self.user_id = user_id
        self.username = username
        self.role = role
        self.is_active = is_active
        self.is_qmb = False


class _UM:
    def __init__(self, current) -> None:
        self._current = current

    def get_current_user(self):
        return self._current

    def list_users(self):
        return [self._current, _User("u2", "inactive", "User", is_active=False)]


class _Pool:
    def list_tasks_for_user(self, *args, **kwargs):
        return []

    def list_review_actions_for_user(self, *args, **kwargs):
        return []

    def list_recent_documents_for_user(self, *args, **kwargs):
        return []


class _Training:
    def list_training_inbox_for_user(self, *args, **kwargs):
        return []


@unittest.skipIf(QApplication is None, "PyQt6 ist nicht installiert")
class HomePendingRegistrationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_admin_sees_pending_registrations_card(self) -> None:
        container = RuntimeContainer()
        container.register_port("usermanagement_service", _UM(_User("a1", "admin", "Admin")))
        container.register_port("documents_pool_api", _Pool())
        container.register_port("training_api", _Training())
        widget = HomeDashboardWidget(container)
        self.assertFalse(widget._cards["admin_pending_registrations"].isHidden())


if __name__ == "__main__":
    unittest.main()

