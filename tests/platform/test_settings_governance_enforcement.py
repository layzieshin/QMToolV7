from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.usermanagement.contracts import issue_user_context
from qm_platform.organization.server_context import INSTALLATION_ORGANIZATION_ID
from qm_platform.persistence.database_evolution import DatabaseEvolutionService
from qm_platform.persistence.platform_settings_contribution import (
    PLATFORM_SETTINGS_DATABASE_CONTRIBUTION,
)
from qm_platform.persistence.database_evolution import DatabaseSpec, MigrationStep
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository


class SettingsGovernanceEnforcementTest(unittest.TestCase):
    def test_governance_critical_requires_acknowledge_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contrib = PLATFORM_SETTINGS_DATABASE_CONTRIBUTION
            db_path = root / "platform_settings.db"
            service_evo = DatabaseEvolutionService(app_home=root, backup_root=root / "backups")
            service_evo.migrate(
                (
                    DatabaseSpec(
                        database_id=contrib.database_id,
                        path=db_path,
                        migrations=tuple(
                            MigrationStep(
                                version=m.version,
                                name=m.name,
                                sql_path=m.sql_path,
                            )
                            for m in contrib.migrations
                        ),
                    ),
                ),
                reason="test",
            )
            service = SettingsService(SettingsRegistry())
            service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
            service.attach_persistence(SqliteSettingsRepository(db_path), None)

            actor = issue_user_context(
                user_id="u1",
                session_id="s1",
                request_id="r1",
        organization_id=INSTALLATION_ORGANIZATION_ID,
                username="admin",
                global_roles=["Admin"],
                is_qmb=False,
                authenticated_at=datetime.now(timezone.utc),
            )

            with self.assertRaises(ValueError):
                service.set_module_settings(
                    "signature",
                    {"require_password": False, "default_mode": "visual"},
                    actor=actor,
                )

            service.set_module_settings(
                "signature",
                {"require_password": False, "default_mode": "visual"},
                actor=actor,
                acknowledge_governance_change=True,
            )
            persisted = service.get_module_settings("signature")
            self.assertEqual(persisted["require_password"], False)

            with self.assertRaises(Exception):
                service.set_module_settings(
                    "signature",
                    {"require_password": True, "default_mode": "visual"},
                    actor="legacy-user",
                    acknowledge_governance_change=True,
                )

            service.set_module_settings(
                "signature",
                {"require_password": True, "default_mode": "visual"},
                actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
                acknowledge_governance_change=True,
            )


if __name__ == "__main__":
    unittest.main()
