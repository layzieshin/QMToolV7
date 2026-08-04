"""J01 residual reader (+) and legacy settings.json writer (-) contracts for J02."""

from __future__ import annotations

from pathlib import Path

import pytest

from modules.incident_management.module import INCIDENT_SETTINGS_CONTRIBUTION
from qm_platform.settings.errors import ResidualArchiveMissingError, ResidualPolicyReadonlyError
from qm_platform.settings.testing import build_settings_service_for_tests
from scripts.json_persistence_gate import evaluate_json_persistence_gate


def test_residual_reader_positive_loads_allowlisted_policy(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(
        tmp_path,
        residual_policy={
            "incident_management": {
                "effectiveness_delay": 12,
                "categories": ["Prozess", "Gerät"],
            }
        },
    )
    service.registry.register(INCIDENT_SETTINGS_CONTRIBUTION)
    settings = service.get_module_settings("incident_management")
    assert settings["effectiveness_delay"] == 12
    assert settings["categories"] == ["Prozess", "Gerät"]


def test_residual_owner_path_literal_allowed_in_j01_gate() -> None:
    payload = evaluate_json_persistence_gate(
        Path("."),
        mode="scratch",
        source_files={
            "qm_platform/settings/residual_store.py": (
                'path = "storage/platform/settings_residual_archive/settings.json"\n'
                "data = open(path, 'r', encoding='utf-8').read()\n"
            ),
        },
    )
    assert not any(
        f["kind"].startswith("unregistered_storage") or f["kind"].startswith("dynamic_storage")
        for f in payload["findings"]
    )


def test_residual_missing_fail_closed_when_module_declares_bucket_c(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(INCIDENT_SETTINGS_CONTRIBUTION)
    with pytest.raises(ResidualArchiveMissingError):
        service.get_module_settings("incident_management")


def test_residual_policy_writer_negative_via_settings_service(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(
        tmp_path,
        residual_policy={"incident_management": {"effectiveness_delay": 30}},
    )
    service.registry.register(INCIDENT_SETTINGS_CONTRIBUTION)
    with pytest.raises(ResidualPolicyReadonlyError):
        service.set_module_settings(
            "incident_management",
            {"effectiveness_delay": 99},
            actor="system:backend_bootstrap",
            acknowledge_governance_change=True,
        )


def test_legacy_settings_json_writer_negative_in_j01_gate() -> None:
    payload = evaluate_json_persistence_gate(
        Path("."),
        mode="scratch",
        source_files={
            "modules/demo/legacy_settings_writer.py": (
                'path = "storage/platform/settings.json"\n'
                "open(path, 'w').write('{}')\n"
            ),
        },
    )
    assert payload["ok"] is False
    assert any(
        f["kind"].startswith("unregistered_storage")
        or f["kind"] == "unregistered_storage_json_write"
        for f in payload["findings"]
    )


def test_residual_archive_path_remains_allowlisted_reader_surface() -> None:
    payload = evaluate_json_persistence_gate(
        Path("."),
        mode="scratch",
        source_files={
            "qm_platform/settings/residual_store.py": (
                'path = "storage/platform/settings_residual_archive/settings.json"\n'
                "data = open(path, 'r', encoding='utf-8').read()\n"
            ),
        },
    )
    assert not any(
        f["kind"].startswith("unregistered_storage") or f["kind"].startswith("dynamic_storage")
        for f in payload["findings"]
    )


def test_residual_archive_dynamic_writer_negative_in_j01_gate() -> None:
    payload = evaluate_json_persistence_gate(
        Path("."),
        mode="scratch",
        source_files={
            "modules/demo/residual_writer.py": (
                'path = "storage/platform/settings_residual_archive/settings.json"\n'
                "open(path, 'w').write('{}')\n"
            ),
        },
    )
    assert payload["ok"] is False
    assert any(
        f["kind"].startswith("unregistered_storage")
        or f["kind"] == "unregistered_storage_json_write"
        or "write" in f["kind"]
        for f in payload["findings"]
    )


def test_cutover_journal_and_backup_paths_stay_in_allowlist_categories() -> None:
    payload = evaluate_json_persistence_gate(Path("."), mode="repo")
    assert payload["ok"] is True
