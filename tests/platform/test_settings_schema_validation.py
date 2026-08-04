"""Unit tests for settings JSON-Schema subset validation (Bucket B)."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.training.module import TRAINING_SETTINGS_CONTRIBUTION
from qm_platform.settings.actors import SYSTEM_BACKEND_BOOTSTRAP_ACTOR
from qm_platform.settings.errors import SettingsSchemaInvalidError
from qm_platform.settings.schema_validation import (
    technical_settings_schema,
    validate_against_schema,
    validate_technical_settings_payload,
)
from qm_platform.settings.testing import build_settings_service_for_tests


def test_technical_schema_excludes_bootstrap_keys() -> None:
    schema = technical_settings_schema("signature", SIGNATURE_SETTINGS_CONTRIBUTION.schema)
    assert set(schema["properties"]) == {"require_password", "default_mode"}
    assert set(schema["required"]) == {"require_password", "default_mode"}


def test_validate_rejects_wrong_types_and_minimum() -> None:
    with pytest.raises(SettingsSchemaInvalidError, match="invalid type"):
        validate_against_schema(
            {"require_password": "yes", "default_mode": "visual"},
            technical_settings_schema("signature", SIGNATURE_SETTINGS_CONTRIBUTION.schema),
        )
    with pytest.raises(SettingsSchemaInvalidError, match="below minimum"):
        validate_technical_settings_payload(
            "training",
            {
                "questions_per_quiz": 0,
                "min_correct_answers": 1,
                "shuffle_answers": True,
                "retry_cooldown_seconds": 0,
                "force_reread_on_fail": False,
            },
            TRAINING_SETTINGS_CONTRIBUTION.schema,
        )


def test_settings_service_rejects_invalid_bucket_b_types(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(SIGNATURE_SETTINGS_CONTRIBUTION)
    with pytest.raises(SettingsSchemaInvalidError):
        service.set_module_settings(
            "signature",
            {"require_password": "yes", "default_mode": "visual"},
            actor=SYSTEM_BACKEND_BOOTSTRAP_ACTOR,
            acknowledge_governance_change=True,
        )
