from __future__ import annotations

from abc import ABC, abstractmethod

from .contracts import SessionRecord


class SessionRepository(ABC):
    """Persistence port for opaque server-side sessions (token hash only)."""

    @abstractmethod
    def save(self, session: SessionRecord) -> None:
        """Insert or replace a session record."""

    @abstractmethod
    def get_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        """Lookup by stored token hash."""

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> SessionRecord | None:
        """Lookup by session id."""

    @abstractmethod
    def list_for_user(self, user_id: str) -> list[SessionRecord]:
        """All sessions (including revoked/expired) belonging to a user.

        Required by revoke-all-for-user; implementations may filter later
        for cleanup jobs but must return every match for revocation safety.
        """

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Remove a session record (optional hard delete; prefer revoke in ops)."""
