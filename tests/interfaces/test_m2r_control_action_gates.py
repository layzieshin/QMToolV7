"""M2R.3 exact control gating by backend UI keys."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from datetime import datetime, timezone

from interfaces.pyqt.contributions.documents_workflow.core_mixin import DocumentsWorkflowCoreMixin
from interfaces.pyqt.presenters.documents_workflow_presenter import DocumentsWorkflowPresenter
from modules.documents.api import ControlClass, DocumentHeader, DocumentStatus, DocumentType, SystemRole


class _Button:
    def __init__(self, key: str) -> None:
        self._key = key
        self.visible = True
        self.enabled = True

    def property(self, name: str):
        return self._key if name == "qmtool_action_key" else None

    def setVisible(self, value: bool) -> None:
        self.visible = bool(value)

    def setEnabled(self, value: bool) -> None:
        self.enabled = bool(value)


class _Field:
    def __init__(self) -> None:
        self.readonly = False

    def setReadOnly(self, value: bool) -> None:
        self.readonly = bool(value)


class _GateProbe(DocumentsWorkflowCoreMixin):
    def __init__(self) -> None:
        self._um = MagicMock()
        self._um.get_current_user.return_value = SimpleNamespace(user_id="u1")
        self._presenter = DocumentsWorkflowPresenter()
        self._current_state = SimpleNamespace(
            status=DocumentStatus.IN_PROGRESS,
            available_actions=frozenset(
                {
                    "update_metadata",
                    "update_header",
                    "assign_roles",
                    "change_requests",
                    "comments",
                    "extend_validity",
                    "new_version",
                    "open_source",
                }
            ),
        )
        self._doc_id = _Field()
        self._version = _Field()
        self._title = _Field()
        self._description = _Field()
        self._doc_type = _Field()
        self._control_class = _Field()
        self._profile = _Field()
        self._department = _Field()
        self._site = _Field()
        self._regulatory_scope = _Field()
        self._valid_until = _Field()
        self._next_review = _Field()
        self._custom_fields = _Field()
        self._role_inputs = [_Field(), _Field(), _Field()]
        self._metadata_buttons = [
            _Button("update_metadata"),
            _Button("update_header"),
            _Button("change_requests"),
        ]
        self._roles_buttons = [_Button("assign_roles")]
        self._extension_buttons = [_Button("extend_validity"), _Button("new_version")]
        self._current_header = DocumentHeader(
            document_id="DOC-1",
            doc_type=DocumentType.OTHER,
            control_class=ControlClass.CONTROLLED,
            workflow_profile_id="p1",
            updated_at=datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc),
        )

    def _can_current_user_create_documents(self) -> bool:
        return False


class ControlGateTests(unittest.TestCase):
    def test_backend_actions_enable_exact_controls(self) -> None:
        probe = _GateProbe()
        visible = probe._presenter.visible_actions_for_context(
            probe._current_state,
            user_id="u1",
            user_role=SystemRole.USER,
        )
        self.assertIn("edit", visible)  # open_source
        self.assertIn("update_metadata", visible)
        self.assertIn("update_header", visible)
        self.assertIn("assign_roles", visible)
        self.assertIn("change_requests", visible)
        self.assertIn("comments", visible)
        self.assertIn("extend_validity", visible)
        self.assertIn("new_version", visible)
        probe._apply_editor_permissions(visible)
        self.assertTrue(probe._title.readonly is False)
        self.assertTrue(probe._profile.readonly is False)
        self.assertTrue(probe._doc_type.readonly is True)
        self.assertTrue(probe._control_class.readonly is True)
        self.assertTrue(all(b.enabled for b in probe._metadata_buttons))
        self.assertTrue(probe._roles_buttons[0].enabled)
        self.assertTrue(all(b.enabled for b in probe._extension_buttons))

    def test_missing_actions_lock_all_mutation_controls(self) -> None:
        probe = _GateProbe()
        probe._current_state.available_actions = None
        visible = probe._presenter.visible_actions_for_context(probe._current_state, user_id="u1")
        probe._apply_editor_permissions(visible)
        self.assertTrue(probe._title.readonly)
        self.assertTrue(probe._profile.readonly)
        self.assertTrue(probe._doc_type.readonly)
        self.assertFalse(any(b.enabled for b in probe._metadata_buttons))
        self.assertFalse(probe._roles_buttons[0].enabled)
        self.assertFalse(any(b.enabled for b in probe._extension_buttons))

    def test_core_mixin_has_no_is_qmb(self) -> None:
        self.assertFalse(hasattr(DocumentsWorkflowCoreMixin, "_is_qmb"))

    def test_header_controls_disabled_without_loaded_token(self) -> None:
        probe = _GateProbe()
        probe._current_header = None
        visible = probe._presenter.visible_actions_for_context(
            probe._current_state,
            user_id="u1",
            user_role=SystemRole.USER,
        )
        probe._apply_editor_permissions(visible)
        header_btn = next(b for b in probe._metadata_buttons if b.property("qmtool_action_key") == "update_header")
        self.assertFalse(header_btn.enabled)
        self.assertTrue(probe._profile.readonly)


if __name__ == "__main__":
    unittest.main()
