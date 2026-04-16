"""§15.1 B: Document tag tests."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .conftest_helpers import make_full_stack


class TestDocumentTagService(unittest.TestCase):
    def test_set_and_read_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            result = s["doc_tag_svc"].set_document_tags("DOC-1", ["safety", "quality"])
            self.assertEqual(result.tags, frozenset(["safety", "quality"]))
            read = s["doc_tag_svc"].list_document_tags("DOC-1")
            self.assertEqual(read.tags, frozenset(["safety", "quality"]))

    def test_empty_tags_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = make_full_stack(Path(tmp))
            read = s["doc_tag_svc"].list_document_tags("NONEXISTENT")
            self.assertEqual(read.tags, frozenset())


if __name__ == "__main__":
    unittest.main()

