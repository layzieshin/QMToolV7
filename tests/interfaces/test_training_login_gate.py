from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None

from interfaces.pyqt.contributions.home_view import HomeDashboardWidget
from interfaces.pyqt.contributions.training_placeholder import TrainingWorkspace
from modules.training.contracts import AssignmentSource, TrainingInboxItem
from qm_platform.runtime.container import RuntimeContainer


class _FakeUser:
    def __init__(self, user_id: str, username: str, role: str, *, is_qmb: bool = False) -> None:
        self.user_id = user_id
        self.username = username
        self.role = role
        self.is_qmb = is_qmb


class _FakeUserManagement:
    def __init__(self, user=None) -> None:
        self._user = user

    def get_current_user(self):
        return self._user


class _FakeTrainingApi:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def list_training_inbox_for_user(self, user_id: str, open_only: bool = False):
        self.calls.append(("list_training_inbox_for_user", user_id, open_only))
        return [
            TrainingInboxItem(
                document_id="DOC-1",
                version=1,
                title="Testdokument",
                status="SCOPE",
                owner_user_id="admin",
                released_at=None,
                read_confirmed=False,
                quiz_available=False,
                quiz_passed=False,
                source=AssignmentSource.SCOPE,
            )
        ]

    def start_quiz(self, user_id: str, document_id: str, version: int):  # pragma: no cover - not used here
        raise AssertionError("start_quiz should not be called")

    def add_comment(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("add_comment should not be called")

    def list_comments_for_document(self, *args, **kwargs):
        return []


class _FakeTrainingAdminApi:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_training_statistics(self):
        self.calls.append("get_training_statistics")
        raise AssertionError("Admin API should not be called without admin rights")

    def __getattr__(self, name):
        def _fn(*args, **kwargs):
            self.calls.append(name)
            return []

        return _fn


class _FakeReadApi:
    def open_released_document_for_training(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("read api should not be called")

    def confirm_released_document_read(self, *args, **kwargs):  # pragma: no cover - not used here
        raise AssertionError("read api should not be called")


class _FakeDocsPool:
    def list_tasks_for_user(self, *args, **kwargs):
        return []

    def list_review_actions_for_user(self, *args, **kwargs):
        return []

    def list_recent_documents_for_user(self, *args, **kwargs):
        return []


def _make_container(user=None) -> RuntimeContainer:
    container = RuntimeContainer()
    container.register_port("usermanagement_service", _FakeUserManagement(user))
    container.register_port("training_api", _FakeTrainingApi())
    container.register_port("training_admin_api", _FakeTrainingAdminApi())
    container.register_port("documents_read_api", _FakeReadApi())
    container.register_port("documents_pool_api", _FakeDocsPool())
    return container


@unittest.skipIf(QApplication is None, "PyQt6 ist nicht installiert")
class TrainingLoginGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_training_workspace_constructs_without_login(self) -> None:
        widget = TrainingWorkspace(_make_container(user=None))
        self.assertFalse(widget._admin_bar.isVisible())
        self.assertEqual(widget._table.rowCount(), 0)
        self.assertIn("Anmeldung erforderlich", widget._out.toPlainText())

    def test_training_workspace_refreshes_after_login(self) -> None:
        container = _make_container(user=None)
        widget = TrainingWorkspace(container)
        container.get_port("usermanagement_service")._user = _FakeUser("u1", "user", "User")
        widget.refresh_for_session()
        self.assertEqual(widget._table.rowCount(), 1)
        self.assertNotIn("Anmeldung erforderlich", widget._out.toPlainText())

    def test_admin_action_without_admin_rights_is_guarded_before_admin_api_call(self) -> None:
        container = _make_container(user=_FakeUser("u1", "user", "User"))
        widget = TrainingWorkspace(container)
        admin_api = container.get_port("training_admin_api")
        with patch("interfaces.pyqt.contributions.training_placeholder.QMessageBox.warning") as warning:
            widget._on_statistics()
        self.assertEqual(admin_api.calls, [])
        self.assertTrue(warning.called)

    def test_home_dashboard_constructs_without_login(self) -> None:
        widget = HomeDashboardWidget(_make_container(user=None))
        self.assertEqual(len(widget._cards), 6)


if __name__ == "__main__":
    unittest.main()



