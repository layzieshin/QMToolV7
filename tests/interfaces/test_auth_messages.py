"""Client auth message mapping (no backend contract changes)."""
from __future__ import annotations

from interfaces.clients.auth_messages import user_facing_auth_message
from interfaces.clients.http_transport import BackendTransportError


def test_unauthorized_maps_to_german_without_json() -> None:
    exc = BackendTransportError(
        'backend HTTP 401: {"detail":{"error":"unauthorized","message":"unauthorized"}}',
        status_code=401,
        body='{"detail":{"error":"unauthorized","message":"unauthorized"}}',
    )
    msg = user_facing_auth_message(exc)
    assert msg == "Ungültige Zugangsdaten."
    assert "detail" not in msg
    assert "HTTP 401" not in msg


def test_unreachable_maps_to_connection_hint() -> None:
    exc = BackendTransportError("backend unreachable at http://127.0.0.1:8000: timed out")
    assert "nicht erreichbar" in user_facing_auth_message(exc)


def test_generic_runtime_error_passthrough() -> None:
    assert user_facing_auth_message(RuntimeError("Bitte Benutzernamen eingeben.")) == (
        "Bitte Benutzernamen eingeben."
    )
