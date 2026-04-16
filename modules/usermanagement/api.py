"""
Public surface of the usermanagement module.

External callers (CLI, GUI, tests) MUST import only from this file or
from ``modules.usermanagement.contracts``.

Forbidden from outside: service.py, sqlite_repository.py,
password_crypto.py, repository.py
"""
from __future__ import annotations

from .contracts import AuthenticatedUser

__all__ = [
    "AuthenticatedUser",
    "get_usermanagement_service",
    "bootstrap_admin",
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


