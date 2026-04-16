"""Document tag management (§3.3)."""
from __future__ import annotations

from .contracts import DocumentTagSet
from .training_tag_repository import TrainingTagRepository


class DocumentTagService:
    def __init__(self, *, tag_repo: TrainingTagRepository) -> None:
        self._repo = tag_repo

    def list_document_tags(self, document_id: str) -> DocumentTagSet:
        return self._repo.get_document_tags(document_id)

    def set_document_tags(self, document_id: str, tags: list[str]) -> DocumentTagSet:
        return self._repo.set_document_tags(document_id, tags)

    def list_all_document_tags(self) -> list[DocumentTagSet]:
        return self._repo.list_all_document_tags()

