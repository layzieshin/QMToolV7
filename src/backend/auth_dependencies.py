"""HTTP auth dependencies: Bearer parsing, request ID, UserContext resolution."""
from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from qm_platform.organization.server_context import (
    ClientOrganizationSpoofRejected,
    resolve_active_organization_id,
)

from modules.usermanagement import api as um_api
from src.backend.cookie_csrf import SESSION_COOKIE_NAME

from modules.usermanagement.api import (
    AuditUnavailableError,
    ExpiredSessionError,
    InactiveUserError,
    InvalidSessionError,
    PasswordChangeRequiredError,
    RevokedSessionError,
    SessionError,
    SessionNotFoundError,
    UserContext,
)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_bearer = HTTPBearer(auto_error=False)

_MAPPED_ERRORS = (
    um_api.AuthenticationError,
    InactiveUserError,
    PasswordChangeRequiredError,
    um_api.WeakPasswordError,
    um_api.AuthorizationError,
    um_api.UserNotFoundError,
    um_api.UserExistsError,
    um_api.LastActiveAdminError,
    um_api.InvalidUserUpdateError,
    AuditUnavailableError,
    InvalidSessionError,
    SessionNotFoundError,
    ExpiredSessionError,
    RevokedSessionError,
    SessionError,
)


def effective_request_id(
    request: Request,
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> str:
    """Return the request id attached by middleware, or allocate one."""
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, str) and existing:
        return existing
    if x_request_id and _REQUEST_ID_RE.fullmatch(x_request_id.strip()):
        return x_request_id.strip()
    return str(uuid.uuid4())


def enforce_server_organization_context(
    x_organization_id: Annotated[str | None, Header(alias="X-Organization-ID")] = None,
) -> None:
    """Reject client attempts to supply a non-matching authoritative organization_id."""
    try:
        resolve_active_organization_id(client_organization_id=x_organization_id)
    except ClientOrganizationSpoofRejected as exc:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "organization context is server-confirmed"},
        ) from exc


def get_container(request: Request):
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "unavailable", "message": "auth not configured"},
        )
    return container


def _unauthorized(message: str = "unauthorized") -> HTTPException:
    return HTTPException(status_code=401, detail={"error": "unauthorized", "message": message})


def map_auth_error(exc: Exception) -> HTTPException:
    """Map usermanagement auth/session/admin errors to stable HTTP errors."""
    if isinstance(exc, AuditUnavailableError):
        return HTTPException(
            status_code=503,
            detail={"error": "unavailable", "message": "audit evidence unavailable"},
        )
    if isinstance(exc, PasswordChangeRequiredError):
        return HTTPException(
            status_code=409,
            detail={"error": "password_change_required", "message": "password change required"},
        )
    if isinstance(exc, um_api.WeakPasswordError):
        return HTTPException(
            status_code=400,
            detail={"error": "weak_password", "message": "password does not meet policy"},
        )
    if isinstance(exc, um_api.InvalidUserUpdateError):
        return HTTPException(
            status_code=400,
            detail={"error": "invalid_user_update", "message": "invalid user update"},
        )
    if isinstance(exc, um_api.AuthorizationError):
        return HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "forbidden"},
        )
    if isinstance(exc, um_api.UserNotFoundError):
        return HTTPException(
            status_code=404,
            detail={"error": "user_not_found", "message": "user not found"},
        )
    if isinstance(exc, um_api.UserExistsError):
        return HTTPException(
            status_code=409,
            detail={"error": "user_exists", "message": "user already exists"},
        )
    if isinstance(exc, um_api.LastActiveAdminError):
        return HTTPException(
            status_code=409,
            detail={"error": "last_active_admin", "message": "cannot remove the last active admin"},
        )
    return _unauthorized()


def extract_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized("missing bearer token")
    return credentials.credentials


def resolve_auth_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """Return Bearer token when Authorization is present (authoritative); else session cookie."""
    auth_header = request.headers.get("Authorization")
    if auth_header is not None and auth_header.strip():
        if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
            raise _unauthorized("invalid bearer token")
        return credentials.credentials
    session = request.cookies.get(SESSION_COOKIE_NAME)
    if not session:
        raise _unauthorized("missing session credential")
    return session


def require_user_context(
    request: Request,
    token: Annotated[str, Depends(resolve_auth_token)],
    request_id: Annotated[str, Depends(effective_request_id)],
    *,
    password_change_allowed: bool,
) -> UserContext:
    container = get_container(request)
    try:
        return um_api.resolve_session(
            container,
            token,
            request_id=request_id,
            password_change_allowed=password_change_allowed,
        )
    except _MAPPED_ERRORS as exc:
        raise map_auth_error(exc) from exc


def require_user_context_normal(
    request: Request,
    token: Annotated[str, Depends(resolve_auth_token)],
    request_id: Annotated[str, Depends(effective_request_id)],
) -> UserContext:
    return require_user_context(
        request,
        token,
        request_id,
        password_change_allowed=False,
    )


def require_user_context_password_change(
    request: Request,
    token: Annotated[str, Depends(resolve_auth_token)],
    request_id: Annotated[str, Depends(effective_request_id)],
) -> UserContext:
    """Only ``/auth/change-password`` may use password_change_allowed=True."""
    return require_user_context(
        request,
        token,
        request_id,
        password_change_allowed=True,
    )


def require_admin_context(
    context: Annotated[UserContext, Depends(require_user_context_normal)],
) -> UserContext:
    """Backend-side Admin gate; service layer re-checks independently."""
    if "ADMIN" not in context.global_roles:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "forbidden"},
        )
    return context
