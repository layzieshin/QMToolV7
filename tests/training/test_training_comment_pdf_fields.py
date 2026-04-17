from __future__ import annotations

from pathlib import Path

from modules.training.training_comment_repository import TrainingCommentRepository
from modules.training.training_comment_service import TrainingCommentService


def test_training_pdf_comment_fields_roundtrip(tmp_path: Path) -> None:
    repo = TrainingCommentRepository(tmp_path / "training.db", Path("modules/training/schema.sql"))
    service = TrainingCommentService(comment_repo=repo)
    created = service.add_pdf_comment(
        "u1",
        "VA-1",
        1,
        page_number=3,
        comment_text="Bitte Abschnitt pruefen",
        anchor_json='{"x": 10}',
    )
    items = service.list_pdf_comments_for_user("u1", "VA-1", 1)
    assert len(items) == 1
    assert items[0].page_number == 3
    assert items[0].anchor_json == '{"x": 10}'
    assert created.page_number == 3
