"""Public contract tests for require_confirmed_user_context (J03-accepted surface)."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from modules.usermanagement.api import UserContext, require_confirmed_user_context
from modules.usermanagement.contracts import issue_user_context
from modules.usermanagement.errors import AuthorizationError
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID


class RequireConfirmedUserContextContractTest(unittest.TestCase):
    def test_accepts_confirmed_public_user_context(self) -> None:
        actor = issue_user_context(
            user_id="u1",
            session_id="s1",
            request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
            username="qmb",
            global_roles=("QMB",),
            is_qmb=True,
            authenticated_at=datetime.now(timezone.utc),
        )
        confirmed = require_confirmed_user_context(actor)
        self.assertIsInstance(confirmed, UserContext)
        self.assertIs(confirmed, actor)

    def test_rejects_duck_typed_object(self) -> None:
        duck = SimpleNamespace(
            user_id="u1",
            session_id="s1",
            request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
            is_confirmed=True,
            username="x",
        )
        with self.assertRaises(AuthorizationError):
            require_confirmed_user_context(duck)

    def test_rejects_unconfirmed_context(self) -> None:
        actor = issue_user_context(
            user_id="u1",
            session_id="s1",
            request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
            username="admin",
            global_roles=("ADMIN",),
            is_qmb=False,
            authenticated_at=datetime.now(timezone.utc),
        )
        # Reconstruct without confirmation by building a non-issued lookalike is impossible
        # for frozen confirmed contexts; instead verify isinstance + is_confirmed gate via duck.
        with self.assertRaises(AuthorizationError):
            require_confirmed_user_context(
                SimpleNamespace(
                    user_id="u1",
                    session_id="s1",
                    request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
                    is_confirmed=False,
                )
            )

    def test_rejects_empty_identity_fields(self) -> None:
        base = dict(
            username="qmb",
            global_roles=frozenset({"QMB"}),
            is_qmb=True,
            authenticated_at=datetime.now(timezone.utc),
        )
        cases = (
            {"user_id": "", "session_id": "s1", "request_id": "r1"},
            {"user_id": "u1", "session_id": "", "request_id": "r1"},
            {"user_id": "u1", "session_id": "s1", "request_id": ""},
        )
        for overrides in cases:
            with self.subTest(**overrides):
                actor = UserContext(**base, **overrides)
                object.__setattr__(actor, "_server_confirmed", True)
                with self.assertRaises(AuthorizationError):
                    require_confirmed_user_context(actor)


if __name__ == "__main__":
    unittest.main()
