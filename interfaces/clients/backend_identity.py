"""Backend-client identity adapter (mirrors session; no local shadow login)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from interfaces.clients.backend_session import BackendSessionApi, BackendSessionUser
from interfaces.clients.http_transport import (
    BackendHttpTransport,
    BackendTransportError,
    resolve_backend_base_url_from_env,
)


@dataclass(frozen=True)
class DirectoryUser:
    """Assignment-picker / admin-table row from user HTTP APIs."""

    user_id: str
    username: str
    role: str
    is_active: bool = True
    is_qmb: bool = False
    must_change_password: bool = False


def _user_from_access_payload(row: dict[str, Any]) -> DirectoryUser:
    return DirectoryUser(
        user_id=str(row.get("user_id", "")),
        username=str(row.get("username", "")),
        role=str(row.get("role", "User")),
        is_active=bool(row.get("is_active", True)),
        is_qmb=bool(row.get("is_qmb", False)),
        must_change_password=bool(row.get("must_change_password", False)),
    )


def _raise_admin_http(exc: BackendTransportError, *, action: str) -> None:
    code = exc.status_code
    body = (exc.body or "").lower()
    if code == 401:
        raise RuntimeError("Anmeldung erforderlich oder Sitzung abgelaufen.") from None
    if code == 403:
        raise RuntimeError(
            f"{action} nur als Administrator (Backend-Admin-Recht)."
        ) from None
    if code == 404:
        raise RuntimeError("Benutzer nicht gefunden.") from None
    if code == 409 and "password_change_required" in body:
        raise RuntimeError(
            "Passwortänderung erforderlich, bevor Admin-Aktionen möglich sind."
        ) from None
    if code == 409:
        raise RuntimeError(
            "Benutzer existiert bereits oder Aktualisierung ist nicht erlaubt."
        ) from None
    detail = (exc.body or str(exc)).strip()
    raise RuntimeError(f"{action} fehlgeschlagen: {detail or 'unbekannter Fehler'}") from None


class BackendIdentityAdapter:
    """PyQt identity surface bound to ``backend_session_api`` + existing user HTTP.

    - ``get_current_user`` / ``logout`` → process session only
    - ``list_users`` → ``GET /users/directory`` (active users)
    - ``create_user`` → ``POST /users`` (Admin)
    - ``update_user_admin_fields`` → ``PATCH /users/{username}/access`` (Admin)
    - local login / register / foreign password paths remain fail-closed
    """

    def __init__(
        self,
        session: BackendSessionApi,
        *,
        transport: BackendHttpTransport | None = None,
    ) -> None:
        self._session = session
        self._transport = transport or BackendHttpTransport(
            base_url=resolve_backend_base_url_from_env(),
            token_provider=session.bearer_token,
        )

    def get_current_user(self) -> BackendSessionUser | None:
        return self._session.current_user()

    def logout(self) -> None:
        self._session.logout()

    def login(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "lokales Login ist im Backend-Modus deaktiviert; "
            "Anmeldung erfolgt über backend_session_api /auth/login"
        )

    def authenticate(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "lokale Authentifizierung ist im Backend-Modus deaktiviert"
        )

    def change_password(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "Fremd-Passwortänderung ist im Backend-Modus nicht verfügbar. "
            "Eigenes Passwort nur über /auth/change-password (SessionCoordinator)."
        )

    def update_user_profile(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "Profilstammdaten (Name/E-Mail) sind im Backend-Modus noch nicht "
            "per HTTP verfügbar."
        )

    def list_users(self) -> list[DirectoryUser]:
        try:
            rows = self._transport.request("GET", "/users/directory", auth=True)
        except BackendTransportError as exc:
            _raise_admin_http(exc, action="Benutzerverzeichnis laden")
            raise  # pragma: no cover
        if not isinstance(rows, list):
            raise BackendTransportError("invalid user directory response")
        result: list[DirectoryUser] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            result.append(_user_from_access_payload(row))
        return result

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "User",
        *,
        is_qmb: bool = False,
        must_change_password: bool = False,
    ) -> DirectoryUser:
        clean_user = str(username or "").strip()
        clean_role = str(role or "User").strip() or "User"
        if not clean_user:
            raise RuntimeError("Benutzername fehlt")
        body: dict[str, Any] = {
            "username": clean_user,
            "password": password,
            "role": clean_role,
            "is_qmb": bool(is_qmb),
            "must_change_password": bool(must_change_password),
        }
        # UI role "QMB" is a base role; keep is_qmb as provided (often False).
        try:
            row = self._transport.request("POST", "/users", body=body, auth=True)
        except BackendTransportError as exc:
            _raise_admin_http(exc, action="Benutzer anlegen")
            raise  # pragma: no cover
        if not isinstance(row, dict):
            raise BackendTransportError("invalid create-user response")
        return _user_from_access_payload(row)

    def update_user_admin_fields(
        self,
        username: str,
        *,
        department: str | None = None,
        scope: str | None = None,
        organization_unit: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        is_qmb: bool | None = None,
    ) -> DirectoryUser:
        clean = str(username or "").strip()
        if not clean:
            raise RuntimeError("Benutzername fehlt")
        unsupported = [
            name
            for name, value in (
                ("Abteilung", department),
                ("Scope", scope),
                ("Organisationseinheit", organization_unit),
            )
            if value is not None and str(value).strip()
        ]
        if unsupported:
            raise RuntimeError(
                "Im Backend-Modus sind nur Rolle, Aktiv-Status und QMB-Zusatzrechte "
                f"änderbar; nicht unterstützt: {', '.join(unsupported)}."
            )
        body: dict[str, Any] = {}
        if role is not None:
            body["role"] = str(role).strip()
        if is_active is not None:
            body["is_active"] = bool(is_active)
        if is_qmb is not None:
            body["is_qmb"] = bool(is_qmb)
        if not body:
            raise RuntimeError("Keine Admin-Zugriffsänderungen angegeben.")
        path = f"/users/{quote(clean, safe='')}/access"
        try:
            row = self._transport.request("PATCH", path, body=body, auth=True)
        except BackendTransportError as exc:
            _raise_admin_http(exc, action="Benutzerzugriff speichern")
            raise  # pragma: no cover
        if not isinstance(row, dict):
            raise BackendTransportError("invalid patch-user-access response")
        return _user_from_access_payload(row)

    def ensure_initial_admin(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("lokaler Admin-Seed ist im Backend-Modus deaktiviert")
