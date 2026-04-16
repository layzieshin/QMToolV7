"""§15.1 G: Comment service tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.training.contracts import CommentStatus
from .conftest_helpers import make_full_stack


class TestTrainingCommentService(unittest.TestCase):
    def test_comment_initial_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            c = s["comment_svc"].add_comment("user", "DOC-1", 1, "Test")
            self.assertEqual(c.status, CommentStatus.ACTIVE)

    def test_active_comments_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["comment_svc"].add_comment("user", "DOC-1", 1, "C1")
            s["comment_svc"].add_comment("user", "DOC-1", 1, "C2")
            active = s["comment_svc"].list_active_comments()
            self.assertEqual(len(active), 2)

    def test_resolved_not_in_active_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            c = s["comment_svc"].add_comment("user", "DOC-1", 1, "C1")
            s["comment_svc"].resolve_comment(c.comment_id, "qmb")
            active = s["comment_svc"].list_active_comments()
            self.assertEqual(len(active), 0)

    def test_inactive_not_in_active_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            c = s["comment_svc"].add_comment("user", "DOC-1", 1, "C1")
            s["comment_svc"].inactivate_comment(c.comment_id, "admin")
            active = s["comment_svc"].list_active_comments()
            self.assertEqual(len(active), 0)

    def test_comment_events_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            c = s["comment_svc"].add_comment("user", "DOC-1", 1, "C1")
            s["comment_svc"].resolve_comment(c.comment_id, "qmb")
            names = s["bus"].event_names()
            self.assertIn("domain.training.comment.created.v1", names)
            self.assertIn("domain.training.comment.resolved.v1", names)


if __name__ == "__main__":
    unittest.main()

