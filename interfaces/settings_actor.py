"""Resolve confirmed settings-write actors without inventing UserContext from legacy session."""

from __future__ import annotations

import os
from typing import Any

from modules.usermanagement import api as um_api
from qm_platform.settings.errors import SettingsActorRequiredError


def resolve_confirmed_settings_actor(
    container: Any,
    *,
    request_id: str = "settings-write",
) -> object:
    """Return a confirmed UserContext via resolve_session.

    Sources (in order):
    - container port ``session_token`` when present
    - environment ``QMTOOL_SESSION_TOKEN``

    Never synthesizes a UserContext from ``get_current_user()`` / ``current_user.json``.
    """
    token = ""
    if hasattr(container, "has_port") and container.has_port("session_token"):
        raw = container.get_port("session_token")
        token = str(raw or "").strip()
    if not token:
        token = os.environ.get("QMTOOL_SESSION_TOKEN", "").strip()
    if not token:
        raise SettingsActorRequiredError(
            "Einstellungen speichern erfordert eine bestaetigte Backend-Session "
            "(Port session_token oder QMTOOL_SESSION_TOKEN). "
            "Die Desktop-Legacy-Anmeldung (current_user.json) ist kein gueltiger Actor."
        )
    try:
        return um_api.resolve_session(container, token, request_id=request_id)
    except (
        um_api.SessionError,
        um_api.InactiveUserError,
        um_api.PasswordChangeRequiredError,
    ) as exc:
        raise SettingsActorRequiredError(
            "Einstellungen speichern erfordert eine aktuell aufloesbare Backend-Session."
        ) from exc
    except RuntimeError as exc:
        if str(exc) != "opaque session repository is not configured":
            raise
        raise SettingsActorRequiredError(
            "Einstellungen speichern ist in diesem Desktop-Legacy-Runtimekontext "
            "bis zum Backend-Sessiontransport nicht verfuegbar."
        ) from exc
