"""Explicit J02 settings revision actors. No silent legacy current_user fallback."""

from __future__ import annotations

MIGRATION_SETTINGS_IMPORT_ACTOR = "migration:j02-settings-import"
SYSTEM_BACKEND_BOOTSTRAP_ACTOR = "system:backend_bootstrap"

ALLOWED_SYSTEM_ACTORS = frozenset(
    {
        MIGRATION_SETTINGS_IMPORT_ACTOR,
        SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
    }
)
