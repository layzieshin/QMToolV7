"""Bootstrap provenance: fresh vs pre-J03 vs post-J03 empty must not be guessed after migrate."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from interfaces.cli.bootstrap import build_container
from modules.documents.bootstrap_provenance import (
    DocumentsBootstrapProvenance,
    derive_documents_bootstrap_provenance,
)
from modules.documents.errors import ValidationError
from qm_platform.persistence.database_evolution import (
    DATABASE_PREFLIGHT_STATUSES_PORT,
    DatabaseEvolutionService,
    DatabaseSpec,
    DatabaseStatus,
    MigrationStep,
)
from qm_platform.persistence.path_resolver import resolve_bootstrap_absolute_path
from qm_platform.runtime import bootstrap as runtime_bootstrap


def _divergent_local_profiles(path: Path) -> None:
    bundled = Path("modules/documents/workflow_profiles.json")
    payload = json.loads(bundled.read_text(encoding="utf-8"))
    payload["profiles"][0]["label"] = "Local Divergent Long Release"
    payload["profiles"].append(
        {
            "profile_id": "local_only_bootstrap",
            "label": "Local Only Bootstrap",
            "control_class": "CONTROLLED",
            "phases": ["IN_PROGRESS", "APPROVED"],
            "four_eyes_required": False,
            "signature_required_transitions": [],
            "requires_editors": True,
            "requires_reviewers": False,
            "requires_approvers": False,
            "allows_content_changes": True,
            "release_evidence_mode": "WORKFLOW",
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _prepare_runtime(tmp_path: Path, monkeypatch):
    from modules.documents.module import create_documents_module_contract
    from qm_platform.runtime.lifecycle import LifecycleManager

    monkeypatch.setenv("QMTOOL_HOME", str(tmp_path))
    monkeypatch.delenv("QMTOOL_DOCUMENTS_LOCAL_WIRING", raising=False)
    container = build_container()
    lifecycle = LifecycleManager(container)
    # Replace client HTTP documents contract with backend SQLite ownership for provenance.
    for contract in runtime_bootstrap.core_module_contracts():
        if contract.module_id == "documents":
            lifecycle.prepare(create_documents_module_contract())
        else:
            lifecycle.prepare(contract)
    container.register_port("documents_runtime_owner", "backend")
    return container, lifecycle


def test_derive_provenance_mapping() -> None:
    missing = DatabaseStatus(
        database_id="documents",
        path="x",
        state="missing",
        current_version=0,
        target_version=2,
        pending_versions=(1, 2),
        integrity="not_run",
    )
    assert derive_documents_bootstrap_provenance(missing) == DocumentsBootstrapProvenance.FRESH_INSTALL

    v1 = DatabaseStatus(
        database_id="documents",
        path="x",
        state="pending",
        current_version=1,
        target_version=2,
        pending_versions=(2,),
        integrity="ok",
    )
    assert derive_documents_bootstrap_provenance(v1) == DocumentsBootstrapProvenance.PRE_J03_UPGRADE

    v2 = DatabaseStatus(
        database_id="documents",
        path="x",
        state="current",
        current_version=2,
        target_version=2,
        pending_versions=(),
        integrity="ok",
    )
    assert derive_documents_bootstrap_provenance(v2) == DocumentsBootstrapProvenance.POST_J03_SCHEMA


def test_fresh_app_home_with_divergent_local_profiles_uses_bundled_seed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container, lifecycle = _prepare_runtime(tmp_path, monkeypatch)
    local_profiles = resolve_bootstrap_absolute_path(tmp_path, "documents", "profiles_file")
    _divergent_local_profiles(local_profiles)

    runtime_bootstrap.activate_core_modules(container, lifecycle)

    statuses = container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
    provenance = derive_documents_bootstrap_provenance(statuses["documents"])
    assert provenance == DocumentsBootstrapProvenance.FRESH_INSTALL
    service = container.get_port("documents_service")
    store = service._profile_store
    codes = {row["profile_code"] for row in store.list_definitions()}
    assert "local_only_bootstrap" not in codes
    assert "long_release" in codes
    assert any(row.classification == "SEED" for row in store.last_import_report)
    assert all(row.source_path.endswith("workflow_profiles.json") for row in store.last_import_report)
    # Bundled seed path, not the divergent local app-home copy.
    assert not any("Local Divergent" in (row.block_reason or "") for row in store.last_import_report)
    assert service.get_profile("long_release").label != "Local Divergent Long Release"


def test_v1_documents_db_imports_local_profiles_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container, lifecycle = _prepare_runtime(tmp_path, monkeypatch)
    local_profiles = resolve_bootstrap_absolute_path(tmp_path, "documents", "profiles_file")
    _divergent_local_profiles(local_profiles)

    service, specs = runtime_bootstrap.configure_database_evolution(container, lifecycle)
    documents_spec = next(spec for spec in specs if spec.database_id == "documents")
    v1_only = DatabaseSpec(
        database_id="documents",
        path=documents_spec.path,
        migrations=(
            MigrationStep(
                version=1,
                name="initial",
                sql_path=Path("modules/documents/migrations/0001_initial.sql").resolve(),
            ),
        ),
    )
    DatabaseEvolutionService(app_home=tmp_path).migrate((v1_only,), reason="test_v1_seed")
    pre = service.status(documents_spec)
    assert pre.current_version == 1
    assert derive_documents_bootstrap_provenance(pre) == DocumentsBootstrapProvenance.PRE_J03_UPGRADE

    runtime_bootstrap.activate_core_modules(container, lifecycle)

    statuses = container.get_port(DATABASE_PREFLIGHT_STATUSES_PORT)
    provenance = derive_documents_bootstrap_provenance(statuses["documents"])
    assert provenance == DocumentsBootstrapProvenance.PRE_J03_UPGRADE
    store = container.get_port("documents_service")._profile_store
    codes = {row["profile_code"] for row in store.list_definitions()}
    assert "local_only_bootstrap" in codes
    assert any(row.classification == "MIGRATED" for row in store.last_import_report)
    assert any(
        row.import_status == "imported" and "local_only_bootstrap" == row.profile_id
        for row in store.last_import_report
    )
    assert store._is_pre_j03_upgrade is True


def test_post_j03_empty_profiles_are_not_treated_as_fresh_install(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container, lifecycle = _prepare_runtime(tmp_path, monkeypatch)
    local_profiles = resolve_bootstrap_absolute_path(tmp_path, "documents", "profiles_file")
    _divergent_local_profiles(local_profiles)

    service, specs = runtime_bootstrap.configure_database_evolution(container, lifecycle)
    service.migrate(specs, reason="test_post_j03_empty")
    documents_spec = next(spec for spec in specs if spec.database_id == "documents")
    pre = service.status(documents_spec)
    assert pre.current_version >= 2
    assert derive_documents_bootstrap_provenance(pre) == DocumentsBootstrapProvenance.POST_J03_SCHEMA

    with sqlite3.connect(documents_spec.path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "workflow_profile_definitions" in tables
        # Schema is J03 but profile stock is empty/manipulated.
        conn.execute("DELETE FROM workflow_profile_transitions")
        conn.execute("DELETE FROM workflow_profile_versions")
        conn.execute("DELETE FROM workflow_profile_definitions")
        conn.execute("DELETE FROM document_type_definitions")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM workflow_profile_definitions").fetchone()[0] == 0

    with pytest.raises(ValidationError, match="refusing silent re-seed"):
        runtime_bootstrap.activate_core_modules(container, lifecycle)
