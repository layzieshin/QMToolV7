"""Minimal user-admin HTTP routes (AP-028 M6). Transport only — no domain logic."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from modules.usermanagement import api as um_api
from modules.usermanagement.api import AuthenticatedUser, UserContext

from src.backend.auth_dependencies import get_container, map_auth_error, require_admin_context, require_user_context_normal

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str
    role: str = "User"
    is_qmb: bool = False
    must_change_password: bool = True


class PatchUserAccessRequest(BaseModel):
    role: str | None = None
    is_qmb: bool | None = None
    is_active: bool | None = None


class PasswordActionRequest(BaseModel):
    new_password: str


class UserAccessResponse(BaseModel):
    user_id: str
    username: str
    role: str
    is_active: bool
    is_qmb: bool
    must_change_password: bool


class UserDirectoryItem(BaseModel):
    user_id: str
    username: str
    role: str
    is_active: bool
    is_qmb: bool


@router.get("/directory", response_model=list[UserDirectoryItem])
def list_directory(
    request: Request,
    _actor: Annotated[UserContext, Depends(require_user_context_normal)],
) -> list[UserDirectoryItem]:
    container = get_container(request)
    entries = um_api.list_users_for_assignment(container)
    return [
        UserDirectoryItem(
            user_id=item.user_id,
            username=item.username,
            role=item.role,
            is_active=item.is_active,
            is_qmb=item.is_qmb,
        )
        for item in entries
    ]


def _user_payload(user: AuthenticatedUser) -> UserAccessResponse:
    return UserAccessResponse(
        user_id=user.user_id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        is_qmb=user.is_qmb,
        must_change_password=user.must_change_password,
    )


def _map_user_admin_error(exc: Exception) -> HTTPException:
    if isinstance(exc, um_api.WeakPasswordError):
        mapped = map_auth_error(exc)
        detail = dict(mapped.detail)
        field_errors = detail.get("field_errors")
        if field_errors:
            detail["field_errors"] = [
                {**item, "field": "new_password"} if item.get("field") == "password" else item
                for item in field_errors
            ]
        return HTTPException(status_code=mapped.status_code, detail=detail)
    if isinstance(exc, um_api.UsermanagementError):
        return map_auth_error(exc)
    if isinstance(exc, ValueError):
        return map_auth_error(um_api.InvalidUserUpdateError(str(exc)))
    if isinstance(exc, KeyError):
        return map_auth_error(um_api.UserNotFoundError(str(exc)))
    raise exc


@router.get("", response_model=list[UserAccessResponse])
def list_users(
    request: Request,
    actor: Annotated[UserContext, Depends(require_admin_context)],
) -> list[UserAccessResponse]:
    container = get_container(request)
    try:
        users = um_api.list_users_for_admin(container, actor)
    except Exception as exc:
        raise _map_user_admin_error(exc) from exc
    return [_user_payload(user) for user in users]


@router.get("/{username}", response_model=UserAccessResponse)
def get_user(
    username: str,
    request: Request,
    actor: Annotated[UserContext, Depends(require_admin_context)],
) -> UserAccessResponse:
    container = get_container(request)
    try:
        user = um_api.get_user_for_admin(container, actor, username)
    except Exception as exc:
        raise _map_user_admin_error(exc) from exc
    return _user_payload(user)


@router.post("", response_model=UserAccessResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    request: Request,
    actor: Annotated[UserContext, Depends(require_admin_context)],
) -> UserAccessResponse:
    container = get_container(request)
    try:
        user = um_api.create_user_as_admin(
            container,
            actor,
            body.username,
            body.password,
            role=body.role,
            is_qmb=body.is_qmb,
            must_change_password=body.must_change_password,
        )
    except Exception as exc:
        if isinstance(exc, um_api.UsermanagementError):
            raise map_auth_error(exc) from exc
        if isinstance(exc, ValueError):
            raise map_auth_error(um_api.InvalidUserUpdateError(str(exc))) from exc
        raise
    return _user_payload(user)


@router.patch("/{username}/access", response_model=UserAccessResponse)
def patch_user_access(
    username: str,
    body: PatchUserAccessRequest,
    request: Request,
    actor: Annotated[UserContext, Depends(require_admin_context)],
) -> UserAccessResponse:
    container = get_container(request)
    try:
        user = um_api.update_user_access_as_admin(
            container,
            actor,
            username,
            role=body.role,
            is_qmb=body.is_qmb,
            is_active=body.is_active,
        )
    except Exception as exc:
        raise _map_user_admin_error(exc) from exc
    return _user_payload(user)


@router.post(
    "/{username}/password-actions",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def password_action(
    username: str,
    body: PasswordActionRequest,
    request: Request,
    actor: Annotated[UserContext, Depends(require_admin_context)],
) -> Response:
    container = get_container(request)
    try:
        um_api.set_user_password_as_admin(container, actor, username, body.new_password)
    except Exception as exc:
        raise _map_user_admin_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
