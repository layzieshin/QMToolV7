from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.training.api import TrainingAdminApi
from modules.training.contracts import QuizImportResult, TrainingDocumentRef
from modules.training.quiz_binding_service import QuizBindingService
from modules.training.training_quiz_repository import TrainingQuizRepository


class _CatalogStub:
    def list_released_documents(self):
        return [
            TrainingDocumentRef(
                document_id="DOC-1",
                version=1,
                title="Dokument Eins",
                owner_user_id="owner",
            )
        ]


class _Noop:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: []  # noqa: ARG005


class TrainingPendingQuizMappingTest(unittest.TestCase):
    def test_pending_mapping_contains_question_count_and_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = TrainingQuizRepository(
                db_path=Path(tmp) / "training.db",
                schema_path=Path("modules/training/schema.sql"),
            )
            repo.create_quiz_import(
                QuizImportResult(
                    import_id="imp-1",
                    document_id="DOC-1",
                    document_version=1,
                    question_count=12,
                    auto_bound=False,
                ),
                storage_key="x",
                sha256="y",
            )
            admin_api = TrainingAdminApi(
                catalog_reader=_CatalogStub(),
                quiz_import=_Noop(),
                quiz_binding=QuizBindingService(quiz_repo=repo),
                doc_tag_service=_Noop(),
                user_tag_service=_Noop(),
                manual_service=_Noop(),
                exemption_service=_Noop(),
                projector=_Noop(),
                comment_service=_Noop(),
                report_service=_Noop(),
            )
            rows = admin_api.list_pending_quiz_mappings()
            self.assertEqual(1, len(rows))
            self.assertEqual(12, rows[0].question_count)
            self.assertEqual("Dokument Eins", rows[0].document_title)


if __name__ == "__main__":
    unittest.main()

