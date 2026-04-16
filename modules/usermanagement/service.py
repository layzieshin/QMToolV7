from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope

from .auth_ops import AuthOps
from .contracts import AuthenticatedUser
from .password_crypto import is_password_hash, verify_password
from .repository import UserRepository
from .session_store import SessionStore
from .user_admin_ops import UserAdminOps


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

    def __post_init__(self) -> None:
        self._session_store = SessionStore(self.session_file, self.repository)
        self._auth_ops = AuthOps(
            repository=self.repository,
            session_store=self._session_store,
            event_bus=self.event_bus,
            fallback_users=self._users,
        )
        self._admin_ops = UserAdminOps(
            repository=self.repository,
            event_bus=self.event_bus,
            fallback_users=self._users,
        )

    # -- Auth delegation -----------------------------------------------------

    def authenticate(self, username: str, password: str) -> AuthenticatedUser | None:
        return self._auth_ops.authenticate(username, password)

    def login(self, username: str, password: str) -> AuthenticatedUser | None:
        return self._auth_ops.login(username, password)

    def logout(self) -> None:
        self._auth_ops.logout()

    def get_current_user(self) -> AuthenticatedUser | None:
        return self._session_store.get_current_user()

    def all_passwords_hashed(self) -> bool:
        return self._auth_ops.all_passwords_hashed()

    # -- Admin delegation ----------------------------------------------------

    def list_users(self) -> list[AuthenticatedUser]:
        return self._admin_ops.list_users()

    def create_user(self, username: str, password: str, role: str) -> AuthenticatedUser:
        return self._admin_ops.create_user(username, password, role)

    def update_user_profile(
        self,
        username: str,
        *,
        first_name: str | None,
        last_name: str | None,
        email: str | None,
        display_name: str | None = None,
    ) -> AuthenticatedUser:
        return self._admin_ops.update_user_profile(
            username, first_name=first_name, last_name=last_name, email=email, display_name=display_name,
        )

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
        return self._admin_ops.update_user_admin_fields(
            username, department=department, scope=scope, organization_unit=organization_unit, role=role, is_active=is_active,
        )

    def set_user_active(self, username: str, is_active: bool) -> AuthenticatedUser:
        return self._admin_ops.set_user_active(username, is_active)

    def change_password(self, username: str, new_password: str) -> None:
        self._admin_ops.change_password(username, new_password)

    def ensure_admin_credentials(self, username: str, password: str, role: str = "Admin") -> AuthenticatedUser:
        return self._admin_ops.ensure_admin_credentials(username, password, role)

    # -- Legacy private methods kept for backward compat ---------------------

    def _save_session_user(self, user: AuthenticatedUser) -> None:
        self._session_store.save(user)

    def _clear_session_user(self) -> None:
        self._session_store.clear()

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

