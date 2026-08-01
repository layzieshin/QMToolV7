from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from .contracts import SessionRecord


class SessionRepository(ABC):
    """Persistence port for opaque server-side sessions (token hash only)."""

    @abstractmethod
    def add(self, session: SessionRecord) -> None:
        """Insert a new session; identifiers and token hashes must be unique."""

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
    def touch(self, session_id: str, last_seen_at: datetime) -> SessionRecord | None:
        """Atomically update an active session without clearing a concurrent revocation.

        Return the current record, including ``revoked_at`` when a revocation won
        the race, or ``None`` when the session no longer exists.
        """

    @abstractmethod
    def revoke(self, session_id: str, revoked_at: datetime) -> SessionRecord | None:
        """Atomically revoke one session and return its current record."""

    @abstractmethod
    def revoke_all_for_user(self, user_id: str, revoked_at: datetime) -> list[SessionRecord]:
        """Atomically revoke all sessions currently belonging to a user."""

    @abstractmethod
    def revoke_other_sessions_for_user(
        self,
        user_id: str,
        keep_session_id: str,
        revoked_at: datetime,
    ) -> list[SessionRecord]:
        """Revoke all active sessions for a user except ``keep_session_id``."""

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Remove a session record (optional hard delete; prefer revoke in ops)."""
