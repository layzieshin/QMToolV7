"""HTTP auth dependencies: Bearer parsing, request ID, UserContext resolution."""
from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from modules.usermanagement import api as um_api
from modules.usermanagement.api import (
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
    """Map usermanagement auth/session errors to stable HTTP errors."""
    if isinstance(exc, PasswordChangeRequiredError):
        return HTTPException(
            status_code=409,
            detail={"error": "password_change_required", "message": "password change required"},
        )
    return _unauthorized()


def extract_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized("missing bearer token")
    return credentials.credentials


def require_user_context(
    request: Request,
    token: Annotated[str, Depends(extract_bearer_token)],
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
    token: Annotated[str, Depends(extract_bearer_token)],
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
    token: Annotated[str, Depends(extract_bearer_token)],
    request_id: Annotated[str, Depends(effective_request_id)],
) -> UserContext:
    """Only ``/auth/change-password`` may use password_change_allowed=True."""
    return require_user_context(
        request,
        token,
        request_id,
        password_change_allowed=True,
    )
