"""
Public surface of the usermanagement module.

External callers (CLI, GUI, backend, tests) MUST import only from this file.
``contracts`` and ``errors`` are implementation details unless re-exported here.

Forbidden from outside: service.py, sqlite_repository.py,
password_crypto.py, password_policy.py, repository.py, session_store.py, auth_ops.py,
user_admin_ops.py, wiring.py, session_ops.py, session_repository.py,
memory_session_repository.py, session_token.py, postgres_schema.py,
postgres_audit_repository.py, postgres_user_repository.py, postgres_session_repository.py,
postgres_connection.py
"""
from __future__ import annotations

from .contracts import (
    AuthenticatedUser,
    IssuedSession,
    SessionRecord,
    SystemExecutionContext,
    UserContext,
)
from .errors import (
    AuditUnavailableError,
    AuthenticationError,
    AuthorizationError,
    ExpiredSessionError,
    InactiveUserError,
    InvalidSessionError,
    InvalidUserUpdateError,
    LastActiveAdminError,
    PasswordChangeRequiredError,
    RevokedSessionError,
    SessionError,
    SessionNotFoundError,
    UsermanagementError,
    UserExistsError,
    UserNotFoundError,
    WeakPasswordError,
)
from .role_policies import is_effective_qmb, normalize_base_role

__all__ = [
    "AuthenticatedUser",
    "UserContext",
    "SystemExecutionContext",
    "SessionRecord",
    "IssuedSession",
    "UsermanagementError",
    "AuthenticationError",
    "InactiveUserError",
    "PasswordChangeRequiredError",
    "SessionError",
    "SessionNotFoundError",
    "InvalidSessionError",
    "ExpiredSessionError",
    "RevokedSessionError",
    "WeakPasswordError",
    "AuthorizationError",
    "UserNotFoundError",
    "UserExistsError",
    "LastActiveAdminError",
    "InvalidUserUpdateError",
    "AuditUnavailableError",
    "get_usermanagement_service",
    "bootstrap_admin",
    "self_register",
    "bootstrap_first_admin",
    "authenticate_user",
    "login_backend",
    "logout_backend",
    "resolve_session",
    "revoke_all_own_sessions",
    "change_own_password",
    "create_user_as_admin",
    "update_user_access_as_admin",
    "ensure_postgres_schema_ready",
    "is_effective_qmb",
    "normalize_base_role",
]


def get_usermanagement_service(container):
    """Retrieve the usermanagement service from the runtime container.

    Use this helper instead of importing the service class directly.
    """
    return container.get_port("usermanagement_service")


def bootstrap_admin(container, username: str, password: str, role: str = "Admin"):
    """Ensure an admin user exists. Public bootstrap use-case for CLI init.

    Delegates to the service's ``ensure_admin_credentials`` method.
    """
    svc = get_usermanagement_service(container)
    return svc.ensure_admin_credentials(username, password, role)


def self_register(
    container,
    username: str,
    password: str,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
):
    svc = get_usermanagement_service(container)
    return svc.self_register(
        username,
        password,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


def bootstrap_first_admin(container, username: str, password: str):
    """Create the first admin only when the user store is empty.

    Sets ``must_change_password=True``. Returns ``None`` when users already exist.
    """
    svc = get_usermanagement_service(container)
    return svc.bootstrap_first_admin(username, password)


def authenticate_user(container, username: str, password: str) -> AuthenticatedUser:
    """Authenticate credentials. Raises ``AuthenticationError`` on failure.

    Invalid credentials and inactive users are both reported as authentication
    failures so callers cannot distinguish them.
    """
    svc = get_usermanagement_service(container)
    user = svc.authenticate(username, password)
    if user is None:
        raise AuthenticationError("invalid credentials")
    return user


def login_backend(container, username: str, password: str, *, request_id: str) -> IssuedSession:
    """Backend login: authenticate, issue opaque session, and write PG audit evidence."""
    svc = get_usermanagement_service(container)
    return svc.login_backend(username, password, request_id=request_id)


def logout_backend(container, *, raw_token: str, request_id: str) -> None:
    """Backend logout: revoke presented session and write PG audit on first revoke."""
    svc = get_usermanagement_service(container)
    svc.logout_backend(raw_token=raw_token, request_id=request_id)


def resolve_session(
    container,
    raw_token: str | None,
    *,
    request_id: str,
    password_change_allowed: bool = False,
) -> UserContext:
    """Resolve a Bearer token into a confirmed ``UserContext``."""
    svc = get_usermanagement_service(container)
    return svc.resolve_session(
        raw_token,
        request_id=request_id,
        password_change_allowed=password_change_allowed,
    )


def revoke_all_own_sessions(container, context: UserContext) -> list[SessionRecord]:
    """Revoke all sessions belonging to the confirmed context user (logout-all)."""
    svc = get_usermanagement_service(container)
    return svc.revoke_all_own_sessions(context)


def change_own_password(container, context: UserContext, new_password: str) -> None:
    """Change password for the confirmed context user.

    Keeps the current session; revokes all other sessions of the same user (M6).
    """
    svc = get_usermanagement_service(container)
    svc.change_own_password(context, new_password)


def create_user_as_admin(
    container,
    actor: UserContext,
    username: str,
    password: str,
    *,
    role: str = "User",
    is_qmb: bool = False,
    must_change_password: bool = True,
) -> AuthenticatedUser:
    """Create a user; requires a confirmed Admin actor (service-enforced)."""
    svc = get_usermanagement_service(container)
    return svc.create_user_as_admin(
        actor,
        username,
        password,
        role=role,
        is_qmb=is_qmb,
        must_change_password=must_change_password,
    )


def update_user_access_as_admin(
    container,
    actor: UserContext,
    username: str,
    *,
    role: str | None = None,
    is_qmb: bool | None = None,
    is_active: bool | None = None,
) -> AuthenticatedUser:
    """Patch role / is_qmb / is_active; requires a confirmed Admin actor."""
    svc = get_usermanagement_service(container)
    return svc.update_user_access_as_admin(
        actor,
        username,
        role=role,
        is_qmb=is_qmb,
        is_active=is_active,
    )


def ensure_postgres_schema_ready(container) -> int:
    """Verify the Usermanagement PostgreSQL schema matches the registered target.

    Uses the runtime DSN only; never applies migrations.
    """
    from .postgres_schema import assert_runtime_schema_ready

    dsn = container.get_port("usermanagement_postgres_dsn")
    return assert_runtime_schema_ready(str(dsn))
