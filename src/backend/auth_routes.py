"""Auth HTTP routes (AP-028 M5). Transport only — no domain logic."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from modules.usermanagement import api as um_api
from modules.usermanagement.api import UserContext

from src.backend.auth_dependencies import (
    effective_request_id,
    extract_bearer_token,
    get_container,
    map_auth_error,
    require_user_context_normal,
    require_user_context_password_change,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)


class MeResponse(BaseModel):
    user_id: str
    session_id: str
    request_id: str
    username: str
    global_roles: list[str]
    is_qmb: bool
    authenticated_at: str


def _me_payload(context: UserContext) -> MeResponse:
    return MeResponse(
        user_id=context.user_id,
        session_id=context.session_id,
        request_id=context.request_id,
        username=context.username,
        global_roles=sorted(context.global_roles),
        is_qmb=context.is_qmb,
        authenticated_at=context.authenticated_at.isoformat(),
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    request_id: Annotated[str, Depends(effective_request_id)],
) -> LoginResponse:
    del request_id  # correlation is applied by middleware; login does not resolve a session
    container = get_container(request)
    try:
        user = um_api.authenticate_user(container, body.username, body.password)
        issued = um_api.create_backend_session(container, user)
    except Exception as exc:
        if isinstance(
            exc,
            (
                um_api.AuthenticationError,
                um_api.InactiveUserError,
                um_api.UsermanagementError,
            ),
        ):
            raise map_auth_error(exc) from exc
        raise
    return LoginResponse(token=issued.raw_token)


@router.get("/me", response_model=MeResponse)
def me(context: Annotated[UserContext, Depends(require_user_context_normal)]) -> MeResponse:
    return _me_payload(context)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    request: Request,
    token: Annotated[str, Depends(extract_bearer_token)],
) -> Response:
    container = get_container(request)
    try:
        um_api.revoke_session(container, raw_token=token)
    except Exception as exc:
        if isinstance(
            exc,
            (
                um_api.InvalidSessionError,
                um_api.SessionNotFoundError,
                um_api.ExpiredSessionError,
                um_api.RevokedSessionError,
                um_api.SessionError,
            ),
        ):
            raise map_auth_error(exc) from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
