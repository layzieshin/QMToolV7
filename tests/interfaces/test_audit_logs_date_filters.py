from __future__ import annotations

import unittest

try:
    from PyQt6.QtWidgets import QApplication, QDateEdit
except Exception:  # pragma: no cover
    QApplication = None
    QDateEdit = None

from interfaces.pyqt.contributions.audit_logs_view import AuditLogsWidget


@unittest.skipIf(QApplication is None or QDateEdit is None, "PyQt6 ist nicht installiert")
class AuditLogsDateFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_date_range_helper_returns_utc_window(self) -> None:
        from_edit = QDateEdit()
        to_edit = QDateEdit()
        AuditLogsWidget._setup_date_editors(from_edit, to_edit)
        start, end = AuditLogsWidget._date_range_utc(from_edit, to_edit)
        self.assertIsNotNone(start.tzinfo)
        self.assertIsNotNone(end.tzinfo)
        self.assertLess(start, end)


if __name__ == "__main__":
    unittest.main()
