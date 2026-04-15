from __future__ import annotations

import unittest

from modules.documents.contracts import DocumentVersionState
from modules.documents.service import DocumentsService


class DocumentsReleaseFilenameTest(unittest.TestCase):
    def test_build_released_filename_transliterates_umlauts(self) -> None:
        state = DocumentVersionState(document_id="VA-100", version=1, title="Pruefplan fuer Kühlung")
        filename = DocumentsService._build_released_filename(state)
        self.assertEqual(filename, "VA-100_Pruefplan_fuer_Kuehlung.pdf")

    def test_build_released_filename_uses_fallback_when_title_sanitizes_to_empty(self) -> None:
        state = DocumentVersionState(document_id="VA-101", version=1, title="!!!")
        filename = DocumentsService._build_released_filename(state)
        self.assertEqual(filename, "VA-101_Dokument.pdf")

    def test_build_released_filename_strips_outer_separators(self) -> None:
        state = DocumentVersionState(document_id="VA-102", version=1, title="   -- Plan 2026 --   ")
        filename = DocumentsService._build_released_filename(state)
        self.assertEqual(filename, "VA-102_Plan_2026.pdf")

    def test_build_released_filename_transliterates_mixed_umlauts_and_sharp_s(self) -> None:
        state = DocumentVersionState(document_id="VA-103", version=1, title="ÄÖÜ Prüfliste ß v2")
        filename = DocumentsService._build_released_filename(state)
        self.assertEqual(filename, "VA-103_AeOeUe_Pruefliste_ss_v2.pdf")


if __name__ == "__main__":
    unittest.main()

