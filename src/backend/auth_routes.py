"""Auth HTTP routes (AP-028 M5 / WEB00). Transport only — no domain logic."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from modules.usermanagement import api as um_api
from modules.usermanagement.api import UserContext

from src.backend.auth_dependencies import (
    effective_request_id,
    enforce_server_organization_context,
    get_container,
    map_auth_error,
    require_user_context_normal,
    require_user_context_password_change,
    resolve_auth_token,
)
from src.backend.cookie_csrf import (
    clear_csrf_cookie,
    clear_session_cookie,
    generate_csrf_token,
    set_csrf_cookie,
    set_session_cookie,
)

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(enforce_server_organization_context)],
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str


class TokenResponse(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    # No min_length here — Usermanagement password policy owns validation.
    new_password: str


class MeResponse(BaseModel):
    user_id: str
    session_id: str
    request_id: str
    organization_id: str
    username: str
    global_roles: list[str]
    is_qmb: bool
    authenticated_at: str


def _me_payload(context: UserContext) -> MeResponse:
    return MeResponse(
        user_id=context.user_id,
        session_id=context.session_id,
        request_id=context.request_id,
        organization_id=context.organization_id,
        username=context.username,
        global_roles=sorted(context.global_roles),
        is_qmb=context.is_qmb,
        authenticated_at=context.authenticated_at.isoformat(),
    )


def _login_issue(
    request: Request,
    body: LoginRequest,
    request_id: str,
) -> str:
    container = get_container(request)
    try:
        issued = um_api.login_backend(
            container,
            body.username,
            body.password,
            request_id=request_id,
        )
    except Exception as exc:
        if isinstance(
            exc,
            (
                um_api.AuthenticationError,
                um_api.InactiveUserError,
                um_api.WeakPasswordError,
                um_api.AuditUnavailableError,
                um_api.UsermanagementError,
            ),
        ):
            raise map_auth_error(exc) from exc
        raise
    return issued.raw_token


@router.get("/csrf", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def csrf_bootstrap() -> Response:
    """Issue a readable CSRF cookie for browser Same-Origin clients."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_csrf_cookie(response, generate_csrf_token())
    return response


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def login_browser(
    body: LoginRequest,
    request: Request,
    request_id: Annotated[str, Depends(effective_request_id)],
) -> Response:
    """Browser login: HttpOnly session cookie, no credential in body."""
    raw_token = _login_issue(request, body, request_id)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    set_session_cookie(response, raw_token)
    set_csrf_cookie(response, generate_csrf_token())
    return response


@router.post("/token", response_model=TokenResponse)
def login_token(
    body: LoginRequest,
    request: Request,
    request_id: Annotated[str, Depends(effective_request_id)],
) -> TokenResponse:
    """CLI/operator login: opaque Bearer token, no Set-Cookie."""
    raw_token = _login_issue(request, body, request_id)
    return TokenResponse(token=raw_token)


@router.get("/me", response_model=MeResponse)
def me(context: Annotated[UserContext, Depends(require_user_context_normal)]) -> MeResponse:
    return _me_payload(context)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    request: Request,
    token: Annotated[str, Depends(resolve_auth_token)],
    request_id: Annotated[str, Depends(effective_request_id)],
) -> Response:
    container = get_container(request)
    try:
        um_api.logout_backend(container, raw_token=token, request_id=request_id)
    except Exception as exc:
        if isinstance(
            exc,
            (
                um_api.InvalidSessionError,
                um_api.SessionNotFoundError,
                um_api.ExpiredSessionError,
                um_api.RevokedSessionError,
                um_api.AuditUnavailableError,
                um_api.SessionError,
            ),
        ):
            raise map_auth_error(exc) from exc
        raise
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    clear_csrf_cookie(response)
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout_all(
    request: Request,
    context: Annotated[UserContext, Depends(require_user_context_normal)],
) -> Response:
    container = get_container(request)
    try:
        um_api.revoke_all_own_sessions(container, context)
    except Exception as exc:
        if isinstance(exc, um_api.UsermanagementError):
            raise map_auth_error(exc) from exc
        raise
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    clear_csrf_cookie(response)
    return response


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    context: Annotated[UserContext, Depends(require_user_context_password_change)],
) -> Response:
    # Target user comes only from confirmed context; body has new_password only.
    container = get_container(request)
    try:
        um_api.change_own_password(container, context, body.new_password)
    except Exception as exc:
        if isinstance(exc, um_api.UsermanagementError):
            raise map_auth_error(exc) from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
