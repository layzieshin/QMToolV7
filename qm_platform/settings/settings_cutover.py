"""Journaled settings.json cutover: full Bucket-B import + complete residual C."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from qm_platform.settings.actors import MIGRATION_SETTINGS_IMPORT_ACTOR
from qm_platform.settings.atomic_io import atomic_write_text
from qm_platform.settings.errors import (
    ResidualPolicyMissingError,
    SettingsCutoverIncompleteError,
    SettingsDomainError,
    UnknownSettingKeyError,
)
from qm_platform.settings.expected_keys import (
    build_complete_bucket_b_payloads,
    build_complete_bucket_c_payloads_from_defaults,
    expected_residual_keys_by_module,
    expected_technical_keys_by_module,
)
from qm_platform.settings.key_classification import SettingBucket, classify_key
from qm_platform.settings.residual_store import (
    ResidualSettingsStore,
    write_residual_archive_bytes,
)
from qm_platform.settings.settings_service import SettingsService
from qm_platform.settings.sqlite_settings_repository import SqliteSettingsRepository

LEGACY_SETTINGS_REL = "storage/platform/settings.json"
CUTOVER_JOURNAL_REL = "storage/platform/settings_cutover_journal.json"

JOURNAL_STATUS_IN_PROGRESS = "in_progress"
JOURNAL_STATUS_COMPLETED = "completed"
JOURNAL_VERSION = 1


class SettingsCutoverError(SettingsDomainError):
    code = "settings_cutover_failed"


@dataclass
class SettingsCutoverReport:
    archived: bool = False
    archive_sha256: str | None = None
    skipped_bootstrap: list[str] = field(default_factory=list)
    residual_policy_keys: list[str] = field(default_factory=list)
    imported_modules: list[str] = field(default_factory=list)
    unknown_keys: list[str] = field(default_factory=list)
    skipped_completed: bool = False
    resumed: bool = False
    seeded_fresh_residual: bool = False
    pre_cutover_backup_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "archived": self.archived,
            "archive_sha256": self.archive_sha256,
            "skipped_bootstrap": list(self.skipped_bootstrap),
            "residual_policy_keys": list(self.residual_policy_keys),
            "imported_modules": list(self.imported_modules),
            "unknown_keys": list(self.unknown_keys),
            "skipped_completed": self.skipped_completed,
            "resumed": self.resumed,
            "seeded_fresh_residual": self.seeded_fresh_residual,
            "pre_cutover_backup_id": self.pre_cutover_backup_id,
        }


def legacy_settings_path(app_home: Path) -> Path:
    return Path(app_home) / LEGACY_SETTINGS_REL


def cutover_journal_path(app_home: Path) -> Path:
    return Path(app_home) / CUTOVER_JOURNAL_REL


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_journal(app_home: Path) -> dict[str, Any] | None:
    path = cutover_journal_path(app_home)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SettingsCutoverIncompleteError(f"cutover journal is damaged: {exc}") from exc
    if not isinstance(payload, dict):
        raise SettingsCutoverIncompleteError("cutover journal root must be an object")
    status = payload.get("status")
    if status not in {JOURNAL_STATUS_IN_PROGRESS, JOURNAL_STATUS_COMPLETED}:
        raise SettingsCutoverIncompleteError(f"cutover journal has invalid status: {status!r}")
    if int(payload.get("version") or 0) != JOURNAL_VERSION:
        raise SettingsCutoverIncompleteError("cutover journal version unsupported")
    return payload


def _write_journal(app_home: Path, payload: dict[str, Any]) -> None:
    path = cutover_journal_path(app_home)
    payload = dict(payload)
    payload["updated_at"] = _utc_now()
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
    )


def _classify_source(
    payload: dict[str, Any],
) -> tuple[list[str], list[str], list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    unknown: list[str] = []
    bootstrap: list[str] = []
    residual_keys: list[str] = []
    technical_by_module: dict[str, dict[str, Any]] = {}
    residual_by_module: dict[str, dict[str, Any]] = {}
    for module_id, blob in payload.items():
        if not isinstance(blob, dict):
            raise SettingsCutoverError(f"module settings must be an object: {module_id}")
        for key, value in blob.items():
            bucket = classify_key(str(module_id), str(key))
            ref = f"{module_id}.{key}"
            if bucket is None:
                unknown.append(ref)
                continue
            if bucket is SettingBucket.BOOTSTRAP:
                bootstrap.append(ref)
                continue
            if bucket is SettingBucket.RESIDUAL_POLICY:
                residual_keys.append(ref)
                residual_by_module.setdefault(str(module_id), {})[str(key)] = value
                continue
            technical_by_module.setdefault(str(module_id), {})[str(key)] = value
    return (
        sorted(unknown),
        sorted(bootstrap),
        sorted(residual_keys),
        technical_by_module,
        residual_by_module,
    )


def _assert_legacy_c_complete(
    settings_service: SettingsService,
    residual_by_module: dict[str, dict[str, Any]],
) -> None:
    expected = expected_residual_keys_by_module(settings_service.registry)
    missing: list[str] = []
    for module_id, keys in expected.items():
        blob = residual_by_module.get(module_id) or {}
        for key in keys:
            if key not in blob:
                missing.append(f"{module_id}.{key}")
    if missing:
        raise ResidualPolicyMissingError(
            "legacy settings.json missing required Bucket-C keys; refusing to invent values: "
            + ", ".join(sorted(missing))
        )


def _anchor_residual_hash(repository: SqliteSettingsRepository, digest: str) -> None:
    repository.set_integrity(
        SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256,
        digest,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )


def _attach_with_anchored_residual(
    settings_service: SettingsService,
    app_home: Path,
    repository: SqliteSettingsRepository,
    *,
    cutover_completed: bool,
) -> ResidualSettingsStore:
    digest = repository.get_integrity(SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256)
    residual = ResidualSettingsStore.under_app_home(app_home, expected_sha256=digest)
    settings_service.attach_persistence(
        repository,
        residual,
        cutover_completed=cutover_completed,
    )
    return residual


def _module_b_fully_present(
    settings_service: SettingsService,
    module_id: str,
    expected_values: dict[str, Any],
) -> bool:
    repository = settings_service.repository
    if repository is None:
        return False
    loaded = repository.load_module_technical(module_id)
    if set(expected_values) - set(loaded):
        return False
    for key, value in expected_values.items():
        if loaded.get(key) != value:
            return False
    return True


def _import_bucket_b_modules(
    settings_service: SettingsService,
    payloads: dict[str, dict[str, Any]],
    *,
    already_imported: set[str],
    journal: dict[str, Any],
    app_home: Path,
    fail_after_module: str | None,
    fail_before_journal_update: str | None,
) -> list[str]:
    imported: list[str] = []
    for module_id in sorted(payloads):
        values = payloads[module_id]
        if module_id in already_imported and _module_b_fully_present(
            settings_service, module_id, values
        ):
            imported.append(module_id)
            continue
        settings_service.set_module_settings(
            module_id,
            values,
            actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
            acknowledge_governance_change=True,
            reason="j02_settings_cutover",
        )
        imported.append(module_id)
        if fail_before_journal_update is not None and module_id == fail_before_journal_update:
            raise SettingsCutoverError(
                f"injected cutover failure before journal update: {module_id}"
            )
        journal["imported_modules"] = list(imported)
        _write_journal(app_home, journal)
        if fail_after_module is not None and module_id == fail_after_module:
            raise SettingsCutoverError(
                f"injected cutover failure after module import: {module_id}"
            )
    return imported


def seed_residual_from_contribution_defaults(
    app_home: Path,
    settings_service: SettingsService,
    *,
    fail_after_module: str | None = None,
) -> SettingsCutoverReport:
    """Fresh install: seed complete C residual and persist all Bucket-B defaults."""
    report = SettingsCutoverReport(seeded_fresh_residual=True)
    repository = settings_service.repository
    if repository is None:
        raise SettingsCutoverError("settings persistence repository missing for residual seed")

    c_payloads = build_complete_bucket_c_payloads_from_defaults(settings_service.registry)
    raw = json.dumps(c_payloads, ensure_ascii=True, indent=2, sort_keys=True).encode("utf-8")
    _, digest = write_residual_archive_bytes(app_home, raw)
    _anchor_residual_hash(repository, digest)
    _attach_with_anchored_residual(
        settings_service, app_home, repository, cutover_completed=False
    )

    b_payloads = build_complete_bucket_b_payloads(settings_service.registry)
    journal = {
        "version": JOURNAL_VERSION,
        "status": JOURNAL_STATUS_IN_PROGRESS,
        "cutover_id": str(uuid.uuid4()),
        "source_path": None,
        "source_sha256": None,
        "planned_modules": sorted(b_payloads),
        "imported_modules": [],
        "archive_sha256": digest,
    }
    _write_journal(app_home, journal)
    imported = _import_bucket_b_modules(
        settings_service,
        b_payloads,
        already_imported=set(),
        journal=journal,
        app_home=app_home,
        fail_after_module=fail_after_module,
        fail_before_journal_update=None,
    )
    report.imported_modules = imported
    report.archived = True
    report.archive_sha256 = digest

    settings_service._assert_residual_complete()
    settings_service._assert_no_overlap()
    repository.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        JOURNAL_STATUS_COMPLETED,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    journal["status"] = JOURNAL_STATUS_COMPLETED
    journal["imported_modules"] = imported
    _write_journal(app_home, journal)
    _attach_with_anchored_residual(
        settings_service, app_home, repository, cutover_completed=True
    )
    return report


def run_settings_json_cutover(
    app_home: Path,
    settings_service: SettingsService,
    *,
    source: Path | None = None,
    fail_after_module: str | None = None,
    fail_before_journal_update: str | None = None,
    fail_after_archive: bool = False,
    fail_after_hash_anchor: bool = False,
    pre_mutation_backup: Callable[[], str | None] | None = None,
) -> SettingsCutoverReport:
    """Archive legacy settings.json and import complete Bucket-B for all modules."""
    home = Path(app_home)
    report = SettingsCutoverReport()
    repository = settings_service.repository
    if repository is None:
        raise SettingsCutoverError("settings persistence repository missing for cutover")

    cutover_status = repository.get_integrity(SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS)
    journal = _read_journal(home)
    if (
        cutover_status == JOURNAL_STATUS_COMPLETED
        and journal
        and journal.get("status") == JOURNAL_STATUS_COMPLETED
    ):
        report.skipped_completed = True
        report.archive_sha256 = repository.get_integrity(
            SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256
        )
        _attach_with_anchored_residual(
            settings_service, home, repository, cutover_completed=True
        )
        return report
    if journal and journal.get("status") == JOURNAL_STATUS_COMPLETED and cutover_status != JOURNAL_STATUS_COMPLETED:
        raise SettingsCutoverIncompleteError(
            "cutover journal is completed but DB cutover status is not; refusing auto-complete"
        )

    src = Path(source) if source is not None else legacy_settings_path(home)
    resuming = bool(journal and journal.get("status") == JOURNAL_STATUS_IN_PROGRESS)
    if resuming:
        report.resumed = True
        src = Path(str(journal.get("source_path") or src))
        if not src.is_file():
            raise SettingsCutoverIncompleteError(
                "incomplete settings cutover journal but source settings.json is missing"
            )
        expected_source_sha = str(journal.get("source_sha256") or "")
        actual_source_sha = _sha256_file(src)
        if expected_source_sha and expected_source_sha != actual_source_sha:
            raise SettingsCutoverIncompleteError(
                "legacy settings.json changed during cutover resume; refusing to continue"
            )
    elif not src.is_file():
        return report

    payload = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SettingsCutoverError("settings.json root must be an object")

    unknown, bootstrap, residual_keys, technical_overrides, residual_by_module = _classify_source(
        payload
    )
    report.unknown_keys = unknown
    report.skipped_bootstrap = bootstrap
    report.residual_policy_keys = residual_keys
    if unknown:
        raise UnknownSettingKeyError(
            "settings cutover blocked by unknown keys: " + ", ".join(unknown)
        )
    _assert_legacy_c_complete(settings_service, residual_by_module)

    b_payloads = build_complete_bucket_b_payloads(
        settings_service.registry,
        overrides_by_module=technical_overrides,
    )
    planned = sorted(b_payloads)

    if resuming:
        planned_journal = [str(item) for item in journal.get("planned_modules") or []]
        if planned_journal != planned:
            raise SettingsCutoverIncompleteError(
                "incomplete cutover journal planned_modules mismatch"
            )
        already = {str(item) for item in journal.get("imported_modules") or []}
        archive_sha = str(journal.get("archive_sha256") or "")
        if not archive_sha:
            raise SettingsCutoverIncompleteError("incomplete cutover journal missing archive_sha256")
        residual_path = ResidualSettingsStore.under_app_home(home).archive_path
        if not residual_path.is_file():
            raise SettingsCutoverIncompleteError("incomplete cutover: residual archive missing")
        if ResidualSettingsStore.under_app_home(home).sha256() != archive_sha:
            raise SettingsCutoverIncompleteError(
                "incomplete cutover: residual archive sha256 does not match journal"
            )
        db_hash = repository.get_integrity(SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256)
        if db_hash != archive_sha:
            raise SettingsCutoverIncompleteError(
                "incomplete cutover: DB residual hash anchor mismatch"
            )
        _attach_with_anchored_residual(
            settings_service, home, repository, cutover_completed=False
        )
        report.archived = True
        report.archive_sha256 = archive_sha
        active_journal = dict(journal)
    else:
        if pre_mutation_backup is not None:
            report.pre_cutover_backup_id = pre_mutation_backup()
        source_sha = _sha256_file(src)
        already = set()
        active_journal = {
            "version": JOURNAL_VERSION,
            "status": JOURNAL_STATUS_IN_PROGRESS,
            "cutover_id": str(uuid.uuid4()),
            "source_path": str(src),
            "source_sha256": source_sha,
            "planned_modules": planned,
            "imported_modules": [],
            "archive_sha256": None,
            "pre_cutover_backup_id": report.pre_cutover_backup_id,
        }
        _write_journal(home, active_journal)
        # Residual archive holds Bucket-C only (never full legacy A/B/C blob).
        residual_raw = json.dumps(
            residual_by_module,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")
        _, digest = write_residual_archive_bytes(home, residual_raw)
        if fail_after_archive:
            raise SettingsCutoverError("injected cutover failure after archive")
        _anchor_residual_hash(repository, digest)
        active_journal["archive_sha256"] = digest
        _write_journal(home, active_journal)
        if fail_after_hash_anchor:
            raise SettingsCutoverError("injected cutover failure after hash anchor")
        _attach_with_anchored_residual(
            settings_service, home, repository, cutover_completed=False
        )
        report.archived = True
        report.archive_sha256 = digest

    imported = _import_bucket_b_modules(
        settings_service,
        b_payloads,
        already_imported=already,
        journal=active_journal,
        app_home=home,
        fail_after_module=fail_after_module,
        fail_before_journal_update=fail_before_journal_update,
    )
    report.imported_modules = imported
    settings_service._assert_residual_complete()
    settings_service._assert_no_overlap()
    settings_service.assert_bucket_b_complete()

    repository.set_integrity(
        SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS,
        JOURNAL_STATUS_COMPLETED,
        actor=MIGRATION_SETTINGS_IMPORT_ACTOR,
    )
    active_journal["status"] = JOURNAL_STATUS_COMPLETED
    active_journal["imported_modules"] = imported
    _write_journal(home, active_journal)
    _attach_with_anchored_residual(
        settings_service, home, repository, cutover_completed=True
    )
    return report


def ensure_settings_residual_ready(
    app_home: Path,
    settings_service: SettingsService,
    *,
    source: Path | None = None,
    pre_mutation_backup: Callable[[], str | None] | None = None,
) -> SettingsCutoverReport:
    """Attach residual with DB-anchored hash; cutover, resume, or seed as needed."""
    home = Path(app_home)
    repository = settings_service.repository
    if repository is None:
        raise SettingsCutoverError("settings persistence repository missing")

    journal = _read_journal(home)
    if journal and journal.get("status") == JOURNAL_STATUS_IN_PROGRESS:
        return run_settings_json_cutover(
            home,
            settings_service,
            source=source,
            pre_mutation_backup=None,
        )

    cutover_status = repository.get_integrity(SqliteSettingsRepository.INTEGRITY_CUTOVER_STATUS)
    residual_path = ResidualSettingsStore.under_app_home(home).archive_path
    src = Path(source) if source is not None else legacy_settings_path(home)

    if cutover_status == JOURNAL_STATUS_COMPLETED:
        if not journal or journal.get("status") != JOURNAL_STATUS_COMPLETED:
            raise SettingsCutoverIncompleteError(
                "DB cutover completed but journal is missing or not completed"
            )
        digest = repository.get_integrity(SqliteSettingsRepository.INTEGRITY_RESIDUAL_SHA256)
        if digest is None or not residual_path.is_file():
            raise SettingsCutoverIncompleteError(
                "cutover marked completed but residual archive or DB hash anchor is missing"
            )
        _attach_with_anchored_residual(
            settings_service, home, repository, cutover_completed=True
        )
        return SettingsCutoverReport(skipped_completed=True, archive_sha256=digest)

    if src.is_file():
        return run_settings_json_cutover(
            home,
            settings_service,
            source=src,
            pre_mutation_backup=pre_mutation_backup,
        )

    if residual_path.is_file():
        raise SettingsCutoverIncompleteError(
            "residual archive exists without completed cutover status; refusing silent skip"
        )

    return seed_residual_from_contribution_defaults(home, settings_service)
