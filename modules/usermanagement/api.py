"""
Public surface of the usermanagement module.

External callers (CLI, GUI, backend, tests) MUST import only from this file.
``contracts`` and ``errors`` are implementation details unless re-exported here.

Forbidden from outside: service.py, sqlite_repository.py,
password_crypto.py, password_policy.py, repository.py, session_store.py, auth_ops.py,
user_admin_ops.py, wiring.py, session_ops.py, session_repository.py,
memory_session_repository.py, session_token.py, postgres_schema.py
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
    AuthenticationError,
    ExpiredSessionError,
    InactiveUserError,
    InvalidSessionError,
    PasswordChangeRequiredError,
    RevokedSessionError,
    SessionError,
    SessionNotFoundError,
    UsermanagementError,
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
    "get_usermanagement_service",
    "bootstrap_admin",
    "self_register",
    "bootstrap_first_admin",
    "authenticate_user",
    "create_backend_session",
    "resolve_session",
    "revoke_session",
    "change_own_password",
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


def create_backend_session(container, user: AuthenticatedUser) -> IssuedSession:
    """Issue an opaque backend session for an already authenticated user."""
    svc = get_usermanagement_service(container)
    return svc.create_session(user, client_type="backend")


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


def revoke_session(container, *, raw_token: str) -> SessionRecord:
    """Revoke the session identified by the presented opaque token (idempotent)."""
    svc = get_usermanagement_service(container)
    return svc.revoke_session(raw_token=raw_token)


def change_own_password(container, context: UserContext, new_password: str) -> None:
    """Change the password of the user identified by a confirmed context.

    The current session remains valid (M5 policy). Revoking other sessions is M6.
    """
    if not context.is_confirmed:
        raise InvalidSessionError("user context is not server-confirmed")
    svc = get_usermanagement_service(container)
    svc.change_password(context.username, new_password)


def ensure_postgres_schema_ready(container) -> int:
    """Verify the Usermanagement PostgreSQL schema matches the registered target.

    Uses the runtime DSN only; never applies migrations.
    """
    from .postgres_schema import assert_runtime_schema_ready

    dsn = container.get_port("usermanagement_postgres_dsn")
    return assert_runtime_schema_ready(str(dsn))
