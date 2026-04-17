from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None

from interfaces.pyqt.widgets.register_dialog import RegisterDialog


class _Svc:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def self_register(self, username, password, **kwargs):
        self.calls.append((username, password, kwargs))


@unittest.skipIf(QApplication is None, "PyQt6 ist nicht installiert")
class RegisterDialogFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_register_calls_service(self) -> None:
        svc = _Svc()
        dlg = RegisterDialog(svc)
        dlg._username.setText("user1")
        dlg._password.setText("pw")
        dlg._password_confirm.setText("pw")
        dlg._first_name.setText("Max")
        dlg._last_name.setText("Mustermann")
        dlg._email.setText("max@example.org")
        with patch("interfaces.pyqt.widgets.register_dialog.QMessageBox.information"):
            dlg._register()
        self.assertEqual(1, len(svc.calls))
        self.assertEqual("user1", svc.calls[0][0])


if __name__ == "__main__":
    unittest.main()

