from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.json_persistence_gate import (
    ALLOWED_DOMAIN_JSON_FILES,
    ALLOWED_JSON_COLUMNS,
    apply_sql_to_table_state,
    evaluate_json_persistence_gate,
)


ROOT = Path(__file__).resolve().parents[2]


def test_repo_mode_is_green_on_current_tree() -> None:
    payload = evaluate_json_persistence_gate(ROOT, mode="repo", base_ref="HEAD")
    assert payload["ok"] is True, payload
    assert payload["checks"]["no_unregistered_json_persistence"] is True


def test_allowlist_entries_are_not_dead() -> None:
    payload = evaluate_json_persistence_gate(ROOT, mode="repo", base_ref="HEAD")
    kinds = {item["kind"] for item in payload["findings"]}
    assert "dead_allowlist_file" not in kinds
    assert "dead_allowlist_column" not in kinds
    for path in ALLOWED_DOMAIN_JSON_FILES:
        assert (ROOT / path).is_file(), path
    found = set(payload["diagnostics"]["existing_allowed_columns"])
    assert found == set(ALLOWED_JSON_COLUMNS)


def test_scratch_mode_requires_source_files() -> None:
    payload = evaluate_json_persistence_gate(ROOT, mode="scratch")
    assert payload["ok"] is False
    assert payload["findings"][0]["kind"] == "gate_error"


def test_scratch_rejects_new_domain_json_and_jsonl() -> None:
    base = {
        "license/license.json": "{}",
        "qm_platform/persistence/migration_manifest.json": "{}",
        "modules/documents/workflow_profiles.json": "{}",
        "modules/documents/migrations/0001_initial.sql": (
            "CREATE TABLE document_headers (\n"
            "  document_id TEXT,\n"
            "  distribution_roles_json TEXT,\n"
            "  distribution_sites_json TEXT,\n"
            "  distribution_departments_json TEXT\n"
            ");\n"
            "CREATE TABLE document_versions (\n"
            "  workflow_profile_json TEXT,\n"
            "  editors_json TEXT,\n"
            "  reviewers_json TEXT,\n"
            "  approvers_json TEXT,\n"
            "  reviewed_by_json TEXT,\n"
            "  approved_by_json TEXT,\n"
            "  custom_fields_json TEXT\n"
            ");\n"
            "CREATE TABLE document_artifacts (metadata_json TEXT);\n"
            "CREATE TABLE document_workflow_comments (anchor_json TEXT);\n"
            "CREATE TABLE incidents (labels_json TEXT);\n"
            "CREATE TABLE incident_timeline (details_json TEXT);\n"
            "CREATE TABLE incident_artifacts (metadata_json TEXT);\n"
            "CREATE TABLE training_quiz_attempts (\n"
            "  selected_question_ids_json TEXT,\n"
            "  presented_questions_json TEXT,\n"
            "  answers_json TEXT\n"
            ");\n"
            "CREATE TABLE training_comments (anchor_json TEXT);\n"
            "CREATE TABLE training_audit_log (details_json TEXT);\n"
        ),
    }
    dirty = dict(base)
    dirty["modules/documents/new_policy.json"] = '{"x":1}'
    dirty["modules/training/events.jsonl"] = '{"e":1}\n'
    payload = evaluate_json_persistence_gate(ROOT, mode="scratch", source_files=dirty)
    assert payload["ok"] is False
    kinds_paths = {(f["kind"], f["path"]) for f in payload["findings"]}
    assert ("unregistered_domain_json_file", "modules/documents/new_policy.json") in kinds_paths
    assert ("unregistered_domain_json_file", "modules/training/events.jsonl") in kinds_paths


def test_scratch_rejects_new_relationship_json_column() -> None:
    sql = (
        "CREATE TABLE document_versions (\n"
        "  editors_json TEXT,\n"
        "  assignees_json TEXT\n"
        ");\n"
    )
    payload = evaluate_json_persistence_gate(
        ROOT,
        mode="scratch",
        source_files={"modules/documents/migrations/0001_initial.sql": sql},
    )
    assert payload["ok"] is False
    assert any(
        f["kind"] == "unregistered_json_column" and f["path"] == "document_versions.assignees_json"
        for f in payload["findings"]
    )


def test_scratch_rejects_unversioned_snapshot_and_schema_version_without_allowlist() -> None:
    sql = (
        "CREATE TABLE workflow_instances (\n"
        "  state_snapshot_json TEXT NOT NULL,\n"
        "  state_snapshot_schema_version INTEGER NOT NULL\n"
        ");\n"
    )
    payload = evaluate_json_persistence_gate(
        ROOT,
        mode="scratch",
        source_files={"modules/documents/migrations/0002_add.sql": sql},
    )
    assert payload["ok"] is False
    assert any(
        f["kind"] == "unregistered_json_column"
        and f["path"] == "workflow_instances.state_snapshot_json"
        for f in payload["findings"]
    )


def test_scratch_rejects_snapshot_missing_schema_version_across_alters() -> None:
    files = {
        "modules/documents/migrations/0001_initial.sql": (
            "CREATE TABLE workflow_instances (\n  id TEXT\n);\n"
        ),
        "modules/documents/migrations/0002_add_snapshot.sql": (
            "ALTER TABLE workflow_instances ADD COLUMN state_snapshot_json TEXT;\n"
        ),
    }
    payload = evaluate_json_persistence_gate(ROOT, mode="scratch", source_files=files)
    assert payload["ok"] is False
    assert any(f["kind"] == "unversioned_snapshot_json_column" for f in payload["findings"])


def test_scratch_accepts_snapshot_schema_version_added_in_later_migration_when_allowlisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.json_persistence_gate as gate

    monkeypatch.setattr(
        gate,
        "ALLOWED_JSON_COLUMNS",
        frozenset({"workflow_instances.state_snapshot_json"}),
    )
    files = {
        "modules/documents/migrations/0001_initial.sql": (
            "CREATE TABLE workflow_instances (\n  state_snapshot_json TEXT\n);\n"
        ),
        "modules/documents/migrations/0002_version.sql": (
            "ALTER TABLE workflow_instances ADD COLUMN state_snapshot_schema_version INTEGER;\n"
        ),
    }
    payload = evaluate_json_persistence_gate(ROOT, mode="scratch", source_files=files)
    assert not any(f["kind"] == "unversioned_snapshot_json_column" for f in payload["findings"])


def test_scratch_keeps_anchor_json_and_legacy_profile_snapshot_green() -> None:
    sql = (
        "CREATE TABLE document_workflow_comments (anchor_json TEXT);\n"
        "CREATE TABLE document_versions (workflow_profile_json TEXT);\n"
    )
    payload = evaluate_json_persistence_gate(
        ROOT,
        mode="scratch",
        source_files={
            "modules/documents/migrations/0001_initial.sql": sql,
            "license/license.json": "{}",
            "qm_platform/persistence/migration_manifest.json": "{}",
            "modules/documents/workflow_profiles.json": "{}",
        },
    )
    assert not any(
        f["path"]
        in {
            "document_workflow_comments.anchor_json",
            "document_versions.workflow_profile_json",
        }
        and f["kind"] in {"unregistered_json_column", "unversioned_snapshot_json_column"}
        for f in payload["findings"]
    )


def test_sql_parser_handles_comments_quotes_case_and_multi_columns() -> None:
    tables: dict[str, set[str]] = {}
    sql = """
    -- leading comment
    CREATE TABLE IF NOT EXISTS "MixedCase" (
      /* block */
      "Editors_JSON" TEXT,
      other TEXT DEFAULT 'a,b',
      reviewers_json TEXT
    );
    ALTER TABLE MixedCase ADD COLUMN approvers_json TEXT;
    ALTER TABLE mixedcase ADD "approved_by_json" TEXT;
    """
    apply_sql_to_table_state(sql, tables)
    assert "mixedcase" in tables
    cols = tables["mixedcase"]
    assert "editors_json" in cols
    assert "reviewers_json" in cols
    assert "approvers_json" in cols
    assert "approved_by_json" in cols


def test_sql_parser_handles_postgres_schema_and_add_if_not_exists() -> None:
    tables: dict[str, set[str]] = {}
    apply_sql_to_table_state(
        "CREATE TABLE usermanagement.users (id TEXT, meta_json TEXT);\n",
        tables,
    )
    assert "users" in tables
    assert "usermanagement" not in tables
    assert "meta_json" in tables["users"]

    apply_sql_to_table_state(
        "ALTER TABLE usermanagement.users ADD COLUMN IF NOT EXISTS extra_json TEXT;\n",
        tables,
    )
    assert "extra_json" in tables["users"]


def test_storage_exact_literal_allowed_dynamic_rejected() -> None:
    allowed = evaluate_json_persistence_gate(
        ROOT,
        mode="scratch",
        source_files={
            "qm_platform/settings/residual_store.py": 'path = "storage/platform/settings_residual_archive/settings.json"\n',
        },
    )
    assert not any(
        f["kind"].startswith("unregistered_storage") or f["kind"].startswith("dynamic_storage")
        for f in allowed["findings"]
    )

    cases = [
        'name = "policy"; path = f"storage/platform/{name}.json"\n',
        'from pathlib import Path\nname = "x"; path = Path("storage") / f"{name}.json"\n',
        'from pathlib import Path\nfolder = "platform"; path = Path("storage") / folder / "state.json"\n',
    ]
    for src in cases:
        dynamic = evaluate_json_persistence_gate(
            ROOT,
            mode="scratch",
            source_files={"modules/demo/bad.py": src},
        )
        assert dynamic["ok"] is False, src
        assert any(f["kind"] == "dynamic_storage_json_write" for f in dynamic["findings"]), src


def test_scratch_python_syntax_error_is_gate_error() -> None:
    payload = evaluate_json_persistence_gate(
        ROOT,
        mode="scratch",
        source_files={
            "modules/demo/broken.py": "def broken(\n",
        },
    )
    assert payload["ok"] is False
    assert any(
        f["kind"] == "gate_error"
        and f["path"] == "modules/demo/broken.py"
        and "syntax error" in f["detail"].lower()
        for f in payload["findings"]
    )


def test_scratch_unclosed_sql_block_comment_is_gate_error() -> None:
    payload = evaluate_json_persistence_gate(
        ROOT,
        mode="scratch",
        source_files={
            "modules/documents/migrations/0001_initial.sql": (
                "CREATE TABLE document_headers (id TEXT);\n"
                "/* unclosed comment hides the rest\n"
                "ALTER TABLE document_headers ADD COLUMN secret_json TEXT;\n"
            ),
        },
    )
    assert payload["ok"] is False
    assert any(
        f["kind"] == "gate_error"
        and f["path"] == "modules/documents/migrations/0001_initial.sql"
        and "unclosed SQL block comment" in f["detail"]
        for f in payload["findings"]
    )
    assert not any(
        "secret_json" in f["path"] for f in payload["findings"]
    ), "hidden columns must not be silently accepted or ignored as column findings"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_repo_mode_detects_untracked_and_staged_new_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "j01@example.com")
    _git(repo, "config", "user.name", "J01")
    (repo / "license").mkdir()
    (repo / "license" / "license.json").write_text("{}", encoding="utf-8")
    (repo / "qm_platform" / "persistence").mkdir(parents=True)
    (repo / "qm_platform" / "persistence" / "migration_manifest.json").write_text(
        "{}", encoding="utf-8"
    )
    (repo / "modules" / "documents").mkdir(parents=True)
    (repo / "modules" / "documents" / "workflow_profiles.json").write_text("{}", encoding="utf-8")
    (repo / "modules" / "documents" / "migrations").mkdir(parents=True)
    (repo / "modules" / "documents" / "migrations" / "0001_initial.sql").write_text(
        "CREATE TABLE document_workflow_comments (anchor_json TEXT);\n"
        "CREATE TABLE document_versions (workflow_profile_json TEXT, editors_json TEXT, "
        "reviewers_json TEXT, approvers_json TEXT, reviewed_by_json TEXT, "
        "approved_by_json TEXT, custom_fields_json TEXT);\n"
        "CREATE TABLE document_headers (distribution_roles_json TEXT, "
        "distribution_sites_json TEXT, distribution_departments_json TEXT);\n"
        "CREATE TABLE document_artifacts (metadata_json TEXT);\n"
        "CREATE TABLE incidents (labels_json TEXT);\n"
        "CREATE TABLE incident_timeline (details_json TEXT);\n"
        "CREATE TABLE incident_artifacts (metadata_json TEXT);\n"
        "CREATE TABLE training_quiz_attempts (selected_question_ids_json TEXT, "
        "presented_questions_json TEXT, answers_json TEXT);\n"
        "CREATE TABLE training_comments (anchor_json TEXT);\n"
        "CREATE TABLE training_audit_log (details_json TEXT);\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed")

    # Temporarily shrink allowlist liveness expectations by using scratch-like
    # full seed that matches allowlist files; repo mode will still flag dead
    # columns for missing modules — so monkeypatch allowlists for this mini-repo.
    import scripts.json_persistence_gate as gate

    old_cols = gate.ALLOWED_JSON_COLUMNS
    old_files = gate.ALLOWED_DOMAIN_JSON_FILES
    old_legacy = gate.LEGACY_UNVERSIONED_SNAPSHOT_COLUMNS
    gate.ALLOWED_DOMAIN_JSON_FILES = frozenset(
        {
            "license/license.json",
            "qm_platform/persistence/migration_manifest.json",
            "modules/documents/workflow_profiles.json",
        }
    )
    gate.ALLOWED_JSON_COLUMNS = frozenset(
        {
            "document_workflow_comments.anchor_json",
            "document_versions.workflow_profile_json",
            "document_versions.editors_json",
            "document_versions.reviewers_json",
            "document_versions.approvers_json",
            "document_versions.reviewed_by_json",
            "document_versions.approved_by_json",
            "document_versions.custom_fields_json",
            "document_headers.distribution_roles_json",
            "document_headers.distribution_sites_json",
            "document_headers.distribution_departments_json",
            "document_artifacts.metadata_json",
            "incidents.labels_json",
            "incident_timeline.details_json",
            "incident_artifacts.metadata_json",
            "training_quiz_attempts.selected_question_ids_json",
            "training_quiz_attempts.presented_questions_json",
            "training_quiz_attempts.answers_json",
            "training_comments.anchor_json",
            "training_audit_log.details_json",
        }
    )
    gate.LEGACY_UNVERSIONED_SNAPSHOT_COLUMNS = frozenset(
        {"document_versions.workflow_profile_json"}
    )
    try:
        green = evaluate_json_persistence_gate(repo, mode="repo", base_ref="HEAD")
        assert green["ok"] is True, green

        untracked = repo / "modules" / "documents" / "rogue.json"
        untracked.write_text("{}", encoding="utf-8")
        red_untracked = evaluate_json_persistence_gate(repo, mode="repo", base_ref="HEAD")
        assert red_untracked["ok"] is False
        assert any(
            f["path"] == "modules/documents/rogue.json" for f in red_untracked["findings"]
        )
        untracked.unlink()

        staged_json = repo / "modules" / "documents" / "staged_policy.json"
        staged_json.write_text("{}", encoding="utf-8")
        staged_sql = repo / "modules" / "documents" / "migrations" / "0002_bad.sql"
        staged_sql.write_text(
            "ALTER TABLE document_versions ADD COLUMN pool_json TEXT;\n",
            encoding="utf-8",
        )
        _git(repo, "add", "modules/documents/staged_policy.json", str(staged_sql))
        red_staged = evaluate_json_persistence_gate(repo, mode="repo", base_ref="HEAD")
        assert red_staged["ok"] is False, red_staged
        paths = {f["path"] for f in red_staged["findings"]}
        assert "modules/documents/staged_policy.json" in paths
        assert "document_versions.pool_json" in paths

        # Staged deletion of an allowlisted file must fail closed (no HEAD fallback).
        _git(repo, "rm", "--", "modules/documents/workflow_profiles.json")
        red_delete = evaluate_json_persistence_gate(repo, mode="repo", base_ref="HEAD")
        assert red_delete["ok"] is False, red_delete
        assert any(
            f["kind"] == "staged_allowlist_deletion"
            and f["path"] == "modules/documents/workflow_profiles.json"
            for f in red_delete["findings"]
        )
    finally:
        gate.ALLOWED_JSON_COLUMNS = old_cols
        gate.ALLOWED_DOMAIN_JSON_FILES = old_files
        gate.LEGACY_UNVERSIONED_SNAPSHOT_COLUMNS = old_legacy
