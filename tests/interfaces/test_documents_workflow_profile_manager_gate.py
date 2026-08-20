"""Gate for Documents workflow profile-manager button visibility."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from interfaces.pyqt.contributions.documents_workflow.core_mixin import DocumentsWorkflowCoreMixin
from modules.documents.contracts import SystemRole


class _Probe(DocumentsWorkflowCoreMixin):
    def __init__(self, um, current_state=None) -> None:
        self._um = um
        self._current_state = current_state
        self._pool = MagicMock()
        self._pool.get_capabilities.return_value = {
            "can_administer_workflow_profiles": um.get_current_user.return_value is not None
            and getattr(um.get_current_user.return_value, "role", "") == "QMB"
        }


class DocumentsWorkflowProfileManagerGateTest(unittest.TestCase):
    def test_denied_without_user(self) -> None:
        um = MagicMock()
        um.get_current_user.return_value = None
        self.assertFalse(_Probe(um)._is_profile_manager_allowed())

    def test_allowed_for_qmb(self) -> None:
        um = MagicMock()
        um.get_current_user.return_value = SimpleNamespace(user_id="u1", role="QMB")
        self.assertTrue(_Probe(um)._is_profile_manager_allowed())

    def test_owner_is_not_a_profile_manager(self) -> None:
        um = MagicMock()
        um.get_current_user.return_value = SimpleNamespace(user_id="owner-1", role="USER")
        state = SimpleNamespace(owner_user_id="owner-1")
        self.assertFalse(_Probe(um, state)._is_profile_manager_allowed())

    def test_denied_for_non_owner_without_selection(self) -> None:
        um = MagicMock()
        um.get_current_user.return_value = SimpleNamespace(user_id="author-1", role="USER")
        self.assertFalse(_Probe(um)._is_profile_manager_allowed())


if __name__ == "__main__":
    unittest.main()
