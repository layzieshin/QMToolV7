from __future__ import annotations

from .contracts import SessionRecord
from .session_repository import SessionRepository


class InMemorySessionRepository(SessionRepository):
    """Test/dev session store. Not a production persistence path."""

    def __init__(self) -> None:
        self._by_id: dict[str, SessionRecord] = {}
        self._hash_index: dict[str, str] = {}

    def save(self, session: SessionRecord) -> None:
        previous = self._by_id.get(session.session_id)
        if previous is not None and previous.token_hash in self._hash_index:
            del self._hash_index[previous.token_hash]
        self._by_id[session.session_id] = session
        self._hash_index[session.token_hash] = session.session_id

    def get_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        session_id = self._hash_index.get(token_hash)
        if session_id is None:
            return None
        return self._by_id.get(session_id)

    def get_by_session_id(self, session_id: str) -> SessionRecord | None:
        return self._by_id.get(session_id)

    def delete(self, session_id: str) -> None:
        existing = self._by_id.pop(session_id, None)
        if existing is not None:
            self._hash_index.pop(existing.token_hash, None)

    def list_for_user(self, user_id: str) -> list[SessionRecord]:
        return [session for session in self._by_id.values() if session.user_id == user_id]
