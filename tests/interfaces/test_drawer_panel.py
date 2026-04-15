from __future__ import annotations

import unittest

try:
    from PyQt6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QApplication = None

from interfaces.pyqt.widgets.drawer_panel import DrawerPanel


@unittest.skipIf(QApplication is None, "PyQt6 ist nicht installiert")
class DrawerPanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_set_open_syncs_toggle_and_visibility(self) -> None:
        panel = DrawerPanel("Details")
        self.assertFalse(panel.is_open())
        self.assertFalse(panel.toggle_button().isChecked())

        panel.set_open(True)
        self.assertTrue(panel.is_open())
        self.assertTrue(panel.toggle_button().isChecked())

        panel.setVisible(False)
        self.assertFalse(panel.is_open())
        self.assertFalse(panel.toggle_button().isChecked())


if __name__ == "__main__":
    unittest.main()

