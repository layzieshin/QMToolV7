from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from qm_platform.events.event_envelope import EventEnvelope

from .auth_ops import AuthOps
from .contracts import AuthenticatedUser, IssuedSession, SessionRecord, UserContext
from .errors import (
    AuthenticationError,
    AuthorizationError,
    ExpiredSessionError,
    InvalidSessionError,
    InvalidUserUpdateError,
    LastActiveAdminError,
    SessionNotFoundError,
    UserExistsError,
    UserNotFoundError,
)
from .password_crypto import is_password_hash, verify_password
from .password_policy import DEFAULT_PASSWORD_POLICY, PasswordPolicy, validate_password
from .postgres_audit_repository import (
    ACTOR_ANONYMOUS,
    ACTOR_SYSTEM,
    ACTOR_USER,
    CLIENT_BACKEND,
    EVENT_LOGIN_DENIED,
    EVENT_LOGIN_SUCCEEDED,
    EVENT_LOGOUT_ALL_SUCCEEDED,
    EVENT_LOGOUT_SUCCEEDED,
    EVENT_SESSION_EXPIRED,
    EVENT_USER_ACCESS_CHANGED,
    EVENT_USER_CREATED,
    EVENT_USER_PASSWORD_CHANGED,
    RESULT_DENIED,
    RESULT_SUCCEEDED,
    SYSTEM_ACTOR_SESSION_EXPIRY,
    AuditEventWrite,
    PostgresAuditRepository,
)
from .postgres_connection import runtime_connection
from .postgres_session_repository import PostgresSessionRepository
from .postgres_user_repository import PostgresUserRepository
from .repository import UserRepository
from .role_policies import normalize_base_role
from .session_ops import DEFAULT_SESSION_LIFETIME, SessionOps
from .session_repository import SessionRepository
from .session_store import SessionStore
from .session_token import generate_session_token, hash_session_token
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


def _uses_postgres_backend(
    repository: UserRepository | None,
    session_repository: SessionRepository | None,
) -> bool:
    return isinstance(repository, PostgresUserRepository) and isinstance(
        session_repository, PostgresSessionRepository
    )


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

    def login_backend(
        self,
        username: str,
        password: str,
        *,
        request_id: str,
        now=None,
    ) -> IssuedSession:
        """Authenticate, issue a backend session, and write PG audit in one TX."""
        if not request_id:
            raise ValueError("request_id is required")
        if not _uses_postgres_backend(self.repository, self.session_repository):
            user = self.authenticate(username, password)
            if user is None:
                raise AuthenticationError("invalid credentials")
            return self.create_session(user, client_type=CLIENT_BACKEND, now=now)
        assert isinstance(self.repository, PostgresUserRepository)
        assert isinstance(self.session_repository, PostgresSessionRepository)
        moment = now or _utc_now()
        deny_reason: str | None = None
        with runtime_connection(self.repository._dsn) as conn:
            record = PostgresUserRepository.get_by_username_on_connection(conn, username)
            if record is None:
                PostgresAuditRepository.insert_on_connection(
                    conn,
                    AuditEventWrite(
                        event_type=EVENT_LOGIN_DENIED,
                        result=RESULT_DENIED,
                        actor_kind=ACTOR_ANONYMOUS,
                        reason_code="unknown_user",
                        request_id=request_id,
                        occurred_at=moment,
                    ),
                )
                deny_reason = "unknown_user"
            else:
                user_id, expected_password, _role = record
                if not verify_password(expected_password, password):
                    PostgresAuditRepository.insert_on_connection(
                        conn,
                        AuditEventWrite(
                            event_type=EVENT_LOGIN_DENIED,
                            result=RESULT_DENIED,
                            actor_kind=ACTOR_ANONYMOUS,
                            reason_code="wrong_password",
                            request_id=request_id,
                            target_user_id=user_id,
                            occurred_at=moment,
                        ),
                    )
                    deny_reason = "wrong_password"
                else:
                    if not is_password_hash(expected_password):
                        PostgresUserRepository.change_password_on_connection(
                            conn, username, password
                        )
                    user = PostgresUserRepository.get_user_on_connection(conn, username)
                    if user is None or not user.is_active:
                        PostgresAuditRepository.insert_on_connection(
                            conn,
                            AuditEventWrite(
                                event_type=EVENT_LOGIN_DENIED,
                                result=RESULT_DENIED,
                                actor_kind=ACTOR_ANONYMOUS,
                                reason_code="inactive_user",
                                request_id=request_id,
                                target_user_id=user_id,
                                occurred_at=moment,
                            ),
                        )
                        deny_reason = "inactive_user"
                    else:
                        raw_token = generate_session_token()
                        session = SessionRecord(
                            session_id=str(uuid4()),
                            token_hash=hash_session_token(raw_token),
                            user_id=user.user_id,
                            created_at=moment,
                            last_seen_at=moment,
                            expires_at=moment + DEFAULT_SESSION_LIFETIME,
                            client_type=CLIENT_BACKEND,
                            authentication_level="password",
                            revoked_at=None,
                        )
                        PostgresSessionRepository.add_on_connection(conn, session)
                        PostgresAuditRepository.insert_on_connection(
                            conn,
                            AuditEventWrite(
                                event_type=EVENT_LOGIN_SUCCEEDED,
                                result=RESULT_SUCCEEDED,
                                actor_kind=ACTOR_USER,
                                request_id=request_id,
                                actor_user_id=user.user_id,
                                actor_session_id=session.session_id,
                                target_user_id=user.user_id,
                                target_session_id=session.session_id,
                                occurred_at=moment,
                            ),
                        )
                        return IssuedSession(raw_token=raw_token, session=session)
        # Denied audits must commit before the authentication error is raised.
        assert deny_reason is not None
        raise AuthenticationError("invalid credentials")


    def logout_backend(
        self,
        *,
        raw_token: str,
        request_id: str,
        now=None,
    ) -> None:
        """Revoke a presented session without must_change blocking; audit first revoke only."""
        if not request_id:
            raise ValueError("request_id is required")
        if raw_token is None or not str(raw_token).strip():
            raise InvalidSessionError("session token is missing")
        if not _uses_postgres_backend(self.repository, self.session_repository):
            self.revoke_session(raw_token=raw_token, now=now)
            return
        assert isinstance(self.repository, PostgresUserRepository)
        assert isinstance(self.session_repository, PostgresSessionRepository)
        moment = now or _utc_now()
        token_hash = hash_session_token(str(raw_token))
        with runtime_connection(self.repository._dsn) as conn:
            session = PostgresSessionRepository.get_by_token_hash_on_connection(conn, token_hash)
            if session is None:
                raise SessionNotFoundError("session not found")
            if session.revoked_at is not None:
                return
            revoked = PostgresSessionRepository.revoke_on_connection(
                conn, session.session_id, moment
            )
            if revoked is None or revoked.revoked_at is None:
                raise SessionNotFoundError("session not found")
            PostgresAuditRepository.insert_on_connection(
                conn,
                AuditEventWrite(
                    event_type=EVENT_LOGOUT_SUCCEEDED,
                    result=RESULT_SUCCEEDED,
                    actor_kind=ACTOR_USER,
                    request_id=request_id,
                    actor_user_id=session.user_id,
                    actor_session_id=session.session_id,
                    target_user_id=session.user_id,
                    target_session_id=session.session_id,
                    occurred_at=moment,
                ),
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
        try:
            return self._require_session_ops().resolve_session(
                raw_token,
                request_id=request_id,
                now=now,
                password_change_allowed=password_change_allowed,
                touch=touch,
            )
        except ExpiredSessionError:
            self._record_session_expired_audit(raw_token, request_id=request_id, now=now)
            raise

    def _record_session_expired_audit(
        self,
        raw_token: str | None,
        *,
        request_id: str,
        now=None,
    ) -> None:
        if not _uses_postgres_backend(self.repository, self.session_repository):
            return
        if raw_token is None or not str(raw_token).strip():
            return
        assert isinstance(self.repository, PostgresUserRepository)
        assert isinstance(self.session_repository, PostgresSessionRepository)
        moment = now or _utc_now()
        token_hash = hash_session_token(str(raw_token))
        with runtime_connection(self.repository._dsn) as conn:
            session = PostgresSessionRepository.get_by_token_hash_on_connection(conn, token_hash)
            if session is None:
                return
            PostgresAuditRepository.insert_on_connection(
                conn,
                AuditEventWrite(
                    event_type=EVENT_SESSION_EXPIRED,
                    result=RESULT_SUCCEEDED,
                    actor_kind=ACTOR_SYSTEM,
                    system_actor=SYSTEM_ACTOR_SESSION_EXPIRY,
                    request_id=request_id,
                    target_user_id=session.user_id,
                    target_session_id=session.session_id,
                    occurred_at=moment,
                ),
                on_conflict_do_nothing=True,
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
        moment = now or _utc_now()
        if _uses_postgres_backend(self.repository, self.session_repository):
            assert isinstance(self.repository, PostgresUserRepository)
            assert isinstance(self.session_repository, PostgresSessionRepository)
            with runtime_connection(self.repository._dsn) as conn:
                revoked = PostgresSessionRepository.revoke_all_for_user_on_connection(
                    conn, context.user_id, moment
                )
                PostgresAuditRepository.insert_on_connection(
                    conn,
                    AuditEventWrite(
                        event_type=EVENT_LOGOUT_ALL_SUCCEEDED,
                        result=RESULT_SUCCEEDED,
                        actor_kind=ACTOR_USER,
                        request_id=context.request_id,
                        actor_user_id=context.user_id,
                        actor_session_id=context.session_id,
                        target_user_id=context.user_id,
                        affected_session_count=len(revoked),
                        occurred_at=moment,
                    ),
                )
                return revoked
        return self.revoke_all_sessions_for_user(context.user_id, now=moment)

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
                before = PostgresUserRepository.get_user_on_connection(conn, context.username)
                must_before = None if before is None else before.must_change_password
                PostgresUserRepository.change_password_on_connection(
                    conn, context.username, cleaned
                )
                revoked = PostgresSessionRepository.revoke_other_sessions_for_user_on_connection(
                    conn,
                    context.user_id,
                    context.session_id,
                    moment,
                )
                PostgresAuditRepository.insert_on_connection(
                    conn,
                    AuditEventWrite(
                        event_type=EVENT_USER_PASSWORD_CHANGED,
                        result=RESULT_SUCCEEDED,
                        actor_kind=ACTOR_USER,
                        request_id=context.request_id,
                        actor_user_id=context.user_id,
                        actor_session_id=context.session_id,
                        target_user_id=context.user_id,
                        affected_session_count=len(revoked),
                        must_change_password_before=must_before,
                        must_change_password_after=False,
                        occurred_at=moment,
                    ),
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
        username = username.strip()
        password_clean = password.strip() if isinstance(password, str) else ""
        role_clean = role.strip()
        if not username:
            raise ValueError("username is required")
        if role_clean not in ("Admin", "QMB", "User"):
            raise ValueError("role must be one of: Admin, QMB, User")
        validate_password(password_clean, self.password_policy)
        if isinstance(self.repository, PostgresUserRepository):
            moment = _utc_now()
            try:
                with runtime_connection(self.repository._dsn) as conn:
                    user = PostgresUserRepository.create_user_on_connection(
                        conn,
                        username,
                        password_clean,
                        role_clean,
                        is_qmb=bool(is_qmb),
                        must_change_password=bool(must_change_password),
                    )
                    PostgresAuditRepository.insert_on_connection(
                        conn,
                        AuditEventWrite(
                            event_type=EVENT_USER_CREATED,
                            result=RESULT_SUCCEEDED,
                            actor_kind=ACTOR_USER,
                            request_id=actor.request_id,
                            actor_user_id=actor.user_id,
                            actor_session_id=actor.session_id,
                            target_user_id=user.user_id,
                            role_after=user.role,
                            is_qmb_after=user.is_qmb,
                            is_active_after=user.is_active,
                            must_change_password_after=user.must_change_password,
                            occurred_at=moment,
                        ),
                    )
                    return user
            except Exception as exc:
                from psycopg.errors import UniqueViolation

                if isinstance(exc, UniqueViolation):
                    raise UserExistsError("user already exists") from exc
                raise
        return self.create_user(
            username,
            password_clean,
            role_clean,
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
            actor=actor,
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
            actor=None,
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
            actor=None,
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
        actor: UserContext | None = None,
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
        changed_fields: list[str] = []
        if role is not None and role != current.role:
            changed_fields.append("role")
        if is_qmb is not None and bool(is_qmb) != current.is_qmb:
            changed_fields.append("is_qmb")
        if is_active is not None and bool(is_active) != current.is_active:
            changed_fields.append("is_active")
        user_repo = self.repository
        session_repo = self.session_repository
        if isinstance(user_repo, PostgresUserRepository):
            moment = _utc_now()
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
                revoked_count = 0
                if becoming_inactive:
                    if not isinstance(session_repo, PostgresSessionRepository):
                        raise RuntimeError(
                            "opaque session repository is required to deactivate PostgreSQL users"
                        )
                    revoked = PostgresSessionRepository.revoke_all_for_user_on_connection(
                        conn, updated.user_id, moment
                    )
                    revoked_count = len(revoked)
                if actor is not None and changed_fields:
                    PostgresAuditRepository.insert_on_connection(
                        conn,
                        AuditEventWrite(
                            event_type=EVENT_USER_ACCESS_CHANGED,
                            result=RESULT_SUCCEEDED,
                            actor_kind=ACTOR_USER,
                            request_id=actor.request_id,
                            actor_user_id=actor.user_id,
                            actor_session_id=actor.session_id,
                            target_user_id=updated.user_id,
                            affected_session_count=revoked_count if becoming_inactive else None,
                            changed_fields=changed_fields,
                            role_before=current.role,
                            role_after=updated.role,
                            is_qmb_before=current.is_qmb,
                            is_qmb_after=updated.is_qmb,
                            is_active_before=current.is_active,
                            is_active_after=updated.is_active,
                            occurred_at=moment,
                        ),
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
