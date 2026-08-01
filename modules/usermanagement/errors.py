from __future__ import annotations

"""Public auth/session error contracts for usermanagement (AP-028 Milestone 1)."""


class UsermanagementError(RuntimeError):
    """Base error for usermanagement domain failures."""


class AuthenticationError(UsermanagementError):
    """Credentials invalid, unknown, or otherwise not authenticated.

    External messages must not reveal whether the username exists.
    """


class InactiveUserError(UsermanagementError):
    """User exists but is not active."""


class PasswordChangeRequiredError(UsermanagementError):
    """User must change password before other use cases are allowed."""


class SessionError(UsermanagementError):
    """Base error for session resolution failures."""


class SessionNotFoundError(SessionError):
    """No session matches the presented token/hash."""


class InvalidSessionError(SessionError):
    """Token missing, malformed, or otherwise not acceptable."""


class ExpiredSessionError(SessionError):
    """Session exists but is past ``expires_at``."""


class RevokedSessionError(SessionError):
    """Session exists but has been revoked."""


class WeakPasswordError(UsermanagementError):
    """Password does not meet the configured password policy."""
