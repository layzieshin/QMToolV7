"""
Public surface of the usermanagement module.

External callers (CLI, GUI, backend, tests) MUST import only from this file.
``contracts`` and ``errors`` are implementation details unless re-exported here.

Forbidden from outside: service.py, sqlite_repository.py,
password_crypto.py, repository.py, session_store.py, auth_ops.py,
user_admin_ops.py, wiring.py
"""
from __future__ import annotations

from .contracts import (
    AuthenticatedUser,
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
)
from .role_policies import is_effective_qmb, normalize_base_role

__all__ = [
    "AuthenticatedUser",
    "UserContext",
    "SystemExecutionContext",
    "SessionRecord",
    "UsermanagementError",
    "AuthenticationError",
    "InactiveUserError",
    "PasswordChangeRequiredError",
    "SessionError",
    "SessionNotFoundError",
    "InvalidSessionError",
    "ExpiredSessionError",
    "RevokedSessionError",
    "get_usermanagement_service",
    "bootstrap_admin",
    "self_register",
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
