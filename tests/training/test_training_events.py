"""§15.1 H: Event tests – events published after commit."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .conftest_helpers import make_full_stack, SAMPLE_QUIZ_JSON


class TestTrainingEvents(unittest.TestCase):
    def test_import_publishes_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            self.assertIn("domain.training.quiz.imported.v1", s["bus"].event_names())

    def test_binding_publishes_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            r = s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            s["quiz_binding"].bind_quiz_to_document(r.import_id, "DOC-1", 1)
            self.assertIn("domain.training.quiz.binding.created.v1", s["bus"].event_names())

    def test_manual_assignment_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            ma = s["manual_svc"].grant_manual_assignment("user", "DOC-1", "reason", "admin")
            self.assertIn("domain.training.manual_assignment.granted.v1", s["bus"].event_names())
            s["manual_svc"].revoke_manual_assignment(ma.assignment_id, "admin")
            self.assertIn("domain.training.manual_assignment.revoked.v1", s["bus"].event_names())

    def test_exemption_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            ex = s["exemption_svc"].grant_exemption("user", "DOC-1", 1, "reason", "admin")
            self.assertIn("domain.training.exemption.granted.v1", s["bus"].event_names())
            s["exemption_svc"].revoke_exemption(ex.exemption_id, "admin")
            self.assertIn("domain.training.exemption.revoked.v1", s["bus"].event_names())

    def test_snapshot_rebuild_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["projector"].rebuild_all()
            self.assertIn("domain.training.assignment.snapshot.rebuilt.v1", s["bus"].event_names())

    def test_snapshot_created_and_updated_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["manual_svc"].grant_manual_assignment("user", "DOC-1", "reason", "admin")
            s["projector"].rebuild_all()
            self.assertIn("domain.training.assignment.snapshot.created.v1", s["bus"].event_names())
            # second rebuild updates an existing key (same user/doc/version)
            s["projector"].rebuild_all()
            self.assertIn("domain.training.assignment.snapshot.updated.v1", s["bus"].event_names())

    def test_comment_status_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            c = s["comment_svc"].add_comment("user", "DOC-1", 1, "text")
            self.assertIn("domain.training.comment.created.v1", s["bus"].event_names())
            s["comment_svc"].inactivate_comment(c.comment_id, "admin")
            self.assertIn("domain.training.comment.inactivated.v1", s["bus"].event_names())

    def test_event_envelope_has_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            s["quiz_import"].import_quiz_json(SAMPLE_QUIZ_JSON)
            event = s["bus"].events[0]
            self.assertTrue(hasattr(event, "event_id"))
            self.assertTrue(hasattr(event, "name"))
            self.assertTrue(hasattr(event, "occurred_at_utc"))
            self.assertTrue(hasattr(event, "module_id"))
            self.assertTrue(hasattr(event, "payload"))


if __name__ == "__main__":
    unittest.main()

