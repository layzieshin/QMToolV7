"""§15.2: GUI permissions / presenter tests."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from modules.training.contracts import AssignmentSource, TrainingInboxItem
from interfaces.pyqt.presenters.training_presenter import TrainingPresenter


def _item(*, read_confirmed=False, quiz_available=False, quiz_passed=False) -> TrainingInboxItem:
    return TrainingInboxItem(
        document_id="DOC-1", version=1, title="T", status="SCOPE",
        owner_user_id="admin", released_at=None,
        read_confirmed=read_confirmed, quiz_available=quiz_available,
        quiz_passed=quiz_passed, source=AssignmentSource.SCOPE,
    )


class TestTrainingGuiPermissions(unittest.TestCase):
    @dataclass
    class _User:
        role: str
        is_qmb: bool = False

    def test_admin_bar_visible_for_admin(self):
        self.assertTrue(TrainingPresenter.is_admin(self._User("Admin")))
        self.assertTrue(TrainingPresenter.is_admin(self._User("QMB")))
        self.assertTrue(TrainingPresenter.is_admin(self._User("User", is_qmb=True)))

    def test_admin_bar_hidden_for_user(self):
        self.assertFalse(TrainingPresenter.is_admin(self._User("User")))
        self.assertFalse(TrainingPresenter.is_admin(self._User("")))

    def test_read_enabled_when_not_confirmed(self):
        self.assertTrue(TrainingPresenter.is_read_enabled(_item(read_confirmed=False)))

    def test_read_disabled_when_already_confirmed(self):
        self.assertFalse(TrainingPresenter.is_read_enabled(_item(read_confirmed=True)))

    def test_read_disabled_when_no_selection(self):
        self.assertFalse(TrainingPresenter.is_read_enabled(None))

    def test_quiz_start_enabled(self):
        self.assertTrue(TrainingPresenter.is_quiz_start_enabled(
            _item(read_confirmed=True, quiz_available=True, quiz_passed=False)))

    def test_quiz_start_disabled_when_not_read(self):
        self.assertFalse(TrainingPresenter.is_quiz_start_enabled(
            _item(read_confirmed=False, quiz_available=True)))

    def test_quiz_start_disabled_when_no_quiz(self):
        self.assertFalse(TrainingPresenter.is_quiz_start_enabled(
            _item(read_confirmed=True, quiz_available=False)))

    def test_quiz_start_disabled_when_already_passed(self):
        self.assertFalse(TrainingPresenter.is_quiz_start_enabled(
            _item(read_confirmed=True, quiz_available=True, quiz_passed=True)))

    def test_comment_enabled_when_attempted(self):
        self.assertTrue(TrainingPresenter.is_comment_enabled(_item(), quiz_attempted=True))

    def test_comment_disabled_when_not_attempted(self):
        self.assertFalse(TrainingPresenter.is_comment_enabled(_item(), quiz_attempted=False))

    def test_comment_disabled_when_no_selection(self):
        self.assertFalse(TrainingPresenter.is_comment_enabled(None, quiz_attempted=True))

    def test_filter_rows_open_only(self):
        items = [
            _item(quiz_passed=True),
            _item(quiz_passed=False),
        ]
        filtered = TrainingPresenter.filter_rows(items, open_only=True)
        self.assertEqual(len(filtered), 1)
        self.assertFalse(filtered[0].quiz_passed)

    def test_filter_rows_all(self):
        items = [_item(quiz_passed=True), _item(quiz_passed=False)]
        self.assertEqual(len(TrainingPresenter.filter_rows(items, open_only=False)), 2)


if __name__ == "__main__":
    unittest.main()

