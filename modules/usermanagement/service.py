from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope

from .auth_ops import AuthOps
from .contracts import AuthenticatedUser, IssuedSession, UserContext
from .password_policy import DEFAULT_PASSWORD_POLICY, PasswordPolicy, validate_password
from .repository import UserRepository
from .session_ops import SessionOps
from .session_repository import SessionRepository
from .session_store import SessionStore
from .user_admin_ops import UserAdminOps


@dataclass
class UserManagementService:
    event_bus: object | None = None
    session_file: Path | None = None
    repository: UserRepository | None = None
    session_repository: SessionRepository | None = None
    password_policy: PasswordPolicy = field(default_factory=lambda: DEFAULT_PASSWORD_POLICY)
    _users: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {
            "admin": ("admin", "Admin"),
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
            password_policy=self.password_policy,
        )
        self._session_ops: SessionOps | None = None
        if self.session_repository is not None:
            self._session_ops = SessionOps(
                session_repository=self.session_repository,
                users=_ServiceUserByIdLookup(self),
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

    # -- Opaque server-side sessions (AP-028) --------------------------------

    def create_session(
        self,
        user: AuthenticatedUser,
        *,
        client_type: str,
        lifetime=None,
        now=None,
        authentication_level: str = "password",
    ) -> IssuedSession:
        return self._require_session_ops().create_session(
            user,
            client_type=client_type,
            lifetime=lifetime,
            now=now,
            authentication_level=authentication_level,
        )

    def resolve_session(
        self,
        raw_token: str | None,
        *,
        request_id: str,
        now=None,
        password_change_allowed: bool = False,
        touch: bool = True,
    ) -> UserContext:
        return self._require_session_ops().resolve_session(
            raw_token,
            request_id=request_id,
            now=now,
            password_change_allowed=password_change_allowed,
            touch=touch,
        )

    def revoke_session(self, *, session_id: str | None = None, raw_token: str | None = None, now=None):
        return self._require_session_ops().revoke_session(
            session_id=session_id,
            raw_token=raw_token,
            now=now,
        )

    def revoke_all_sessions_for_user(self, user_id: str, *, now=None):
        return self._require_session_ops().revoke_all_for_user(user_id, now=now)

    def _require_session_ops(self) -> SessionOps:
        if self._session_ops is None:
            raise RuntimeError("opaque session repository is not configured")
        return self._session_ops

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
        is_qmb: bool | None = None,
    ) -> AuthenticatedUser:
        return self._admin_ops.update_user_admin_fields(
            username,
            department=department,
            scope=scope,
            organization_unit=organization_unit,
            role=role,
            is_active=is_active,
            is_qmb=is_qmb,
        )

    def set_user_active(self, username: str, is_active: bool) -> AuthenticatedUser:
        return self._admin_ops.set_user_active(username, is_active)

    def set_user_qmb(self, username: str, is_qmb: bool) -> AuthenticatedUser:
        return self._admin_ops.set_user_qmb(username, is_qmb)

    def self_register(
        self,
        username: str,
        password: str,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> AuthenticatedUser:
        return self._admin_ops.self_register(
            username,
            password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

    def change_password(self, username: str, new_password: str) -> None:
        self._admin_ops.change_password(username, new_password)

    def ensure_admin_credentials(self, username: str, password: str, role: str = "Admin") -> AuthenticatedUser:
        return self._admin_ops.ensure_admin_credentials(username, password, role)

    def bootstrap_first_admin(self, username: str, password: str) -> AuthenticatedUser | None:
        """Create the first Admin with must_change_password when no users exist.

        Returns ``None`` when users already exist (idempotent no-op for operators).
        """
        if self.list_users():
            return None
        if self.repository is None:
            raise RuntimeError("user repository is not configured")
        validate_password(password, self.password_policy)
        return self.repository.ensure_initial_admin(
            username,
            password,
            role="Admin",
            must_change_password=True,
        )

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


class _ServiceUserByIdLookup:
    def __init__(self, service: UserManagementService) -> None:
        self._service = service

    def get_user_by_id(self, user_id: str) -> AuthenticatedUser | None:
        if self._service.repository is not None:
            for user in self._service.repository.list_users():
                if user.user_id == user_id:
                    return user
            return None
        entry = self._service._users.get(user_id)
        if entry is None:
            return None
        _password, role = entry
        return AuthenticatedUser(user_id=user_id, username=user_id, role=role)
