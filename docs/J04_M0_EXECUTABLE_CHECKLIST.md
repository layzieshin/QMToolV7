# J04-M0 Executable Closure Checklist

Living task list for the J04-M0 executable closure plan. Status values: `TODO` | `PASS` | `BLOCKED` | `FAILED`.

## Repository baseline (CP00 input)

| Item | Value |
| --- | --- |
| Branch | `feature/ap-j04-m0` |
| `HEAD` | `125709fedc4c6b719a46cab9c45e4e342e3df241` |
| `origin/main` | `125709fedc4c6b719a46cab9c45e4e342e3df241` |
| Divergence | `0 0` (no local commits ahead/behind) |
| Modified tracked | 94 paths (92 with content diff; 2 stat-only) |
| Untracked (product) | 59 paths under repo root (excl. evidence) |
| Untracked (evidence) | ~3014 paths under `.j04*` (bulk E; ignored after CP00) |

## Checkpoint status

| CP | Title | Status | Commit SHA | Notes |
| --- | --- | --- | --- | --- |
| CP00 | Preserve and classify baseline | PASS | `0a844c2` | 153 A–D paths; 24 smokes green |
| CP01 | Backend ownership, auth, HTTP contracts | PASS | `3f3f7b1` | 77+1 tests green; OpenAPI reproducible; no code fixes |
| CP02 | Client-facing M0 use-case gates | PASS | `c2d6f3d` | 62 focused tests green; no code fixes |
| CP03 | Word COM isolation | PASS | `1993292` | DispatchEx + cleanup + redaction; 24 tests green |
| CP04 | PostgreSQL-16 destructive gate | PASS | `c71c1f1` | 57 static/guard tests green; PG16 LIVE NOT RUN |
| CP05 | Real-process acceptance harness | PASS | _(pending)_ | 10 harness+reference tests; final gate NOT RUN |
| CP06 | Onedir packaging preparation | TODO | — | Depends CP02, CP05 |
| CP07 | Freeze technical acceptance candidate | TODO | — | Depends CP00–CP06 |
| CP08 | Final acceptance gate | TODO | — | Depends CP07 + external preconditions |
| CP09 | Human acceptance | TODO | — | Depends CP08 + explicit human sign-off |

## Classification legend

| Cat | Meaning |
| --- | --- |
| **A** | J04-M0 product code |
| **B** | J04-M0 test code |
| **C** | J04-M0 documentation / contract |
| **D** | Cross-package test fixture (required for J04 tests) |
| **E** | Evidence / cache / basetemp / build output (never stage) |
| **F** | Out of scope |
| **G** | Unclear (blocks CP00 if staged overlap) |

## Modified tracked files (94)

Stat-only (no content diff; refresh index only, **not staged**):

| Path | Cat | Reason |
| --- | --- | --- |
| `interfaces/pyqt/widgets/signature_placement/label_geometry.py` | — | LF/CRLF stat-only (`git diff --quiet` exit 0) |
| `modules/training/wiring.py` | — | LF/CRLF stat-only (`git diff --quiet` exit 0) |

### A — J04-M0 product code (modified)

| Path | Reason |
| --- | --- |
| `interfaces/cli/bootstrap.py` | CLI backend-session bootstrap for M0 |
| `interfaces/cli/commands/documents_commands.py` | Documents CLI scoped to M0 / `legacy_not_in_m0` |
| `interfaces/cli/commands/settings_commands.py` | Settings aligned with backend profile |
| `interfaces/cli/commands/signature_commands.py` | Signature CLI backend transport |
| `interfaces/cli/commands/users_commands.py` | User admin via backend |
| `interfaces/cli/parsers/documents_parsers.py` | Parser updates for reduced M0 scope |
| `interfaces/gui/main.py` | Legacy Tk fail-closed for documents under J04-M0 |
| `interfaces/pyqt/contributions/common.py` | Shared PyQt backend session wiring |
| `interfaces/pyqt/contributions/documents_pool_view.py` | Documents pool HTTP consumer |
| `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py` | Workflow actions fail-closed on `available_actions` |
| `interfaces/pyqt/contributions/documents_workflow/core_mixin.py` | Workflow core HTTP transport |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | Selection soft-degrade |
| `interfaces/pyqt/contributions/documents_workflow_view.py` | Workflow view backend wiring |
| `interfaces/pyqt/contributions/settings_sections/profile_section.py` | Profile manager backend scope |
| `interfaces/pyqt/contributions/settings_sections/signature_settings_section.py` | Signature settings backend |
| `interfaces/pyqt/main.py` | PyQt entry backend profile |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | Signature ops via HTTP |
| `interfaces/pyqt/presenters/documents_workflow_filter_presenter.py` | Filter presenter fail-closed |
| `interfaces/pyqt/presenters/documents_workflow_presenter.py` | Workflow presenter backend reads |
| `interfaces/pyqt/runtime/host.py` | Runtime host backend profile |
| `interfaces/pyqt/sections/action_bar.py` | Action bar server-driven visibility |
| `interfaces/pyqt/sections/detail_drawer.py` | Detail drawer backend state |
| `interfaces/pyqt/sections/filter_bar.py` | Filter bar backend integration |
| `interfaces/pyqt/shell/main_window.py` | Main window session coordinator |
| `interfaces/pyqt/shell/session_coordinator.py` | Session token provider |
| `interfaces/pyqt/widgets/audit_log_helpers.py` | Audit helpers backend scope |
| `interfaces/pyqt/widgets/document_create_wizard.py` | Create wizard capability gate |
| `interfaces/pyqt/widgets/force_password_change_dialog.py` | Auth flow alignment |
| `interfaces/pyqt/widgets/pdf_viewer_dialog.py` | Artifact read via HTTP IDs |
| `interfaces/pyqt/widgets/reject_reason_dialog.py` | Workflow mutation tokens |
| `interfaces/pyqt/widgets/signature_placement/options_mixin.py` | Signature placement |
| `interfaces/pyqt/widgets/signature_placement/placement_dialog.py` | Signature placement |
| `interfaces/pyqt/widgets/signature_preview_panel.py` | Signature preview |
| `interfaces/pyqt/widgets/signature_request_form.py` | Signature request |
| `interfaces/pyqt/widgets/signature_sign_wizard.py` | Sign wizard backend |
| `interfaces/pyqt/widgets/validity_extension_dialog.py` | Lifecycle extend_validity |
| `interfaces/pyqt/widgets/workflow_profile_wizard.py` | Profile create HTTP |
| `modules/documents/api.py` | Public documents API extensions |
| `modules/documents/comment_permissions.py` | Comment authorization |
| `modules/documents/comment_service.py` | Comment service |
| `modules/documents/comment_sync_service.py` | Comment sync |
| `modules/documents/contracts.py` | Documents contracts |
| `modules/documents/docx_to_pdf.py` | DOCX→PDF (Word COM owner) |
| `modules/documents/errors.py` | Structured errors / redaction |
| `modules/documents/eventing.py` | Domain events |
| `modules/documents/module.py` | Module registration |
| `modules/documents/repository.py` | Repository layer |
| `modules/documents/service.py` | Documents service / policy-on-lock |
| `modules/documents/sqlite_repository.py` | Backend-owned SQLite |
| `modules/documents/storage.py` | Artifact storage |
| `modules/documents/validation.py` | Validation |
| `modules/documents/wiring.py` | `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` |
| `modules/documents/workflow_use_cases.py` | Workflow use cases |
| `modules/signature/api.py` | Signature public API |
| `modules/signature/module.py` | Signature module |
| `modules/signature/service.py` | Signature service |
| `modules/signature/signature_policy_ops.py` | Policy operations |
| `modules/signature/template_use_cases.py` | Template use cases |
| `modules/signature/wiring.py` | Signature wiring |
| `modules/training/released_document_catalog_reader.py` | Training read-only documents |
| `modules/usermanagement/api.py` | Usermanagement API for backend auth |
| `qm_platform/runtime/backend_bootstrap.py` | Backend composition root |
| `qm_platform/runtime/bootstrap.py` | Client/runtime bootstrap |
| `qm_platform/runtime/lifecycle.py` | Lifecycle / backend profile |
| `src/backend/api.py` | Backend public surface |
| `src/backend/bootstrap.py` | Backend startup |
| `src/backend/user_admin_routes.py` | User admin HTTP routes |

### B — J04-M0 test code (modified)

| Path | Reason |
| --- | --- |
| `tests/backend/test_auth_api_postgres_live.py` | PG live auth (marker `postgres`) |
| `tests/backend/test_m6_postgres_live.py` | PG live M6 |
| `tests/e2e_cli/test_database_commands.py` | CLI e2e adjustments |
| `tests/e2e_cli/test_documents_cli.py` | Documents CLI M0 scope |
| `tests/e2e_cli/test_documents_cli_authorization_matrix.py` | CLI auth matrix |
| `tests/e2e_cli/test_training_cli.py` | Training CLI scope |
| `tests/interfaces/test_architecture_gates.py` | Architecture gates |
| `tests/interfaces/test_documents_workflow_presenter_filters.py` | Presenter filters |
| `tests/interfaces/test_documents_workflow_profile_cli.py` | Profile CLI contract |
| `tests/interfaces/test_ui_mvp_smoke.py` | UI smoke |
| `tests/modules/test_documents_authorization_matrix.py` | 16-action matrix |
| `tests/modules/test_documents_infrastructure.py` | Infrastructure |
| `tests/modules/test_documents_module_ports.py` | Module ports / wiring |
| `tests/modules/test_documents_registry_invariants.py` | Registry invariants |
| `tests/modules/test_training_module_ports.py` | Training ports |
| `tests/modules/usermanagement/test_m7_audit_evidence_live.py` | M7 PG live |
| `tests/modules/usermanagement/test_m8_cutover_prep.py` | M8 cutover prep |
| `tests/modules/usermanagement/test_postgres_repositories_live.py` | PG repos live |
| `tests/modules/usermanagement/test_postgres_schema_live.py` | PG schema live |
| `tests/platform/test_core_database_migrations.py` | Platform migrations |
| `tests/platform/test_documents_bootstrap_provenance.py` | Bootstrap provenance |

### C — J04-M0 documentation / contract (modified)

| Path | Reason |
| --- | --- |
| `docs/MASTER_ORCHESTRATION_ROADMAP.md` | J04-M0 roadmap status |
| `docs/QMToolV7_Dokumentenlenkung_Artefaktpaket_v2/JSON_TO_DATABASE_MIGRATION_PLAN.md` | Migration plan J04 context |

### D — Cross-package test fixtures (modified)

| Path | Reason |
| --- | --- |
| `tests/conftest.py` | Shared pytest fixtures for backend HTTP / session tests across layers |
| `tests/modules/incident_management_test_support.py` | Incident fixtures reused by documents authorization tests |

## Untracked product files (59) — all staged as A/B/C/D

### A — product (untracked)

| Path |
| --- |
| `interfaces/clients/auth_messages.py` |
| `interfaces/clients/backend_identity.py` |
| `interfaces/clients/backend_session.py` |
| `interfaces/clients/documents_http.py` |
| `interfaces/clients/documents_http_ports.py` |
| `interfaces/clients/http_transport.py` |
| `interfaces/clients/signature_http.py` |
| `interfaces/clients/signature_http_ports.py` |
| `modules/documents/actor_context.py` |
| `modules/documents/capabilities.py` |
| `modules/documents/sign_intent_builder.py` |
| `modules/documents/state_transport.py` |
| `modules/documents/workflow_policy.py` |
| `modules/signature/transport_dto.py` |
| `qm_platform/runtime/client_runtime_profile.py` |
| `scripts/export_openapi.py` |
| `src/backend/documents_routes.py` |
| `src/backend/signature_routes.py` |

### B — tests (untracked)

| Path |
| --- |
| `tests/backend/test_documents_artifacts_http.py` |
| `tests/backend/test_documents_authorization_http.py` |
| `tests/backend/test_documents_concurrency_http.py` |
| `tests/backend/test_documents_http_api.py` |
| `tests/backend/test_documents_p4_p9_http.py` |
| `tests/backend/test_documents_reads_http.py` |
| `tests/backend/test_documents_signed_transitions_http.py` |
| `tests/backend/test_documents_training_read_http.py` |
| `tests/backend/test_openapi_contract.py` |
| `tests/backend/test_signature_authorization_http.py` |
| `tests/backend/test_signature_http_api.py` |
| `tests/backend/test_user_directory_api.py` |
| `tests/interfaces/test_action_bar_visibility.py` |
| `tests/interfaces/test_auth_messages.py` |
| `tests/interfaces/test_backend_identity.py` |
| `tests/interfaces/test_backend_identity_hotspots.py` |
| `tests/interfaces/test_backend_session_client.py` |
| `tests/interfaces/test_documents_http_client_fail_closed.py` |
| `tests/interfaces/test_documents_http_gates.py` |
| `tests/interfaces/test_documents_http_reads.py` |
| `tests/interfaces/test_documents_http_workflow_port_stubs.py` |
| `tests/interfaces/test_documents_workflow_profile_manager_gate.py` |
| `tests/interfaces/test_documents_workflow_selection_soft_degrade.py` |
| `tests/interfaces/test_gui_documents_fail_closed.py` |
| `tests/interfaces/test_home_fail_closed_documents.py` |
| `tests/interfaces/test_m2r_control_action_gates.py` |
| `tests/interfaces/test_m2r_header_comment_cas_consumers.py` |
| `tests/interfaces/test_m3_prelive_token_controls.py` |
| `tests/interfaces/test_pyqt_backend_profile_scope.py` |
| `tests/interfaces/test_pyqt_session_coordinator.py` |
| `tests/postgres/compose.yaml` |
| `tests/postgres/init/001_test_cluster_marker.sql` |
| `tests/postgres/manage.ps1` |
| `tests/postgres/README.md` |
| `tests/postgres_destructive_guard.py` |
| `tests/postgres_live_support.py` |
| `tests/test_postgres_destructive_guard.py` |

### C — documentation / contract (untracked)

| Path |
| --- |
| `docs/J04_M0_ACCEPTANCE_REPORT.md` |
| `docs/J04_M0_ALLOWED_ACTIONS_ANALYSIS.md` |
| `docs/J04_M0_PATH_MATRIX.md` |
| `docs/J04_M0_EXECUTABLE_CHECKLIST.md` |
| `docs/contracts/j04-m0-openapi.json` |

## E — Evidence / cache (never stage)

Bulk patterns (all contents under these roots):

| Pattern | Count (approx.) | Reason |
| --- | --- | --- |
| `.j04_final_focused_basetemp/**` | 9 | Pytest basetemp from prior focused runs |
| `.j04_g3_evidence/**` | ~120+ | G3 milestone raw logs and basetemps |
| `.j04_g_modules2_basetemp/**` | ~800+ | Module test basetemps |
| `.j04_m0_evidence/**` | varies | M0 verification logs |
| `.j04_m1r_evidence/**` | varies | M1R verification logs |
| `.j04_m2_evidence/**` | varies | M2 verification logs |
| `.j04_m2r_evidence/**` | varies | M2R verification logs |
| Other `.j04*` dirs | varies | Historical/local evidence |

Also excluded: `.env`, `*.db`, `*.sqlite`, `build/j04-m0-closure/` (runtime output), `.venv/`.

Historical evidence in prior reports is **not** current CP00 evidence.

## F / G — none identified

No path classified **F** (out of scope) or **G** (unclear). All modified/untracked product paths map to A–D.

## CP00 acceptance criteria

- [x] Every modified/untracked path classified A–G with rationale
- [x] No E/F/G path staged
- [x] No secrets, `.env`, DBs, or raw logs staged
- [x] Stat-only files confirmed (`label_geometry.py`, `wiring.py`)
- [x] Focused architecture/contract smokes green (24 passed)
- [x] Checklist and acceptance report updated
- [x] Staged file list contains only confirmed J04-M0 baseline (A–D)

## CP00 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/platform/test_documents_bootstrap_provenance.py `
  tests/modules/test_documents_module_ports.py `
  tests/interfaces/test_documents_http_gates.py `
  tests/backend/test_openapi_contract.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp00
```

Result: **24 passed** (2026-08-17, `build/j04-m0-closure/cp00`)

## CP02 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/backend/test_documents_artifacts_http.py `
  tests/backend/test_signature_http_api.py `
  tests/backend/test_signature_authorization_http.py `
  tests/backend/test_documents_training_read_http.py `
  tests/backend/test_documents_p4_p9_http.py `
  tests/interfaces/test_documents_http_reads.py `
  tests/interfaces/test_documents_workflow_profile_manager_gate.py `
  tests/interfaces/test_action_bar_visibility.py `
  tests/interfaces/test_m2r_control_action_gates.py `
  tests/interfaces/test_m2r_header_comment_cas_consumers.py `
  tests/interfaces/test_pyqt_backend_profile_scope.py `
  tests/modules/test_documents_authorization_matrix.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp02
```

Result: **62 passed** (2026-08-17, `build/j04-m0-closure/cp02`)

## CP02 acceptance criteria

- [x] All M0 vertical slices use existing HTTP/public-API paths
- [x] PyQt actions remain server-driven and fail-closed
- [x] Training has no documents workflow/artifact logic ownership
- [x] Profile manager has no local mutation path
- [x] Out-of-scope findings documented as follow-ups (historical report sections)
- [x] Documentation and tests align (62/62 green; no fixes required)

## CP03 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/modules/test_docx_to_pdf.py `
  tests/interfaces/test_docx_conversion_worker.py `
  tests/backend/test_documents_p4_p9_http.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp03
```

Result: **24 passed** (2026-08-17, `build/j04-m0-closure/cp03`)

## CP03 acceptance criteria

- [x] Production code uses isolated own Word instance (`DispatchEx`)
- [x] Cleanup affects only self-created COM objects
- [x] Success and error paths covered by mock-based tests
- [x] Error output redacted (paths, COM repr)
- [x] No real Word E2E in this checkpoint
- [x] No changes to running Word sessions (mock-only)

## CP04 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/test_postgres_destructive_guard.py `
  tests/modules/usermanagement/test_postgres_schema_static.py `
  tests/modules/usermanagement/test_postgres_migration_gate.py `
  tests/modules/usermanagement/test_m7_audit_evidence_static.py `
  tests/modules/usermanagement/test_m8_cutover_prep.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp04
```

Result: **57 passed** (2026-08-17, `build/j04-m0-closure/cp04`)

## CP04 acceptance criteria

- [x] Every destructive path centrally guarded (`require_approved_admin_dsn`)
- [x] Runtime/lab DSNs cannot pass the guard (unit-tested)
- [x] No secrets in staged config/docs
- [x] CI service is ephemeral and marker-bound
- [x] `pg_dump`/`pg_restore` remain M8-only (static prep tests pass)
- [x] **PG16 LIVE NOT RUN** locally
- [x] Config/docs only in CP04 commit (no product code)

## CP05 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/backend/test_documents_http_api.py `
  -k "two_clients_and_restart_readback or version_read_after_restart or harness" `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp05
```

Result: **10 passed** (2026-08-17, `build/j04-m0-closure/cp05`)

## CP05 acceptance criteria

- [x] Harness uses real separate processes (client workers; backend launch verified via mock + canonical `-m src.backend`)
- [x] Separate `QMTOOL_HOME` paths for backend and two clients
- [x] Cleanup terminates only tracked PIDs
- [x] Logs redacted before write under `build/j04-m0-closure/`
- [x] Final test requires marker + explicit opt-in (excluded in CP05 run)
- [x] Full realprocess test **NOT RUN** in CP05
- [x] No new product entrypoint/port/API
