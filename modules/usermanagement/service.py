from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope

from .contracts import AuthenticatedUser
from .password_crypto import is_password_hash, verify_password
from .repository import UserRepository


@dataclass
class UserManagementService:
    event_bus: object | None = None
    session_file: Path | None = None
    repository: UserRepository | None = None
    _users: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {
            "admin": ("admin", "Admin"),
            "qmb": ("qmb", "QMB"),
            "user": ("user", "User"),
        }
    )

    def authenticate(self, username: str, password: str) -> AuthenticatedUser | None:
        record: tuple[str, str, str] | None
        if self.repository is not None:
            record = self.repository.get_by_username(username)
        else:
            in_memory = self._users.get(username)
            record = (username, in_memory[0], in_memory[1]) if in_memory else None
        if record is None:
            self._publish_event("domain.usermanagement.auth.failed.v1", {"username": username, "reason": "unknown_user"})
            return None
        user_id, expected_password, role = record
        if not verify_password(expected_password, password):
            self._publish_event("domain.usermanagement.auth.failed.v1", {"username": username, "reason": "wrong_password"})
            return None
        if self.repository is not None and not is_password_hash(expected_password):
            self.repository.change_password(username, password)
        if self.repository is not None:
            user = self.repository.get_user(username) or AuthenticatedUser(user_id=user_id, username=username, role=role)
        else:
            user = AuthenticatedUser(user_id=user_id, username=username, role=role)
        if not user.is_active:
            self._publish_event("domain.usermanagement.auth.failed.v1", {"username": username, "reason": "inactive_user"})
            return None
        self._publish_event(
            "domain.usermanagement.auth.succeeded.v1",
            {"username": username, "role": role},
            actor_user_id=user.user_id,
        )
        return user

    def login(self, username: str, password: str) -> AuthenticatedUser | None:
        user = self.authenticate(username, password)
        if user is None:
            return None
        self._save_session_user(user)
        self._publish_event(
            "domain.usermanagement.session.login.v1",
            {"username": user.username, "role": user.role},
            actor_user_id=user.user_id,
        )
        return user

    def logout(self) -> None:
        existing = self.get_current_user()
        self._clear_session_user()
        self._publish_event(
            "domain.usermanagement.session.logout.v1",
            {"username": existing.username if existing else None},
            actor_user_id=existing.user_id if existing else None,
        )

    def get_current_user(self) -> AuthenticatedUser | None:
        if self.session_file is None or not self.session_file.exists():
            return None
        data = json.loads(self.session_file.read_text(encoding="utf-8"))
        user_id = data.get("user_id")
        username = data.get("username")
        role = data.get("role")
        if not user_id or not username or not role:
            return None
        if self.repository is not None:
            user = self.repository.get_user(str(username))
            if user is not None:
                return user
        return AuthenticatedUser(user_id=str(user_id), username=str(username), role=str(role))

    def list_users(self) -> list[AuthenticatedUser]:
        if self.repository is not None:
            return self.repository.list_users()
        return [
            AuthenticatedUser(user_id=username, username=username, role=role)
            for username, (_password, role) in sorted(self._users.items())
        ]

    def create_user(self, username: str, password: str, role: str) -> AuthenticatedUser:
        username = username.strip()
        password = password.strip()
        role = role.strip()
        if not username:
            raise ValueError("username is required")
        if not password:
            raise ValueError("password is required")
        if role not in ("Admin", "QMB", "User"):
            raise ValueError("role must be one of: Admin, QMB, User")
        if self.repository is not None:
            user = self.repository.create_user(username, password, role)
        else:
            if username in self._users:
                raise ValueError("user already exists")
            self._users[username] = (password, role)
            user = AuthenticatedUser(user_id=username, username=username, role=role)
        self._publish_event(
            "domain.usermanagement.user.created.v1",
            {"username": user.username, "role": user.role},
            actor_user_id=user.user_id,
        )
        return user

    def update_user_profile(self, username: str, *, display_name: str | None, email: str | None) -> AuthenticatedUser:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        if self.repository is None:
            existing = self._users.get(username)
            if existing is None:
                raise KeyError(f"unknown user: {username}")
            _password, role = existing
            return AuthenticatedUser(
                user_id=username,
                username=username,
                role=role,
                display_name=display_name,
                email=email,
            )
        return self.repository.update_user_profile(username, display_name=display_name, email=email)

    def update_user_admin_fields(
        self,
        username: str,
        *,
        department: str | None,
        scope: str | None,
        organization_unit: str | None,
        role: str | None,
        is_active: bool | None,
    ) -> AuthenticatedUser:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        if role is not None and role not in ("Admin", "QMB", "User"):
            raise ValueError("role must be one of: Admin, QMB, User")
        if self.repository is None:
            existing = self._users.get(username)
            if existing is None:
                raise KeyError(f"unknown user: {username}")
            password, current_role = existing
            new_role = role or current_role
            self._users[username] = (password, new_role)
            return AuthenticatedUser(
                user_id=username,
                username=username,
                role=new_role,
                department=department,
                scope=scope,
                organization_unit=organization_unit,
                is_active=is_active if is_active is not None else True,
            )
        return self.repository.update_user_admin_fields(
            username,
            department=department,
            scope=scope,
            organization_unit=organization_unit,
            role=role,
            is_active=is_active,
        )

    def set_user_active(self, username: str, is_active: bool) -> AuthenticatedUser:
        return self.update_user_admin_fields(
            username,
            department=None,
            scope=None,
            organization_unit=None,
            role=None,
            is_active=is_active,
        )

    def change_password(self, username: str, new_password: str) -> None:
        username = username.strip()
        new_password = new_password.strip()
        if not username:
            raise ValueError("username is required")
        if not new_password:
            raise ValueError("new_password is required")
        if self.repository is not None:
            self.repository.change_password(username, new_password)
            user = self.repository.get_by_username(username)
            actor_user_id = user[0] if user else None
        else:
            if username not in self._users:
                raise KeyError(f"unknown user: {username}")
            _old_password, role = self._users[username]
            self._users[username] = (new_password, role)
            actor_user_id = username
        self._publish_event(
            "domain.usermanagement.user.password_changed.v1",
            {"username": username},
            actor_user_id=actor_user_id,
        )

    def _save_session_user(self, user: AuthenticatedUser) -> None:
        if self.session_file is None:
            return
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(
            json.dumps(
                {"user_id": user.user_id, "username": user.username, "role": user.role},
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _clear_session_user(self) -> None:
        if self.session_file is None:
            return
        if self.session_file.exists():
            self.session_file.unlink()

    def _publish_event(self, name: str, payload: dict, actor_user_id: str | None = None) -> None:
        if self.event_bus is None:
            return
        publish = getattr(self.event_bus, "publish", None)
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

