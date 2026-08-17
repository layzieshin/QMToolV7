"""Client-side auth error messages (no backend contract changes)."""
from __future__ import annotations

from interfaces.clients.http_transport import BackendTransportError, error_code_from_body


def user_facing_auth_message(exc: BaseException) -> str:
    """Map transport failures to short German UI text without raw JSON bodies."""
    if isinstance(exc, BackendTransportError):
        code = error_code_from_body(exc.body or "")
        status = exc.status_code
        if status == 401 or code in {"unauthorized", "invalid_credentials"}:
            return "Ungültige Zugangsdaten."
        if status == 403 or code == "forbidden":
            return "Zugriff verweigert."
        if status == 409 and code == "password_change_required":
            return "Passwortänderung erforderlich."
        if status == 503 or code == "unavailable":
            return "Backend vorübergehend nicht verfügbar."
        msg = str(exc)
        if "unreachable" in msg.lower() or status is None and "backend unreachable" in msg.lower():
            return "Backend nicht erreichbar. Bitte Verbindung und QMTOOL_BACKEND_URL prüfen."
        if status is not None and status >= 500:
            return "Backend-Fehler bei der Anmeldung. Bitte später erneut versuchen."
        return "Anmeldung fehlgeschlagen."
    text = str(exc).strip()
    if not text:
        return "Anmeldung fehlgeschlagen."
    if text.startswith("backend HTTP") or '{"detail"' in text:
        return "Anmeldung fehlgeschlagen."
    return text
