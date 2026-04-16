"""Session persistence for the usermanagement module (SRP split B3)."""
from __future__ import annotations

import json
from pathlib import Path

from .contracts import AuthenticatedUser
from .repository import UserRepository


class SessionStore:
    """Read/write the current-user session from a JSON file."""

    def __init__(self, session_file: Path | None, repository: UserRepository | None = None) -> None:
        self._session_file = session_file
        self._repository = repository

    def save(self, user: AuthenticatedUser) -> None:
        if self._session_file is None:
            return
        self._session_file.parent.mkdir(parents=True, exist_ok=True)
        self._session_file.write_text(
            json.dumps(
                {"user_id": user.user_id, "username": user.username, "role": user.role},
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if self._session_file is None:
            return
        if self._session_file.exists():
            self._session_file.unlink()

    def get_current_user(self) -> AuthenticatedUser | None:
        if self._session_file is None or not self._session_file.exists():
            return None
        data = json.loads(self._session_file.read_text(encoding="utf-8"))
        user_id = data.get("user_id")
        username = data.get("username")
        role = data.get("role")
        if not user_id or not username or not role:
            return None
        if self._repository is not None:
            user = self._repository.get_user(str(username))
            if user is not None:
                return user
        return AuthenticatedUser(user_id=str(user_id), username=str(username), role=str(role))

