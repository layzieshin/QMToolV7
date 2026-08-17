"""Action bar visibility updates without requiring a profile-manager button."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from interfaces.pyqt.sections.action_bar import update_action_visibility


class ActionBarVisibilityTest(unittest.TestCase):
    def test_update_without_profile_manager_button(self) -> None:
        workflow = {"new": MagicMock(), "start": MagicMock()}
        top = {"refresh": MagicMock()}
        update_action_visibility(workflow, top, {"new"}, profile_manager_allowed=True)
        workflow["new"].setVisible.assert_called_once_with(True)
        workflow["new"].setEnabled.assert_called_once_with(True)
        workflow["start"].setVisible.assert_called_once_with(False)
        workflow["start"].setEnabled.assert_called_once_with(False)
        top["refresh"].setVisible.assert_not_called()

    def test_update_with_profile_manager_button(self) -> None:
        workflow = {"new": MagicMock()}
        profile = MagicMock()
        top = {"profile_manager": profile}
        update_action_visibility(workflow, top, set(), profile_manager_allowed=False)
        profile.setVisible.assert_called_once_with(False)
        profile.setEnabled.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
