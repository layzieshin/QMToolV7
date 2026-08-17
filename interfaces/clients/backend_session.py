"""Process-local backend session API (J04-M0-P0). Token stays in memory only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from interfaces.clients.http_transport import (
    BackendHttpTransport,
    BackendTransportError,
    error_code_from_body,
    resolve_backend_base_url_from_env,
)


@dataclass(frozen=True)
class BackendSessionUser:
    """UI-facing confirmed backend user (no token fields)."""

    user_id: str
    session_id: str
    username: str
    role: str
    global_roles: tuple[str, ...]
    is_qmb: bool
    authenticated_at: str
    must_change_password: bool = False
    is_active: bool = True

    @property
    def roles(self) -> tuple[str, ...]:
        return self.global_roles


def _role_for_ui(*, global_roles: list[str], is_qmb: bool) -> str:
    normalized = {str(r).strip().upper() for r in global_roles}
    if "ADMIN" in normalized:
        return "ADMIN"
    if is_qmb or "QMB" in normalized:
        return "QMB"
    return "USER"


class BackendSessionApi:
    """login / me / change_password / logout against /auth/*."""

    def __init__(self, transport: BackendHttpTransport | None = None) -> None:
        self._token: str | None = None
        self._user: BackendSessionUser | None = None
        self._transport = transport or BackendHttpTransport(
            base_url=resolve_backend_base_url_from_env(),
            token_provider=self.bearer_token,
        )

    def bearer_token(self) -> str | None:
        return self._token

    def current_user(self) -> BackendSessionUser | None:
        return self._user

    def clear(self) -> None:
        self._token = None
        self._user = None

    def login(self, username: str, password: str) -> BackendSessionUser:
        clean_user = str(username or "").strip()
        if not clean_user:
            raise BackendTransportError("username is required")
        payload = self._transport.request(
            "POST",
            "/auth/login",
            body={"username": clean_user, "password": password},
            auth=False,
        )
        if not isinstance(payload, dict) or not str(payload.get("token", "")).strip():
            raise BackendTransportError("login response missing token")
        self._token = str(payload["token"]).strip()
        try:
            return self.refresh_me()
        except BackendTransportError as exc:
            if exc.status_code == 409 and error_code_from_body(exc.body) == "password_change_required":
                self._user = BackendSessionUser(
                    user_id="",
                    session_id="",
                    username=clean_user,
                    role="USER",
                    global_roles=(),
                    is_qmb=False,
                    authenticated_at=datetime.now(timezone.utc).isoformat(),
                    must_change_password=True,
                )
                return self._user
            self.clear()
            raise

    def refresh_me(self) -> BackendSessionUser:
        if not self._token:
            raise BackendTransportError("not authenticated", status_code=401)
        try:
            payload = self._transport.request("GET", "/auth/me", auth=True)
        except BackendTransportError as exc:
            if exc.status_code == 401:
                self.clear()
            if exc.status_code == 409 and error_code_from_body(exc.body) == "password_change_required":
                # Keep token for change-password; mark must_change.
                existing = self._user
                self._user = BackendSessionUser(
                    user_id=getattr(existing, "user_id", "") or "",
                    session_id=getattr(existing, "session_id", "") or "",
                    username=getattr(existing, "username", "") or "",
                    role=getattr(existing, "role", "USER") or "USER",
                    global_roles=tuple(getattr(existing, "global_roles", ()) or ()),
                    is_qmb=bool(getattr(existing, "is_qmb", False)),
                    authenticated_at=getattr(existing, "authenticated_at", "")
                    or datetime.now(timezone.utc).isoformat(),
                    must_change_password=True,
                )
                return self._user
            raise
        user = self._user_from_me_payload(payload)
        self._user = user
        return user

    def change_password(self, new_password: str) -> BackendSessionUser:
        if not self._token:
            raise BackendTransportError("not authenticated", status_code=401)
        self._transport.request(
            "POST",
            "/auth/change-password",
            body={"new_password": new_password},
            auth=True,
            expect_json=False,
        )
        return self.refresh_me()

    def logout(self) -> None:
        token = self._token
        if token:
            try:
                self._transport.request(
                    "POST",
                    "/auth/logout",
                    auth=True,
                    expect_json=False,
                )
            except BackendTransportError:
                # Always clear local process session.
                pass
        self.clear()

    @staticmethod
    def _user_from_me_payload(payload: Any) -> BackendSessionUser:
        if not isinstance(payload, dict):
            raise BackendTransportError("invalid /auth/me payload")
        roles = payload.get("global_roles") or []
        if not isinstance(roles, list):
            roles = []
        role_list = [str(r) for r in roles]
        is_qmb = bool(payload.get("is_qmb", False))
        return BackendSessionUser(
            user_id=str(payload.get("user_id", "")),
            session_id=str(payload.get("session_id", "")),
            username=str(payload.get("username", "")),
            role=_role_for_ui(global_roles=role_list, is_qmb=is_qmb),
            global_roles=tuple(role_list),
            is_qmb=is_qmb,
            authenticated_at=str(payload.get("authenticated_at", "")),
            must_change_password=False,
        )


def create_backend_session_api() -> BackendSessionApi:
    return BackendSessionApi()
