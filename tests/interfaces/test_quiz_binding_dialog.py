from __future__ import annotations

import unittest
from datetime import datetime, timezone

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None

from interfaces.pyqt.widgets.quiz_binding_dialog import QuizBindingDialog
from modules.training.contracts import PendingQuizMapping


@unittest.skipIf(QApplication is None, "PyQt6 ist nicht installiert")
class QuizBindingDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_renders_and_returns_selection(self) -> None:
        pending = [
            PendingQuizMapping(
                import_id="abcdef123456",
                document_id="DOC-1",
                document_version=2,
                created_at=datetime.now(timezone.utc),
                question_count=8,
                document_title="Titel",
            )
        ]
        dlg = QuizBindingDialog(pending)
        selected = dlg.selected()
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual("DOC-1", selected.document_id)


if __name__ == "__main__":
    unittest.main()

