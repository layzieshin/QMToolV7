from __future__ import annotations

import unittest

from interfaces.pyqt.registry.contribution import QtModuleContribution
from interfaces.pyqt.shell.visibility_policy import ContributionVisibilityPolicy


class _User:
    def __init__(self, role: str) -> None:
        self.role = role


class MainWindowVisibilityPolicyTest(unittest.TestCase):
    def test_policy_allows_matching_role(self) -> None:
        contribution = QtModuleContribution(
            contribution_id="test.admin",
            module_id="test",
            title="Admin",
            sort_order=1,
            factory=lambda _: None,  # type: ignore[arg-type]
            allowed_roles=("Admin",),
        )
        self.assertTrue(ContributionVisibilityPolicy.is_visible_for_user(contribution, _User("ADMIN")))
        self.assertFalse(ContributionVisibilityPolicy.is_visible_for_user(contribution, _User("USER")))

    def test_policy_hides_login_required_for_anonymous(self) -> None:
        contribution = QtModuleContribution(
            contribution_id="test.auth",
            module_id="test",
            title="Auth",
            sort_order=1,
            factory=lambda _: None,  # type: ignore[arg-type]
            requires_login=True,
            allowed_roles=None,
        )
        self.assertFalse(ContributionVisibilityPolicy.is_visible_for_user(contribution, None))


if __name__ == "__main__":
    unittest.main()
