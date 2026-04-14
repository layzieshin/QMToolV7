from __future__ import annotations

import unittest

from interfaces.pyqt.presenters.settings_policy_presenter import SettingsPolicyPresenter


class SettingsPolicySmokeTest(unittest.TestCase):
    def test_privileged_roles(self) -> None:
        presenter = SettingsPolicyPresenter()
        self.assertTrue(presenter.is_privileged("ADMIN"))
        self.assertTrue(presenter.is_privileged("QMB"))
        self.assertFalse(presenter.is_privileged("USER"))

    def test_governance_ack_summary(self) -> None:
        presenter = SettingsPolicyPresenter()
        self.assertIn("gesetzt", presenter.summarize_governance_ack(acknowledged=True))
        self.assertIn("fehlt", presenter.summarize_governance_ack(acknowledged=False))


if __name__ == "__main__":
    unittest.main()
