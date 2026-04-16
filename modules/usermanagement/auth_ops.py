"""Authentication operations for the usermanagement module (SRP split B3)."""
from __future__ import annotations

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import AuthenticatedUser
from .password_crypto import is_password_hash, verify_password
from .repository import UserRepository
from .session_store import SessionStore


class AuthOps:
    """Authenticate, login, logout and password-hash audit."""

    def __init__(
        self,
        repository: UserRepository | None,
        session_store: SessionStore,
        event_bus: object | None = None,
        fallback_users: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self._repository = repository
        self._session = session_store
        self._event_bus = event_bus
        self._fallback_users = fallback_users or {}

    # -- public API ----------------------------------------------------------

    def authenticate(self, username: str, password: str) -> AuthenticatedUser | None:
        record: tuple[str, str, str] | None
        if self._repository is not None:
            record = self._repository.get_by_username(username)
        else:
            in_memory = self._fallback_users.get(username)
            record = (username, in_memory[0], in_memory[1]) if in_memory else None
        if record is None:
            self._publish("domain.usermanagement.auth.failed.v1", {"username": username, "reason": "unknown_user"})
            return None
        user_id, expected_password, role = record
        if not verify_password(expected_password, password):
            self._publish("domain.usermanagement.auth.failed.v1", {"username": username, "reason": "wrong_password"})
            return None
        if self._repository is not None and not is_password_hash(expected_password):
            self._repository.change_password(username, password)
        if self._repository is not None:
            user = self._repository.get_user(username) or AuthenticatedUser(user_id=user_id, username=username, role=role)
        else:
            user = AuthenticatedUser(user_id=user_id, username=username, role=role)
        if not user.is_active:
            self._publish("domain.usermanagement.auth.failed.v1", {"username": username, "reason": "inactive_user"})
            return None
        self._publish(
            "domain.usermanagement.auth.succeeded.v1",
            {"username": username, "role": role},
            actor_user_id=user.user_id,
        )
        return user

    def login(self, username: str, password: str) -> AuthenticatedUser | None:
        user = self.authenticate(username, password)
        if user is None:
            return None
        self._session.save(user)
        self._publish(
            "domain.usermanagement.session.login.v1",
            {"username": user.username, "role": user.role},
            actor_user_id=user.user_id,
        )
        return user

    def logout(self) -> None:
        existing = self._session.get_current_user()
        self._session.clear()
        self._publish(
            "domain.usermanagement.session.logout.v1",
            {"username": existing.username if existing else None},
            actor_user_id=existing.user_id if existing else None,
        )

    def all_passwords_hashed(self) -> bool:
        if self._repository is not None:
            from .password_crypto import is_password_hash as _is_hash
            rows = [
                entry
                for user in (self._repository.list_users())
                if (entry := self._repository.get_by_username(user.username)) is not None
            ]
            if not rows:
                return False
            return all(_is_hash(str(row[1])) for row in rows)
        if not self._fallback_users:
            return False
        return all(is_password_hash(password) for password, _role in self._fallback_users.values())

    # -- internal ------------------------------------------------------------

    def _publish(self, name: str, payload: dict, actor_user_id: str | None = None) -> None:
        if self._event_bus is None:
            return
        publish = getattr(self._event_bus, "publish", None)
        if not callable(publish):
            return
        publish(
            EventEnvelope.create(
                name=name,
                module_id="usermanagement",
                payload=payload,
                actor_user_id=actor_user_id,
            )
        )

