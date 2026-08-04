"""J02.1 settings cutover: full B/C, resume, hash anchor, atomic journal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.documents.module import DOCUMENTS_SETTINGS_CONTRIBUTION
from modules.incident_management.module import INCIDENT_SETTINGS_CONTRIBUTION
from modules.signature.module import SIGNATURE_SETTINGS_CONTRIBUTION
from modules.training.module import TRAINING_SETTINGS_CONTRIBUTION
from modules.usermanagement.module import USERMANAGEMENT_SETTINGS_CONTRIBUTION
from qm_platform.settings.errors import (
    ResidualArchiveIntegrityError,
    ResidualArchiveMissingError,
    ResidualPolicyMissingError,
    SettingsCutoverIncompleteError,
    UnknownSettingKeyError,
)
from qm_platform.settings.expected_keys import (
    expected_residual_keys_by_module,
    expected_technical_keys_by_module,
)
from qm_platform.settings.key_classification import SettingBucket, classify_key
from qm_platform.settings.residual_store import ResidualSettingsStore
from qm_platform.settings.settings_cutover import (
    SettingsCutoverError,
    cutover_journal_path,
    ensure_settings_residual_ready,
    run_settings_json_cutover,
    seed_residual_from_contribution_defaults,
)
from qm_platform.settings.settings_registry import SettingsRegistry
from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository
from qm_platform.settings.testing import build_settings_service_for_tests

_CORE_CONTRIBUTIONS = (
    USERMANAGEMENT_SETTINGS_CONTRIBUTION,
    SIGNATURE_SETTINGS_CONTRIBUTION,
    TRAINING_SETTINGS_CONTRIBUTION,
    DOCUMENTS_SETTINGS_CONTRIBUTION,
    INCIDENT_SETTINGS_CONTRIBUTION,
)


def _register_core(service) -> None:
    for contribution in _CORE_CONTRIBUTIONS:
        if service.registry.get(contribution.module_id) is None:
            service.registry.register(contribution)


def _complete_legacy_settings(**module_overrides: dict) -> dict:
    """Legacy settings.json with full A/B/C seed for registered core modules."""
    registry = SettingsRegistry()
    for contribution in _CORE_CONTRIBUTIONS:
        registry.register(contribution)
    from qm_platform.settings.expected_keys import (
        build_complete_bucket_b_payloads,
        build_complete_bucket_c_payloads_from_defaults,
    )

    payload: dict = {}
    for module_id, blob in build_complete_bucket_b_payloads(registry).items():
        payload.setdefault(module_id, {}).update(blob)
    for module_id, blob in build_complete_bucket_c_payloads_from_defaults(registry).items():
        payload.setdefault(module_id, {}).update(blob)
    for contribution in _CORE_CONTRIBUTIONS:
        for key, value in (contribution.defaults or {}).items():
            if classify_key(contribution.module_id, key) is SettingBucket.BOOTSTRAP:
                payload.setdefault(contribution.module_id, {})[key] = value
    for module_id, blob in module_overrides.items():
        payload.setdefault(module_id, {}).update(blob)
    return payload


def test_cutover_persists_full_bucket_b_for_all_registered_modules(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    legacy = _complete_legacy_settings(
        usermanagement={"seed_mode": "hardened", "dev_mode": False},
        signature={"require_password": False, "default_mode": "visual"},
    )
    legacy.pop("training", None)
    source.write_text(json.dumps(legacy, ensure_ascii=True), encoding="utf-8")

    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    report = run_settings_json_cutover(tmp_path, service)
    assert report.archived is True
    assert "training" in report.imported_modules

    expected = expected_technical_keys_by_module(service.registry)
    assert service.repository is not None
    for module_id, keys in expected.items():
        loaded = service.repository.load_module_technical(module_id)
        for key in keys:
            assert key in loaded, f"missing B key {module_id}.{key}"
            assert classify_key(module_id, key) is SettingBucket.TECHNICAL
        for key in loaded:
            assert classify_key(module_id, key) is SettingBucket.TECHNICAL
    import sqlite3
    from contextlib import closing

    assert service.repository is not None
    with closing(sqlite3.connect(service.repository.db_path)) as conn:
        actors = {
            str(row[0])
            for row in conn.execute(
                "SELECT DISTINCT changed_by_user_id FROM platform_setting_revisions"
            ).fetchall()
        }
    assert "migration:j02-settings-import" in actors
    assert service.get_module_settings("signature")["require_password"] is False
    assert service.get_module_settings("usermanagement")["seed_mode"] == "hardened"
    assert service.get_module_settings("training")["questions_per_quiz"] == 3


def test_cutover_blocks_incomplete_legacy_bucket_c(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    source.write_text(
        json.dumps(
            {
                "usermanagement": {
                    "users_db_path": "storage/platform/users.db",
                    "seed_mode": "hardened",
                    "dev_mode": False,
                }
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    with pytest.raises(ResidualPolicyMissingError):
        run_settings_json_cutover(tmp_path, service)


def test_fresh_seed_writes_complete_b_and_c(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    report = seed_residual_from_contribution_defaults(tmp_path, service)
    assert report.seeded_fresh_residual is True
    expected_b = expected_technical_keys_by_module(service.registry)
    assert service.repository is not None
    for module_id, keys in expected_b.items():
        loaded = service.repository.load_module_technical(module_id)
        assert set(keys) <= set(loaded)
    residual = ResidualSettingsStore.under_app_home(
        tmp_path,
        expected_sha256=service.repository.get_integrity(
            SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256
        ),
    )
    residual.assert_complete_against_expected(
        expected_residual_keys_by_module(service.registry)
    )


def test_cutover_resumes_after_failure_between_module_imports(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(_complete_legacy_settings(), ensure_ascii=True), encoding="utf-8")
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)

    first_module = sorted(expected_technical_keys_by_module(service.registry))[0]
    with pytest.raises(SettingsCutoverError, match="injected cutover failure"):
        run_settings_json_cutover(tmp_path, service, fail_after_module=first_module)

    journal = json.loads(cutover_journal_path(tmp_path).read_text(encoding="utf-8"))
    assert journal["status"] == "in_progress"
    assert first_module in journal["imported_modules"]
    assert journal.get("source_sha256")
    assert journal.get("archive_sha256")
    assert journal.get("cutover_id")

    resumed = run_settings_json_cutover(tmp_path, service)
    assert resumed.resumed is True
    assert set(resumed.imported_modules) == set(
        expected_technical_keys_by_module(service.registry)
    )
    assert (
        service.repository.get_integrity(SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS)
        == "completed"
    )


def test_cutover_resume_blocks_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(_complete_legacy_settings(), ensure_ascii=True), encoding="utf-8")
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    first_module = sorted(expected_technical_keys_by_module(service.registry))[0]
    with pytest.raises(SettingsCutoverError):
        run_settings_json_cutover(tmp_path, service, fail_after_module=first_module)
    source.write_text(
        json.dumps(
            _complete_legacy_settings(usermanagement={"seed_mode": "hardened", "dev_mode": True}),
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    with pytest.raises(SettingsCutoverIncompleteError, match="changed"):
        run_settings_json_cutover(tmp_path, service)


def test_cutover_abort_after_archive_blocks_resume_without_hash(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(_complete_legacy_settings(), ensure_ascii=True), encoding="utf-8")
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    with pytest.raises(SettingsCutoverError, match="after archive"):
        run_settings_json_cutover(tmp_path, service, fail_after_archive=True)
    journal = json.loads(cutover_journal_path(tmp_path).read_text(encoding="utf-8"))
    assert journal["status"] == "in_progress"
    assert journal.get("archive_sha256") is None
    with pytest.raises(SettingsCutoverIncompleteError, match="archive_sha256"):
        run_settings_json_cutover(tmp_path, service)


def test_cutover_resumes_after_hash_anchor_abort(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(_complete_legacy_settings(), ensure_ascii=True), encoding="utf-8")
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    with pytest.raises(SettingsCutoverError, match="after hash anchor"):
        run_settings_json_cutover(tmp_path, service, fail_after_hash_anchor=True)
    resumed = run_settings_json_cutover(tmp_path, service)
    assert resumed.resumed is True
    assert (
        service.repository.get_integrity(SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS)
        == "completed"
    )


def test_damaged_journal_blocks(tmp_path: Path) -> None:
    path = cutover_journal_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    with pytest.raises(SettingsCutoverIncompleteError, match="damaged"):
        ensure_settings_residual_ready(tmp_path, service)


def test_residual_hash_rejects_paired_sidecar_and_archive_tamper(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    seed_residual_from_contribution_defaults(tmp_path, service)
    assert service.repository is not None
    anchored = service.repository.get_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256
    )
    residual = ResidualSettingsStore.under_app_home(tmp_path, expected_sha256=anchored)
    residual.verify()
    residual.archive_path.write_text('{"tampered": true}', encoding="utf-8")
    residual.hash_path.write_text(
        f"{residual.sha256()}  settings.json\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(ResidualArchiveIntegrityError, match="mismatch"):
        residual.verify()


def test_bucket_c_without_residual_is_fail_closed(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    service.registry.register(USERMANAGEMENT_SETTINGS_CONTRIBUTION)
    with pytest.raises(ResidualArchiveMissingError):
        service.get_module_settings("usermanagement")


def test_partial_residual_blocks_attach(tmp_path: Path) -> None:
    from qm_platform.settings.testing import write_residual_policy_archive

    service = build_settings_service_for_tests(tmp_path)
    assert service.repository is not None
    write_residual_policy_archive(
        tmp_path,
        {"usermanagement": {"password_policy": {"min_length": 8}}},
        repository=service.repository,
        merge_complete_defaults=False,
    )
    _register_core(service)
    with pytest.raises(ResidualPolicyMissingError):
        service.attach_persistence(
            service.repository,
            ResidualSettingsStore.under_app_home(
                tmp_path,
                expected_sha256=service.repository.get_integrity(
                    SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256
                ),
            ),
            cutover_completed=False,
        )


def test_cutover_rejects_unknown_keys(tmp_path: Path) -> None:
    source = tmp_path / "storage" / "platform" / "settings.json"
    source.parent.mkdir(parents=True)
    legacy = _complete_legacy_settings()
    legacy["signature"]["mystery"] = 1
    source.write_text(json.dumps(legacy, ensure_ascii=True), encoding="utf-8")
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    with pytest.raises(UnknownSettingKeyError):
        run_settings_json_cutover(tmp_path, service)


def test_journal_completed_without_db_status_blocks(tmp_path: Path) -> None:
    service = build_settings_service_for_tests(tmp_path)
    _register_core(service)
    seed_residual_from_contribution_defaults(tmp_path, service)
    assert service.repository is not None
    service.repository.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        "in_progress",
        actor="migration:j02-settings-import",
    )
    with pytest.raises(SettingsCutoverIncompleteError, match="refusing auto-complete"):
        run_settings_json_cutover(tmp_path, service)


def test_bucket_partitions_cover_cutover_sample() -> None:
    assert classify_key("signature", "require_password") is SettingBucket.TECHNICAL
    assert classify_key("usermanagement", "users_db_path") is SettingBucket.BOOTSTRAP
    assert classify_key("usermanagement", "password_policy") is SettingBucket.RESIDUAL_POLICY
