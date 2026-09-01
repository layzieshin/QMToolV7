"""Installation maintenance mode and update rehearsal coordination (OPS00-D)."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qm_platform.blob.backup_orchestrator import (
    BackupOrchestratorError,
    BackupResult,
    RestoreResult,
    compute_app_release_fingerprint,
    create_backup,
    is_host_running_marker_present,
    release_identity_path,
    restore_backup_set,
)
from qm_platform.runtime.operation_lock import OperationLock, OperationLockError
from qm_platform.runtime.paths import resolve_home_path, runtime_home

_MAINTENANCE_DIR = "maintenance"
_ENABLED_FLAG = "enabled"
_RELEASE_SNAPSHOT_DIR = "release_snapshot"
_REHEARSAL_STATE_FILE = "rehearsal_state.json"
_PHASE_CANDIDATE_STAGED = "candidate_staged"
_PHASE_ABORTED = "aborted"


class MaintenanceError(RuntimeError):
    """Raised when maintenance or update rehearsal cannot proceed safely."""


@dataclass(frozen=True)
class UpdateRehearsalStartResult:
    backup_id: str
    backup_path: str
    prior_release_fingerprint: str
    candidate_release_fingerprint: str
    app_release_fingerprint: str
    schema_migration_fingerprint: str
    blob_count: int


@dataclass(frozen=True)
class UpdateRehearsalAbortResult:
    backup_id: str
    target_database: str
    restored_release_fingerprint: str
    restored_blob_count: int
    verified_artifact_count: int


def maintenance_root(app_home: Path | None = None) -> Path:
    home = app_home if app_home is not None else runtime_home()
    return resolve_home_path(home, _MAINTENANCE_DIR)


def maintenance_enabled_path(app_home: Path | None = None) -> Path:
    return maintenance_root(app_home) / _ENABLED_FLAG


def release_snapshot_dir(app_home: Path | None = None) -> Path:
    return maintenance_root(app_home) / _RELEASE_SNAPSHOT_DIR


def rehearsal_state_path(app_home: Path | None = None) -> Path:
    return maintenance_root(app_home) / _REHEARSAL_STATE_FILE


def is_maintenance_active(app_home: Path | None = None) -> bool:
    return maintenance_enabled_path(app_home).is_file()


def enter_maintenance(app_home: Path | None = None) -> None:
    path = maintenance_enabled_path(app_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("enabled\n", encoding="utf-8")


def exit_maintenance(app_home: Path | None = None) -> None:
    maintenance_enabled_path(app_home).unlink(missing_ok=True)


def _load_rehearsal_state(app_home: Path | None = None) -> dict[str, Any] | None:
    path = rehearsal_state_path(app_home)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MaintenanceError("rehearsal state file is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise MaintenanceError("rehearsal state file must be a JSON object")
    return payload


def _save_rehearsal_state(state: dict[str, Any], app_home: Path | None = None) -> None:
    root = maintenance_root(app_home)
    root.mkdir(parents=True, exist_ok=True)
    rehearsal_state_path(app_home).write_text(
        json.dumps(state, sort_keys=True, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def _clear_rehearsal_state(app_home: Path | None = None) -> None:
    rehearsal_state_path(app_home).unlink(missing_ok=True)


def get_expected_release_fingerprint(app_home: Path | None = None) -> str | None:
    state = _load_rehearsal_state(app_home)
    if state is None:
        return None
    if str(state.get("phase") or "") != _PHASE_ABORTED:
        return None
    expected = str(state.get("expected_app_release_fingerprint") or "").strip()
    if len(expected) != 64:
        return None
    return expected


def is_rehearsal_in_progress(app_home: Path | None = None) -> bool:
    state = _load_rehearsal_state(app_home)
    if state is None:
        return False
    return str(state.get("phase") or "") == _PHASE_CANDIDATE_STAGED


def _release_tree_root(app_home: Path) -> Path:
    return resolve_home_path(app_home, "release")


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def snapshot_release_tree(app_home: Path | None = None) -> str:
    """Copy the current release tree and return its fingerprint."""
    home = app_home if app_home is not None else runtime_home()
    release_root = _release_tree_root(home)
    if not release_identity_path(home).is_file():
        raise MaintenanceError("release identity file is missing; cannot snapshot release tree")
    prior_fp = compute_app_release_fingerprint(home)
    snapshot = release_snapshot_dir(home)
    _copy_tree(release_root, snapshot)
    return prior_fp


def restore_release_snapshot(app_home: Path | None = None) -> str:
    """Restore the snapshotted release tree byte-for-byte and return its fingerprint."""
    home = app_home if app_home is not None else runtime_home()
    snapshot = release_snapshot_dir(home)
    if not snapshot.is_dir():
        raise MaintenanceError("release snapshot is missing; cannot restore prior release tree")
    identity = snapshot / "identity"
    if not identity.is_file():
        raise MaintenanceError("release snapshot identity file is missing")
    release_root = _release_tree_root(home)
    _copy_tree(snapshot, release_root)
    return compute_app_release_fingerprint(home)


def _validate_candidate_release(candidate_dir: Path) -> None:
    candidate = Path(candidate_dir)
    if not candidate.is_dir():
        raise MaintenanceError("candidate release directory is missing")
    identity = candidate / "identity"
    if not identity.is_file():
        raise MaintenanceError("candidate release directory must contain identity file")


def replace_release_with_candidate(
    candidate_release_dir: Path,
    app_home: Path | None = None,
) -> str:
    """Replace the live release tree with candidate B and return its fingerprint."""
    home = app_home if app_home is not None else runtime_home()
    _validate_candidate_release(candidate_release_dir)
    release_root = _release_tree_root(home)
    if release_root.exists():
        shutil.rmtree(release_root)
    shutil.copytree(candidate_release_dir, release_root)
    return compute_app_release_fingerprint(home)


def _acquire_operation_lock(app_home: Path) -> OperationLock:
    lock = OperationLock(app_home=app_home)
    try:
        lock.acquire()
    except OperationLockError as exc:
        raise MaintenanceError(
            "update rehearsal refused while exclusive operation lock is held"
        ) from exc
    return lock


def _guard_start_rehearsal_state(app_home: Path) -> None:
    """Reject a second start while staged; allow only a missing or aborted terminal."""
    state = _load_rehearsal_state(app_home)
    if state is None:
        return
    phase = state.get("phase")
    if not isinstance(phase, str) or phase == "":
        raise MaintenanceError(
            "update rehearsal start refused: rehearsal state phase is missing or malformed"
        )
    if phase == _PHASE_CANDIDATE_STAGED:
        raise MaintenanceError(
            "update rehearsal start refused while a candidate is already staged"
        )
    if phase != _PHASE_ABORTED:
        raise MaintenanceError(
            "update rehearsal start refused: rehearsal state phase is unknown"
        )


def _canonical_staged_backup_dir(state: dict[str, Any] | None, supplied: Path) -> Path:
    """Bind caller backup_dir to the persisted staged directory before any restore."""
    if state is None:
        raise MaintenanceError("update rehearsal abort refused: rehearsal state is missing")
    phase = state.get("phase")
    if phase == _PHASE_ABORTED:
        raise MaintenanceError("update rehearsal abort refused: rehearsal already aborted")
    if phase != _PHASE_CANDIDATE_STAGED:
        if not isinstance(phase, str) or phase == "":
            raise MaintenanceError(
                "update rehearsal abort refused: rehearsal state phase is missing or malformed"
            )
        raise MaintenanceError(
            "update rehearsal abort refused: rehearsal state phase is unknown"
        )
    raw_path = state.get("backup_path")
    if not isinstance(raw_path, str) or raw_path.strip() == "":
        raise MaintenanceError(
            "update rehearsal abort refused: staged backup_path is missing or invalid"
        )
    try:
        persisted = Path(raw_path).resolve(strict=True)
        supplied_resolved = Path(supplied).resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise MaintenanceError(
            "update rehearsal abort refused: backup path does not exist or is invalid"
        ) from exc
    if not persisted.is_dir():
        raise MaintenanceError(
            "update rehearsal abort refused: staged backup_path is not a directory"
        )
    if not supplied_resolved.is_dir():
        raise MaintenanceError(
            "update rehearsal abort refused: supplied backup path is not a directory"
        )
    try:
        same = persisted.samefile(supplied_resolved)
    except OSError as exc:
        raise MaintenanceError(
            "update rehearsal abort refused: backup path cannot be compared"
        ) from exc
    if not same:
        raise MaintenanceError(
            "update rehearsal abort refused: backup directory does not match the staged backup set"
        )
    return persisted


def start_update_rehearsal(
    *,
    candidate_release_dir: Path,
    source_dsn: str,
    metadata_dsn: str,
    app_home: Path | None = None,
) -> UpdateRehearsalStartResult:
    """Snapshot release A, seal a C backup set, and stage candidate release B."""
    home = app_home if app_home is not None else runtime_home()
    lock = _acquire_operation_lock(home)
    try:
        _guard_start_rehearsal_state(home)
        if is_host_running_marker_present(home):
            raise MaintenanceError(
                "update rehearsal refused while backend host running marker is present; "
                "stop and drain the host before starting"
            )
        _validate_candidate_release(candidate_release_dir)
        prior_fp = snapshot_release_tree(home)
        try:
            backup = create_backup(
                source_dsn=source_dsn,
                metadata_dsn=metadata_dsn,
                app_home=home,
                held_operation_lock=lock,
            )
        except BackupOrchestratorError as exc:
            raise MaintenanceError(str(exc)) from exc
        try:
            candidate_fp = replace_release_with_candidate(candidate_release_dir, home)
            _save_rehearsal_state(
                {
                    "phase": _PHASE_CANDIDATE_STAGED,
                    "backup_id": backup.backup_id,
                    "backup_path": backup.backup_path,
                    "prior_release_fingerprint": prior_fp,
                    "candidate_release_fingerprint": candidate_fp,
                },
                home,
            )
        except Exception:
            restore_release_snapshot(home)
            raise
    finally:
        lock.release()

    return UpdateRehearsalStartResult(
        backup_id=backup.backup_id,
        backup_path=backup.backup_path,
        prior_release_fingerprint=prior_fp,
        candidate_release_fingerprint=candidate_fp,
        app_release_fingerprint=backup.app_release_fingerprint,
        schema_migration_fingerprint=backup.schema_migration_fingerprint,
        blob_count=backup.blob_count,
    )


def abort_update_rehearsal(
    *,
    backup_dir: Path,
    target_admin_dsn: str,
    target_database: str,
    destination_blob_root: Path,
    app_home: Path | None = None,
) -> UpdateRehearsalAbortResult:
    """Abort rehearsal: restore release tree A and the sealed C PG+Blob backup set."""
    home = app_home if app_home is not None else runtime_home()
    lock = _acquire_operation_lock(home)
    try:
        canonical_backup = _canonical_staged_backup_dir(
            _load_rehearsal_state(home),
            Path(backup_dir),
        )
        restored_fp = restore_release_snapshot(home)
        try:
            restore_result: RestoreResult = restore_backup_set(
                backup_dir=canonical_backup,
                target_admin_dsn=target_admin_dsn,
                target_database=target_database,
                destination_blob_root=destination_blob_root,
                app_home=home,
                held_operation_lock=lock,
            )
        except BackupOrchestratorError as exc:
            raise MaintenanceError(str(exc)) from exc
        state = _load_rehearsal_state(home) or {}
        state.update(
            {
                "phase": _PHASE_ABORTED,
                "expected_app_release_fingerprint": restored_fp,
            }
        )
        _save_rehearsal_state(state, home)
    finally:
        lock.release()

    return UpdateRehearsalAbortResult(
        backup_id=restore_result.backup_id,
        target_database=restore_result.target_database,
        restored_release_fingerprint=restored_fp,
        restored_blob_count=restore_result.restored_blob_count,
        verified_artifact_count=restore_result.verified_artifact_count,
    )
