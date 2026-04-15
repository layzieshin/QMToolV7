from __future__ import annotations

import unittest

from interfaces.pyqt.widgets.document_create_wizard import parse_document_id_and_title_from_filename


class DocumentCreateWizardParserTest(unittest.TestCase):
    def test_parse_document_id_and_title_from_filename(self) -> None:
        document_id, title = parse_document_id_and_title_from_filename("C:/tmp/VA-123_Pruefung_ueber_Aenderung.docx")
        self.assertEqual(document_id, "VA-123")
        self.assertEqual(title, "Pruefung ueber Aenderung")

    def test_parse_ignores_invalid_filename_without_separator(self) -> None:
        document_id, title = parse_document_id_and_title_from_filename("C:/tmp/KeinSeparator.docx")
        self.assertEqual(document_id, "")
        self.assertEqual(title, "")


if __name__ == "__main__":
    unittest.main()

