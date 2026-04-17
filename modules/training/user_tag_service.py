"""User tag management (§3.4)."""
from __future__ import annotations

from .contracts import UserTagSet
from .training_tag_repository import TrainingTagRepository


class UserTagService:
    def __init__(self, *, tag_repo: TrainingTagRepository) -> None:
        self._repo = tag_repo

    def list_user_tags(self, user_id: str) -> UserTagSet:
        return self._repo.get_user_tags(user_id)

    def set_user_tags(self, user_id: str, tags: list[str]) -> UserTagSet:
        return self._repo.set_user_tags(user_id, tags)

    def list_all_user_tags(self) -> list[UserTagSet]:
        return self._repo.list_all_user_tags()

    def list_tag_pool(self) -> list[str]:
        return self._repo.list_tag_pool()

