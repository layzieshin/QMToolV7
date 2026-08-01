from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from qm_platform.events.event_envelope import EventEnvelope

from .auth_ops import AuthOps
from .contracts import AuthenticatedUser, IssuedSession, UserContext
from .errors import (
    AuthorizationError,
    InvalidSessionError,
    InvalidUserUpdateError,
    LastActiveAdminError,
    UserNotFoundError,
)
from .password_policy import DEFAULT_PASSWORD_POLICY, PasswordPolicy, validate_password
from .postgres_connection import runtime_connection
from .postgres_session_repository import PostgresSessionRepository
from .postgres_user_repository import PostgresUserRepository
from .repository import UserRepository
from .role_policies import normalize_base_role
from .session_ops import SessionOps
from .session_repository import SessionRepository
from .session_store import SessionStore
from .user_admin_ops import UserAdminOps


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_admin_user(user: AuthenticatedUser) -> bool:
    return normalize_base_role(user.role) == "ADMIN"


def _require_admin_actor(actor: UserContext) -> None:
    if not actor.is_confirmed:
        raise InvalidSessionError("user context is not server-confirmed")
    if "ADMIN" not in actor.global_roles:
        raise AuthorizationError("admin role required")


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

    def revoke_other_sessions_for_user(self, user_id: str, keep_session_id: str, *, now=None):
        return self._require_session_ops().revoke_other_sessions_for_user(
            user_id, keep_session_id, now=now
        )

    def revoke_all_own_sessions(self, context: UserContext, *, now=None):
        if not context.is_confirmed:
            raise InvalidSessionError("user context is not server-confirmed")
        return self.revoke_all_sessions_for_user(context.user_id, now=now)

    def change_own_password(self, context: UserContext, new_password: str, *, now=None) -> None:
        """Change password, keep current session, revoke all other sessions (M6)."""
        if not context.is_confirmed:
            raise InvalidSessionError("user context is not server-confirmed")
        cleaned = new_password.strip() if isinstance(new_password, str) else ""
        validate_password(cleaned, self.password_policy)
        moment = now or _utc_now()
        user_repo = self.repository
        session_repo = self.session_repository
        if isinstance(user_repo, PostgresUserRepository) and isinstance(
            session_repo, PostgresSessionRepository
        ):
            with runtime_connection(user_repo._dsn) as conn:
                PostgresUserRepository.change_password_on_connection(
                    conn, context.username, cleaned
                )
                PostgresSessionRepository.revoke_other_sessions_for_user_on_connection(
                    conn,
                    context.user_id,
                    context.session_id,
                    moment,
                )
            self._publish_event(
                "domain.usermanagement.user.password_changed.v1",
                {"username": context.username},
                actor_user_id=context.user_id,
            )
            return
        self._admin_ops.change_password(context.username, cleaned)
        self.revoke_other_sessions_for_user(
            context.user_id, context.session_id, now=moment
        )

    def _require_session_ops(self) -> SessionOps:
        if self._session_ops is None:
            raise RuntimeError("opaque session repository is not configured")
        return self._session_ops

    def list_users(self) -> list[AuthenticatedUser]:
        return self._admin_ops.list_users()

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "User",
        *,
        is_qmb: bool = False,
        must_change_password: bool = False,
    ) -> AuthenticatedUser:
        return self._admin_ops.create_user(
            username,
            password,
            role,
            is_qmb=is_qmb,
            must_change_password=must_change_password,
        )

    def create_user_as_admin(
        self,
        actor: UserContext,
        username: str,
        password: str,
        *,
        role: str = "User",
        is_qmb: bool = False,
        must_change_password: bool = True,
    ) -> AuthenticatedUser:
        _require_admin_actor(actor)
        return self.create_user(
            username,
            password,
            role,
            is_qmb=is_qmb,
            must_change_password=must_change_password,
        )

    def update_user_access_as_admin(
        self,
        actor: UserContext,
        username: str,
        *,
        role: str | None = None,
        is_qmb: bool | None = None,
        is_active: bool | None = None,
    ) -> AuthenticatedUser:
        _require_admin_actor(actor)
        if role is None and is_qmb is None and is_active is None:
            raise InvalidUserUpdateError("at least one of role, is_qmb, is_active is required")
        return self._apply_user_access_change(
            username,
            department=None,
            scope=None,
            organization_unit=None,
            role=role,
            is_active=is_active,
            is_qmb=is_qmb,
        )

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
        """Desktop/CLI access updates share last-admin and deactivate+revoke rules."""
        return self._apply_user_access_change(
            username,
            department=department,
            scope=scope,
            organization_unit=organization_unit,
            role=role,
            is_active=is_active,
            is_qmb=is_qmb,
        )

    def set_user_active(self, username: str, is_active: bool) -> AuthenticatedUser:
        return self._apply_user_access_change(
            username,
            department=None,
            scope=None,
            organization_unit=None,
            role=None,
            is_active=is_active,
            is_qmb=None,
        )

    def _apply_user_access_change(
        self,
        username: str,
        *,
        department: str | None,
        scope: str | None,
        organization_unit: str | None,
        role: str | None,
        is_active: bool | None,
        is_qmb: bool | None,
    ) -> AuthenticatedUser:
        username = username.strip()
        if not username:
            raise InvalidUserUpdateError("username is required")
        current = self._get_user_or_raise(username)
        next_role = role if role is not None else current.role
        next_active = bool(current.is_active if is_active is None else is_active)
        self._assert_not_last_active_admin(
            current,
            next_role=next_role,
            next_active=next_active,
        )
        becoming_inactive = current.is_active and not next_active
        user_repo = self.repository
        session_repo = self.session_repository
        if isinstance(user_repo, PostgresUserRepository):
            with runtime_connection(user_repo._dsn) as conn:
                updated = PostgresUserRepository.update_user_admin_fields_on_connection(
                    conn,
                    username,
                    department=department,
                    scope=scope,
                    organization_unit=organization_unit,
                    role=role,
                    is_active=is_active,
                    is_qmb=is_qmb,
                )
                if becoming_inactive:
                    if not isinstance(session_repo, PostgresSessionRepository):
                        raise RuntimeError(
                            "opaque session repository is required to deactivate PostgreSQL users"
                        )
                    PostgresSessionRepository.revoke_all_for_user_on_connection(
                        conn, updated.user_id, _utc_now()
                    )
            return updated

        updated = self._admin_ops.update_user_admin_fields(
            username,
            department=department,
            scope=scope,
            organization_unit=organization_unit,
            role=role,
            is_active=is_active,
            is_qmb=is_qmb,
        )
        if becoming_inactive and self._session_ops is not None:
            self.revoke_all_sessions_for_user(updated.user_id)
        return updated

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
        if self.list_users():
            return None
        if self.repository is None:
            raise RuntimeError("user repository is not configured")
        cleaned = password.strip() if isinstance(password, str) else ""
        validate_password(cleaned, self.password_policy)
        return self.repository.ensure_initial_admin(
            username,
            cleaned,
            role="Admin",
            must_change_password=True,
        )

    def _get_user_or_raise(self, username: str) -> AuthenticatedUser:
        if self.repository is not None:
            user = self.repository.get_user(username)
            if user is None:
                raise UserNotFoundError(f"unknown user: {username}")
            return user
        for user in self.list_users():
            if user.username == username:
                return user
        raise UserNotFoundError(f"unknown user: {username}")

    def _assert_not_last_active_admin(
        self,
        current: AuthenticatedUser,
        *,
        next_role: str,
        next_active: bool,
    ) -> None:
        if not _is_admin_user(current) or not current.is_active:
            return
        demoting = normalize_base_role(next_role) != "ADMIN"
        deactivating = not next_active
        if not demoting and not deactivating:
            return
        other_active_admins = [
            user
            for user in self.list_users()
            if user.user_id != current.user_id and user.is_active and _is_admin_user(user)
        ]
        if not other_active_admins:
            raise LastActiveAdminError("cannot remove the last active admin")

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
