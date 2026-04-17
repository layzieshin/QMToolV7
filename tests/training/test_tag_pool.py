from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .conftest_helpers import make_full_stack


class TestTagPool(unittest.TestCase):
    def test_tag_pool_collects_user_and_document_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stack = make_full_stack(Path(tmp))
            doc_tags = stack["doc_tag_svc"]
            user_tags = stack["user_tag_svc"]

            doc_tags.set_document_tags("DOC-1", ["safety", "quality"])
            user_tags.set_user_tags("user-1", ["quality", "onboarding"])

            self.assertEqual(doc_tags.list_tag_pool(), ["onboarding", "quality", "safety"])
            self.assertEqual(user_tags.list_tag_pool(), ["onboarding", "quality", "safety"])

    def test_tag_pool_keeps_previous_values_after_reassignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stack = make_full_stack(Path(tmp))
            doc_tags = stack["doc_tag_svc"]

            doc_tags.set_document_tags("DOC-1", ["legacy"])
            doc_tags.set_document_tags("DOC-1", ["updated"])

            self.assertEqual(doc_tags.list_tag_pool(), ["legacy", "updated"])


if __name__ == "__main__":
    unittest.main()
