from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock

from .contracts import SessionRecord
from .session_repository import SessionRepository


class InMemorySessionRepository(SessionRepository):
    """Test/dev session store. Not a production persistence path."""

    def __init__(self) -> None:
        self._by_id: dict[str, SessionRecord] = {}
        self._hash_index: dict[str, str] = {}
        self._lock = RLock()

    def add(self, session: SessionRecord) -> None:
        with self._lock:
            if session.session_id in self._by_id:
                raise ValueError("session_id already exists")
            if session.token_hash in self._hash_index:
                raise ValueError("token_hash already exists")
            self._by_id[session.session_id] = session
            self._hash_index[session.token_hash] = session.session_id

    def get_by_token_hash(self, token_hash: str) -> SessionRecord | None:
        with self._lock:
            session_id = self._hash_index.get(token_hash)
            if session_id is None:
                return None
            return self._by_id.get(session_id)

    def get_by_session_id(self, session_id: str) -> SessionRecord | None:
        with self._lock:
            return self._by_id.get(session_id)

    def delete(self, session_id: str) -> None:
        with self._lock:
            existing = self._by_id.pop(session_id, None)
            if existing is not None:
                self._hash_index.pop(existing.token_hash, None)

    def list_for_user(self, user_id: str) -> list[SessionRecord]:
        with self._lock:
            return [session for session in self._by_id.values() if session.user_id == user_id]

    def touch(self, session_id: str, last_seen_at: datetime) -> SessionRecord | None:
        with self._lock:
            existing = self._by_id.get(session_id)
            if existing is None or existing.revoked_at is not None:
                return existing
            if last_seen_at <= existing.last_seen_at:
                return existing
            updated = replace(existing, last_seen_at=last_seen_at)
            self._by_id[session_id] = updated
            return updated

    def revoke(self, session_id: str, revoked_at: datetime) -> SessionRecord | None:
        with self._lock:
            existing = self._by_id.get(session_id)
            if existing is None or existing.revoked_at is not None:
                return existing
            revoked = replace(existing, revoked_at=revoked_at)
            self._by_id[session_id] = revoked
            return revoked

    def revoke_all_for_user(self, user_id: str, revoked_at: datetime) -> list[SessionRecord]:
        with self._lock:
            revoked_sessions: list[SessionRecord] = []
            for session_id, session in tuple(self._by_id.items()):
                if session.user_id != user_id or session.revoked_at is not None:
                    continue
                revoked = replace(session, revoked_at=revoked_at)
                self._by_id[session_id] = revoked
                revoked_sessions.append(revoked)
            return revoked_sessions
