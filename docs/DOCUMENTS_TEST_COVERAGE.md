# Documents Test Coverage Map

This file tracks executable coverage for the `documents` domain using an action-role-status matrix.

## Scope

- Service-layer matrix and variant matrix:
  - `tests/modules/test_documents_authorization_matrix.py`
  - `tests/modules/test_documents_variants_matrix.py`
- Existing service/infrastructure regression tests:
  - `tests/modules/test_documents_service.py`
  - `tests/modules/test_documents_infrastructure.py`
- CLI matrix and end-to-end behavior:
  - `tests/e2e_cli/test_documents_cli_authorization_matrix.py`
  - `tests/e2e_cli/test_documents_cli.py`

## Coverage Snapshot (Machine Readable)

```json
{
  "version": 1,
  "last_verified_full_suite": {
    "result": "pass",
    "tests_passed": 62,
    "warnings": 1
  },
  "actions": [
    {
      "action": "assign_roles",
      "statuses": ["PLANNED", "IN_PROGRESS", "IN_REVIEW", "IN_APPROVAL", "APPROVED"],
      "authorization": {
        "owner_user_before_first_edit_signature": "allow",
        "owner_user_after_first_edit_signature": "deny",
        "qmb": "allow_with_strict_previous_phase_locks",
        "admin": "allow"
      },
      "covered_by": [
        "tests/modules/test_documents_authorization_matrix.py::test_assign_roles_owner_gate_before_after_first_signature",
        "tests/modules/test_documents_authorization_matrix.py::test_qmb_strict_previous_phase_locks_matrix",
        "tests/e2e_cli/test_documents_cli_authorization_matrix.py::test_qmb_phase_lock_matrix_for_assign_roles",
        "tests/e2e_cli/test_documents_cli.py::test_owner_cannot_reassign_roles_after_first_signature"
      ]
    },
    {
      "action": "workflow_start",
      "statuses": ["PLANNED"],
      "authorization": {
        "owner_user": "allow",
        "non_owner_user": "deny",
        "qmb": "allow",
        "admin": "allow"
      },
      "covered_by": [
        "tests/modules/test_documents_authorization_matrix.py::test_start_workflow_owner_systemrole_matrix",
        "tests/modules/test_documents_service.py::test_workflow_start_requires_all_role_sets",
        "tests/e2e_cli/test_documents_cli_authorization_matrix.py::test_workflow_start_matrix"
      ]
    },
    {
      "action": "editing_complete",
      "statuses": ["IN_PROGRESS"],
      "authorization": {
        "assigned_editor_user": "allow",
        "owner_user": "allow",
        "non_participant_user": "deny",
        "qmb": "allow",
        "admin": "allow"
      },
      "covered_by": [
        "tests/modules/test_documents_authorization_matrix.py::test_complete_editing_authorization_matrix",
        "tests/modules/test_documents_service.py::test_signature_required_transition_fails_without_request",
        "tests/e2e_cli/test_documents_cli_authorization_matrix.py::test_editing_complete_matrix"
      ]
    },
    {
      "action": "review_accept",
      "statuses": ["IN_REVIEW"],
      "authorization": {
        "assigned_reviewer": "allow",
        "non_assigned_reviewer": "deny"
      },
      "covered_by": [
        "tests/e2e_cli/test_documents_cli.py::test_non_participant_role_is_blocked_in_review",
        "tests/e2e_cli/test_documents_cli.py::test_workflow_moves_to_approved_with_required_sign_steps"
      ]
    },
    {
      "action": "review_reject",
      "statuses": ["IN_REVIEW"],
      "authorization": {
        "assigned_reviewer": "allow_with_reason_required"
      },
      "covered_by": [
        "tests/modules/test_documents_service.py::test_reject_requires_text_or_template",
        "tests/modules/test_documents_variants_matrix.py::test_reject_paths_return_to_in_progress"
      ]
    },
    {
      "action": "approval_accept",
      "statuses": ["IN_APPROVAL"],
      "authorization": {
        "assigned_approver": "allow",
        "reviewer_same_user_when_four_eyes": "deny",
        "reviewer_same_user_when_four_eyes_disabled": "allow"
      },
      "covered_by": [
        "tests/modules/test_documents_service.py::test_long_release_profile_enforces_four_eyes",
        "tests/modules/test_documents_service.py::test_custom_profile_can_disable_four_eyes",
        "tests/modules/test_documents_variants_matrix.py::test_four_eyes_combination_matrix",
        "tests/e2e_cli/test_documents_cli.py::test_workflow_moves_to_approved_with_required_sign_steps"
      ]
    },
    {
      "action": "approval_reject",
      "statuses": ["IN_APPROVAL"],
      "authorization": {
        "assigned_approver": "allow_with_reason_required"
      },
      "covered_by": [
        "tests/modules/test_documents_variants_matrix.py::test_reject_paths_return_to_in_progress"
      ]
    },
    {
      "action": "workflow_abort",
      "statuses": ["IN_PROGRESS", "IN_REVIEW", "IN_APPROVAL"],
      "authorization": {
        "owner_user": "allow",
        "non_owner_user": "deny",
        "qmb": "allow",
        "admin": "allow"
      },
      "covered_by": [
        "tests/modules/test_documents_authorization_matrix.py::test_abort_workflow_owner_systemrole_matrix",
        "tests/modules/test_documents_variants_matrix.py::test_abort_matrix_across_active_statuses"
      ]
    },
    {
      "action": "archive",
      "statuses": ["APPROVED"],
      "authorization": {
        "qmb": "allow",
        "admin": "allow",
        "user": "deny"
      },
      "covered_by": [
        "tests/modules/test_documents_service.py::test_archive_approved_requires_qmb_or_admin"
      ]
    },
    {
      "action": "annual_extend",
      "statuses": ["APPROVED"],
      "authorization": {
        "signature_required": "true",
        "max_extensions_per_version": 3,
        "recreate_required_after_limit": "true"
      },
      "covered_by": [
        "tests/modules/test_documents_service.py::test_annual_extension_limited_to_three_per_version",
        "tests/modules/test_documents_variants_matrix.py::test_annual_extension_limit_matrix"
      ]
    },
    {
      "action": "pool_list_by_status",
      "statuses": ["ANY"],
      "authorization": {
        "login_required": "true",
        "default_status": "PLANNED"
      },
      "covered_by": [
        "tests/e2e_cli/test_documents_cli.py::test_pool_list_by_status_defaults_to_planned",
        "tests/e2e_cli/test_documents_cli.py::test_documents_commands_require_login",
        "tests/modules/test_documents_service.py::test_pool_query_lists_documents_by_status"
      ]
    },
    {
      "action": "intake_import_pdf_docx_template",
      "statuses": ["PLANNED"],
      "authorization": {
        "owner_qmb_admin_only_mutating": "true",
        "artifact_registry_immutable": "true"
      },
      "covered_by": [
        "tests/modules/test_documents_infrastructure.py::test_intake_creates_immutable_artifact_registry_entries",
        "tests/e2e_cli/test_documents_cli.py::test_intake_commands_register_artifacts"
      ]
    },
    {
      "action": "event_contracts",
      "statuses": ["PLANNED", "IN_PROGRESS", "IN_REVIEW", "IN_APPROVAL", "APPROVED", "ARCHIVED"],
      "authorization": {
        "module_id_is_documents": "true",
        "core_payload_keys": ["document_id", "version"],
        "action_specific_payload_keys_present": "true"
      },
      "covered_by": [
        "tests/modules/test_documents_event_contracts.py::test_intake_events_publish_expected_payload_fields",
        "tests/modules/test_documents_event_contracts.py::test_workflow_events_publish_expected_payload_fields"
      ]
    }
  ]
}
```

## Explicit Non-Goals / Open Coverage Edges

- Full combinatorial explosion for all profile permutations is intentionally avoided in one single test;
  representative profile combinations are covered (`long_release`, custom no-four-eyes).
- CLI currently verifies the high-risk authorization paths and phase locks, not every single negative permutation.

## Critical Invariant Traceability (Architecture Contract)

Source invariants: `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md` (items 4 and 7 are explicitly highlighted here).

- **Invariant 4**: New approval supersedes prior approved version deterministically.
  - covered_by:
    - `tests/modules/test_documents_event_contracts.py::test_registry_projection_stays_consistent_with_documents_status`
    - `tests/modules/test_documents_registry_invariants.py::test_new_approval_supersedes_previous_approved_version`
  - residual risk:
    - large historical datasets with manual backfills require migration-gate SQL verification in release pipeline.

- **Invariant 7**: Archived versions are never active in registry validity.
  - covered_by:
    - `tests/modules/test_documents_event_contracts.py::test_registry_projection_stays_consistent_with_documents_status`
    - `tests/modules/test_documents_service.py::test_archive_approved_requires_qmb_or_admin`
  - residual risk:
    - projection drift under storage incidents must be handled by registry recovery runbook.

- **Registry recovery primitive (deterministic projection replay)**:
  - covered_by:
    - `tests/modules/test_registry_module.py::test_apply_documents_state_deterministic_replay_supports_reconciliation`
    - `tests/modules/test_registry_module.py::test_registry_rebuild_on_empty_db_matches_replayed_projection`
  - meaning:
    - Verifies that `RegistryService.apply_documents_state` is **deterministic for a fixed event envelope** and that a **fresh empty registry DB** can be brought to the same row by replaying the same projection inputs. This is the automated anchor for the operational “rebuild/reconcile” contract in `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`; it does **not** replace a full incident drill with real backups and documents/registry correlation.
  - residual risk:
    - end-to-end recovery (ordering, batch replay from documents truth, backup restore) remains procedure- and evidence-driven until covered by broader integration tests or runbook drills.

## Documented Residual Risks

- Not all profile permutations are executed as exhaustive combinatorial matrix in a single run.
- As additional `workflow_profile_id` values are introduced, rare interaction defects become more likely; mitigations are expanded matrix rows, targeted scenario tests, or explicit release gates before promoting new profiles.
- CLI negative permutations are risk-focused, not mathematically exhaustive.
- Residual risks are accepted only with:
  - green regression suite,
  - migration gate evidence,
  - explicit release owner sign-off.

## How to Keep This File Updated

When adding a workflow rule:

1. Add or update executable tests first.
2. Update the corresponding `actions[]` entry in the JSON block.
3. Keep the `covered_by` list pointing to concrete test functions.
4. If adding a new `workflow_profile_id`, update profile-specific tests so `tests/modules/test_documents_profile_coverage_guard.py` remains green.
