from __future__ import annotations

import unittest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None

from interfaces.pyqt.contributions.home_view import HomeDashboardWidget
from qm_platform.runtime.container import RuntimeContainer


class _User:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.username = "user"
        self.role = "User"
        self.is_active = True
        self.is_qmb = False


class _UM:
    def get_current_user(self):
        return _User()

    def list_users(self):
        return []


class _AvailablePool:
    def list_tasks_for_user(self, *args, **kwargs):
        return []

    def list_review_actions_for_user(self, *args, **kwargs):
        return []

    def list_recent_documents_for_user(self, *args, **kwargs):
        return []


@unittest.skipIf(QApplication is None, "PyQt6 ist nicht installiert")
class HomeFailClosedDocumentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_home_loads_available_documents_http_reads(self) -> None:
        container = RuntimeContainer()
        container.register_port("usermanagement_service", _UM())
        container.register_port("documents_pool_api", _AvailablePool())
        widget = HomeDashboardWidget(container)
        self.assertEqual(len(widget._cards), 6)


if __name__ == "__main__":
    unittest.main()
