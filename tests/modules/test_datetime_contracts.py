from __future__ import annotations

import unittest

from modules.documents.contracts import DocumentHeader
from modules.documents.contracts import control_class_for
from modules.documents.contracts import DocumentType
from modules.training.contracts import TrainingAssignment, TrainingAssignmentStatus, TrainingCategory


class DateTimeContractsTest(unittest.TestCase):
    def test_document_header_defaults_are_timezone_aware(self) -> None:
        header = DocumentHeader(
            document_id="DOC-TZ-1",
            doc_type=DocumentType.VA,
            control_class=control_class_for(DocumentType.VA),
            workflow_profile_id="long_release",
        )
        self.assertIsNotNone(header.created_at.tzinfo)
        self.assertIsNotNone(header.updated_at.tzinfo)

    def test_training_contract_defaults_are_timezone_aware(self) -> None:
        category = TrainingCategory(category_id="cat-1", name="Category 1")
        self.assertIsNotNone(category.created_at.tzinfo)
        assignment = TrainingAssignment(
            assignment_id="a-1",
            user_id="u-1",
            document_id="DOC-TZ-2",
            version=1,
            category_id="cat-1",
            status=TrainingAssignmentStatus.ASSIGNED,
            active=True,
        )
        self.assertIsNotNone(assignment.created_at.tzinfo)
        self.assertIsNotNone(assignment.updated_at.tzinfo)


if __name__ == "__main__":
    unittest.main()
