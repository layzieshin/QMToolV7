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
| CP04 | PostgreSQL destructive gate (static/CI) | PASS | `c71c1f1` | 57 static/guard tests; CI ephemer PG16 |
| CP04-R | PG test infra remediation (Slot-2 / major pin) | PASS | `8c273de` | 28 guard/runner tests; PG18 local smoke; **nicht neu implementieren** |
| CP05 | Real-process acceptance harness | PASS | `29ddaa6` | 10 harness+reference tests; final gate NOT RUN |
| CP06 | Onedir packaging preparation | PASS | `ba67126` | 16 packaging tests green; Packaging NOT RUN |
| CP07 | Freeze technical acceptance candidate | PASS | `d19e8b9` | superseded by remediation `8c273de` for `$CandidateSha` |
| CP08 | Final acceptance gate | FAILED | — | PG live **51 passed**; regression **1 failed**; Word **BLOCKED** |
| CP08-R1 | Literal optional documents port in wiring | PASS | `fbea360` | Architecture gate green; constant still exported; **no freeze** |
| CP08-R2 | Realprocess scenario (replace skip stub) | PASS | `30b73e9` | Scenario implemented; live gate **NOT RUN** |
| Word readiness | Word COM `DispatchEx` probe (interactive) | PASS (WR05) | — | Safe mode title confirmed; interactive DispatchEx/Version/Quit PASS; add-ins not causal; DOCX/PDF E2E **NOT RUN** |
| CP08-R3 | Isolate realprocess workspace from pytest basetemp | PASS | `c3d6587` | Test-only; included in FR09 freeze |
| FR09 | Freeze R1+R2+R3 acceptance candidate | PASS | `1a22d38` | 50 focused gates; `$CandidateSha` below; CP08-V3 failed |
| CP08-V3 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at start contract (`pg_bootstrap` / RESET); Word **NOT REACHED** |
| CP08-R4 | Acceptance start contract via PG runner | PASS | `5233b5d` | Runner `--j04-final-acceptance`; guard unchanged; included in FR10 freeze |
| FR10 | Freeze R1–R4 acceptance candidate | PASS | `1bd8aa0` | 83 focused gates; `$CandidateSha` below; CP08-V4 failed |
| CP08-V4 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at `bootstrap_admin_login` (`/auth/me` 409); Word **NOT REACHED** |
| CP08-R5 | Bootstrap-admin `/auth/me` handshake | PASS | `34f39c0` | Harness-only password-change handshake; product auth unchanged; included in FR11 freeze |
| FR11 | Freeze R1–R5 acceptance candidate | PASS | `c263ff5` | 93 focused gates; `$CandidateSha` below; CP08-V5 failed |
| CP08-V5 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at `document_baseline_flow`; bootstrap handshake **PASS**; Word **NOT REACHED** |
| CP08-R6 | Document-create 403 (QMB actor + diagnostics) | PASS | `e28a44d` | Harness-only; Create/Race/Comments/Word-Token use seeded QMB; `require_version_success`; included in FR12 freeze |
| FR12 | Freeze R1–R6 acceptance candidate | PASS | `b63d9a1` | 108 focused gates; `$CandidateSha` below; CP08-V6 failed |
| CP08-V6 | Final acceptance attempt | FAILED | — | PG live **51 passed**; realprocess **FAILED** at `etag_concurrency_race` (`TypeError`); document create **PASS**; Word **NOT REACHED** |
| CP08-R7 | ETag-race harness `sorted()` + stable assignment | PASS | `f5dcfa8` | Test-only; `sorted([a, b])`; both race bodies keep editor/reviewer/approver; next: new freeze, then one CP08 |
| CP09 | Human acceptance | TODO | — | Depends green CP08 + explicit human sign-off |

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

## CP06 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/packaging/test_bundle_excludes_secrets.py `
  tests/packaging/test_j04_m0_onedir_contract.py `
  tests/interfaces/test_backend_session_client.py `
  tests/interfaces/test_pyqt_backend_profile_scope.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp06
```

Result: **16 passed** (2026-08-17, `build/j04-m0-closure/cp06`)

## CP06 acceptance criteria

- [x] Existing onedir owner covers J04-M0 runtime imports (hidden-import list extended)
- [x] Bundle verifier rejects secrets, local DBs, `.env`, evidence artifacts
- [x] `QMTOOL_BACKEND_URL` remains runtime configuration (contract test)
- [x] No parallel/onefile build path introduced
- [x] **Packaging NOT RUN** documented
- [x] Static contract test added (gap not fully covered by prior tests)
- [x] No new product entrypoint/port/API

## CP07 verification command

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/docs/test_document_control_artifact_package.py `
  tests/backend/test_openapi_contract.py::test_openapi_snapshot_is_reproducible `
  tests/test_postgres_destructive_guard.py `
  tests/interfaces/test_architecture_gates.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp07
$Py -m pytest tests/packaging/test_j04_m0_onedir_contract.py -q `
  --basetemp build/j04-m0-closure/cp07-packaging
```

Result: **60 passed** + **5 passed** (2026-08-17)

## CP07 acceptance criteria

- [x] CP00–CP06 committed and documented
- [x] No unresolved F/G files overlapping the candidate
- [x] Historical evidence is not presented as the current pass
- [x] Remaining live/packaging/human gates documented as **NOT RUN**
- [x] Worktree clean except the two known stat-only files
- [x] `$CandidateSha` recorded: `8c273de4e33837dbca44464172db1033de476399` (`8c273de`) — remediation after CP07 freeze

## CP04-R verification (adopted — other agent, do not re-implement)

Verified 2026-08-17 on `feature/ap-j04-m0` @ `8c273de`:

| Item | Value |
| --- | --- |
| Slot 1 (Lab, unchanged) | `192.168.0.4:5432` / `qmtool_test` |
| Slot 2 (destructive) | `127.0.0.1:5432` / PostgreSQL **18.4** |
| Test DB | `qmtool_j04_destructive_test` |
| Admin | `qmtool_j04_test_admin` |
| Marker | `j04_m0_destructive_pg16` (unchanged string) |
| `QMTOOL_PG_TEST_EXPECTED_MAJOR` | local **18**, CI **16**, default **16** |
| Floor | PostgreSQL **>= 16** |
| RESET | not persisted; injected only in pytest child via runner |

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest tests/test_postgres_destructive_guard.py tests/test_run_postgres_live_tests.py -q `
  --basetemp build/j04-m0-closure/cp04r-verify
```

Result: **28 passed** (closure verification 2026-08-17)

Commit: `8c273de` — `test(j04-m0): pin destructive PG major via env for local PG18 smoke`

## CP08 preconditions (next open checkpoint)

- [x] Product `$CandidateSha` = `8c273de` (doc follow-up `94fb480` only)
- [x] Worktree clean except known stat-only files
- [x] Slot-2 PG18 preflight: major=18, marker valid, port 5432
- [x] Port 8000 free
- [ ] Word available (COM isolation already in product)
- [ ] Explicit opt-in before `j04_final_acceptance` full run
- [ ] Human gate remains separate (CP09)

## CP08 execution order (FAILED — candidate NOT_READY)

Per gate rules: **no product/test fixes during CP08**. One regression failure aborts the gate.

| Step | Gate | Status | Evidence |
| --- | --- | --- | --- |
| 1 | PostgreSQL live (`run_postgres_live_tests.py`, PG18 / `EXPECTED_MAJOR=18`) | **PASS** | **51 passed**; preflight major=18; `build/j04-m0-closure/cp08-pg-live-runner-clean.log` |
| 2 | Full `j04_final_acceptance` real-process E2E | **NOT RUN** | Opt-in not set; harness scenario still `pytest.skip` stub |
| 3 | Word COM live E2E | **BLOCKED** | `CO_E_SERVER_EXEC_FAILURE` — Word cannot start in this session |
| 4 | Onedir build + bundle verify | **NOT RUN** | Blocked by gate abort after step 5 failure |
| 5 | Full non-destructive regression | **FAILED** | `test_module_wiring_hard_get_ports_are_declared_as_required_ports` — `modules/documents/wiring.py` non-literal `get_port` |
| 6 | `scripts/golive_gate.py` | **NOT RUN** | — |
| 7 | Human acceptance prep | **NOT RUN** | CP09 |

### CP08 regression failure (blocks gate)

```
FAILED tests/modules/test_module_contract_wiring.py::test_module_wiring_hard_get_ports_are_declared_as_required_ports
AssertionError: modules\documents\wiring.py uses non-literal get_port
```

Cause: `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` constant passed to `container.get_port()` in
`modules/documents/wiring.py` (J04 baseline product code). Requires a **post-gate remediation
checkpoint** — not an in-gate fix.

Log: `build/j04-m0-closure/cp08-regression.log`

## CP08-R1 verification (wiring literal port)

Minimal product fix only. `DOCUMENTS_ALLOW_INPROCESS_SQLITE_PORT` remains exported for
tests/composition roots. Architecture test unchanged. **No freeze.**

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/modules/test_module_contract_wiring.py `
  tests/modules/test_documents_module_ports.py `
  tests/interfaces/test_documents_http_gates.py `
  tests/platform/test_documents_bootstrap_provenance.py `
  -m "not postgres" -q `
  --basetemp build/j04-m0-closure/cp08-r1
```

Result: **16 passed** (2026-08-17)

Remaining after R1:

1. CP08-R2 — implement full real-process scenario (remove `pytest.skip` stub) — **PASS (implementation only)**
2. Word COM readiness in an interactive session — **WR03 DispatchEx PASS** (see WR03 below); freeze not started this turn
3. New technical freeze — **next** (R1+R2 including docs HEAD) after this report is accepted
4. Second full CP08 attempt — **blocked until freeze**

## Word COM readiness probe (2026-08-17)

Minimal probe only — **no DOCX/PDF E2E**, no termination of pre-existing Word sessions.

| Item | Result |
| --- | --- |
| Method | `win32com.client.DispatchEx("Word.Application")` + `pythoncom.CoInitialize()` (matches product CP03) |
| Controlled quit | Attempted on owned instance only (`word.Quit()` in `finally`) |
| Pre-existing WINWORD | PIDs **15936**, **23944** — **not terminated** |
| Post-probe WINWORD | **15936**, **23944** still present; transient PID **22184** appeared during failed start |
| HRESULT | **0x80080005** (`CO_E_SERVER_EXEC_FAILURE`) |
| Status | **BLOCKED** — Word cannot be started from this agent shell session |
| Evidence | `build/j04-m0-closure/word-com-readiness/probe-result.json` (local, not committed) |

Classification: interactive Windows/COM environment failure, **not** a new product deviation.
`e8a015c` is documentation only. Overall closure status: **`NOT_READY`**.

Re-probe **must** run in a normal interactive desktop PowerShell (not the agent shell).
On **PASS** only, in this order:

1. Document readiness in checklist and report
2. Freeze R1+R2 including documentation HEAD
3. Record the new `$CandidateSha`
4. Start exactly one second CP08 run against that SHA

Until then: no freeze, no second CP08.

## WR03 — Safe mode + add-in isolation (2026-08-17)

WR02 leftover PID was already gone. No pre-existing WINWORD at WR03 start. **No DOCX/PDF E2E.**

### Safe mode

| Item | Result |
| --- | --- |
| Command | `C:\Program Files\Microsoft Office\Root\Office16\WINWORD.EXE /safe` |
| PID | **21364** (started by this probe; later stopped) |
| Title | **`Microsoft Word (Abgesicherter Modus)`** |
| Responding | True |
| Status | **PASS** |

### Add-in inventory and isolation order

Autoload (`LoadBehavior=3`) third-party first, then HKCU demand-load copies:

1. Acrobat PDFMaker (HKLM + WOW6432Node `LoadBehavior=3`; HKCU `2`)
2. Citavi Word Add-In 6.17 (WOW6432Node `LoadBehavior=3`; HKCU `2`)
3. OneNote (HKCU `8` / `0`) — not changed

| Action | Result |
| --- | --- |
| HKLM `LoadBehavior` 3→0 (Acrobat, Citavi) | **BLOCKED** — registry access denied (no elevation) |
| HKCU Acrobat + Citavi `LoadBehavior`→0, then `DispatchEx` | **PASS** Word 16.0 |
| A: Acrobat=0, Citavi=2 | **PASS** |
| B: Acrobat=2, Citavi=0 | **PASS** |
| C: both restored HKCU=2 | **PASS** |
| HKCU restored to snapshot | Acrobat=2, Citavi=2 |

**Add-in effect:** not causal in this session. `DispatchEx` succeeded with original HKCU values after a clean safe-mode quit and empty WINWORD list. HKLM autoload entries remain `3`.

Evidence (local, not committed): `build/j04-m0-closure/word-com-readiness/wr03-result.json`

Freeze and second CP08 were **not** started in WR03.


## WR05 — Interactive Word COM readiness (PASS)

WR03 recovery was followed by a successful `DispatchEx('Word.Application')` probe in the normal
interactive desktop session 1. Office version `16.0.17932.20884` was readable, the owned
instance was quit, and the original HKCU add-in values were restored. No DOCX/PDF E2E was run.

Readiness is **PASS** for the COM boundary only. The prior agent-context `0x80080005` attempt is
historical evidence; it does not change the successful interactive result. FR08 must now freeze
R1, R2, and the documentation before CP08-V2.

## FR08 — Remediated acceptance candidate freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), WR05 documentation (`034425f`), and the
current technical tree. The focused gates are **46 passed**. The frozen candidate is
`fe172c9fc3b5753b9b6d4b9b1a1d026760257c37` (`fe172c9`). No product or test changes are allowed
after this freeze. CP08-V2 remains **NOT STARTED**.

## CP08-V2 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `fe172c9fc3b5753b9b6d4b9b1a1d026760257c37`.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 guard preflight; **51 passed** |
| Full real-process E2E | **FAILED/ABORTED** — `WinError 5` prevented pytest basetemp use and cleanup |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** — first mandatory step after PG stopped the gate |

No repair was performed during CP08-V2. Status remains **`NOT_READY`**; no retry is allowed
without a bounded remediation checkpoint and a new technical freeze.

## CP08-R3 — Basetemp / workspace isolation (test-only)

Observed CP08-V2 abort: **`WinError 5`** on pytest basetemp use and cleanup. Child-process file
locks under `tmp_path` remain a **plausible** cause, not a proven one. R3 decouples the
long-lived workspace from pytest `tmp_path` without claiming a root-cause proof.

Workspace helper in `tests/acceptance/j04_m0_realprocess_harness.py`:

```text
build/j04-m0-closure/cp08-realprocess-ws/<UTC-timestamp>-<uuid>/
```

Path is `resolve()`-enforced under `repo_root()/build/j04-m0-closure/`. Existing paths are never
reused or deleted. Full-gate test no longer takes `tmp_path`. `pytest.ini` default basetemp
unchanged.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r3-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **18 passed** (`build/j04-m0-closure/cp08-r3-20260817T125918964Z`). No `PermissionError` /
WinError 5 on start or cleanup.

Fail-closed: **1 skipped**, exit 0 (`cp08-r3-skip-20260817T125934013Z`).

**No freeze. No CP08-V3.** R3 PASS is not Freeze, CP08-V3, or ACCEPTED.

CP08-R3 commit: `c3d6587` — `test(j04-m0): isolate realprocess workspace from pytest basetemp`

## FR09 — R1+R2+R3 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), WR05 documentation
(`034425f`), and the freeze documentation. Focused gates are **50 passed**
(`build/j04-m0-closure/freeze-r3-20260817T171311893Z`): R1 16, R3 harness/scenario 18,
Word isolation 16 (`test_docx_to_pdf.py` + `test_docx_conversion_worker.py`). FR08 reported
46 on the pre-R3 set. The frozen candidate is
`1a22d3809683d16ad9354d609f6ce2d2af7c053a` (`1a22d38`). No product or test changes are
allowed after this freeze. CP08-V3 was executed once against this candidate and **FAILED**.
Overall status remains **`NOT_READY`**. `ACCEPTED` is not set.

## CP08-V3 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `1a22d3809683d16ad9354d609f6ce2d2af7c053a`.
Lauf-SHA at gate start: `57d87d46012ea2ed12c95fc7c1bca54bd200595b` (FR09 SHA-record docs only;
`git diff 1a22d38..57d87d4` is the two documentation files). Gate policy: no repair and no
retry after the first red mandatory step.

The documented start command was **direct pytest**. That is inconsistent with the PostgreSQL
safety model: the PG runner injects `QMTOOL_PG_TEST_RESET` only into its pytest child after
read-only preflight. A separately started pytest process does not receive that injection.
`prepare_live_environment()` requires RESET because it is destructive; the guard is correct
and must not be weakened or bypassed with a global/automatic RESET.

Stop point: `pg_bootstrap`. Backend start and Word COM were **not reached**. CP08-V3 has
**no Word-COM result**. Historical Word-readiness issues are not the cause of this run.
Status is **`NOT_READY` because of the acceptance start contract**.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 guard preflight; **51 passed**; `build/j04-m0-closure/cp08-v3-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at start contract / `pg_bootstrap` (RESET unset in the separate pytest process) |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** — Word not reached |

No repair was performed during CP08-V3. `ACCEPTED` is not set.

## CP08-R4 — Acceptance start contract (PG runner)

Test-only. Extends the existing runner; does not change the destructive guard.

The full realprocess gate must be started as:

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$env:QMTOOL_PG_TEST_EXPECTED_MAJOR = "18"
$env:QMTOOL_J04_FINAL_ACCEPTANCE = "I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN"
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-pytest-$stamp"
$Py scripts/run_postgres_live_tests.py `
  --j04-final-acceptance `
  --basetemp $Base
```

RESET remains child-only after preflight. The runner does not set Word COM live.
Loose `pytest tests/acceptance/test_j04_m0_realprocess.py` is rejected by the runner
(exit 4) so the unsupported start path cannot be mixed into default live targets.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r4-$stamp"
$Py -m pytest `
  tests/test_run_postgres_live_tests.py `
  tests/test_postgres_destructive_guard.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **51 passed** (`build/j04-m0-closure/cp08-r4-20260817T182342311Z`).

**No freeze. No CP08 retry.** Overall **`NOT_READY`** at R4 close: start contract remediating;
Word not in scope for that checkpoint.

CP08-R4 commit: `5233b5d` — `test(j04-m0): route realprocess gate through PG live runner`

## FR10 — R1–R4 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), WR05 documentation (`034425f`), and the freeze documentation. Focused gates are
**83 passed** (`build/j04-m0-closure/freeze-r4-20260817T182715064Z`): FR09 set plus R4 runner
and destructive-guard tests. The frozen candidate is
`1bd8aa0f026249cd8e635d4a3c3ad34857ea953e` (`1bd8aa0`). No product or test changes are
allowed after this freeze. CP08-V4 was executed once and **FAILED** at
`bootstrap_admin_login`. Word COM was **not reached**. Overall **`NOT_READY`**: after the
start-contract remediation there is not yet a successful CP08 run. Historical CP08-V3 aborted
on the acceptance start contract, not Word COM. `ACCEPTED` is not set.

## CP08-V4 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `1bd8aa0f026249cd8e635d4a3c3ad34857ea953e`.
Lauf-SHA: `fd3aeb8`. Realprocess via `--j04-final-acceptance`. No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v4-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `bootstrap_admin_login` — `POST /auth/login` 200, `GET /auth/me` **409**. Start contract (`pg_bootstrap`) **PASS**. Word **not reached**. Workspace `20260817T183206770668Z-3da54ae0ec944243aeab4f6f96c132a3` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

## CP08-R5 — Bootstrap-admin `/auth/me` handshake (test-only)

CP08-V4 stopped at `bootstrap_admin_login` after `POST /auth/login` **200** and `GET /auth/me` **409**.
The V4 fail log did not capture the 409 body. Investigation (read-only, then harness-only fix):

| # | Check | Finding |
| --- | --- | --- |
| 1 | 409 body / backend log | Uvicorn: login 200 then `/auth/me` 409. Product mapping: `PasswordChangeRequiredError` → `{"detail":{"error":"password_change_required","message":"password change required"}}`. Other 409s (`user_exists`, `last_active_admin`) are not typical of `GET /auth/me`. |
| 2 | Authorization header | `AcceptanceHttpClient.request_raw(..., auth=True)` sends `Authorization: Bearer {token}` after login. A missing token would be **401**, not 409. |
| 3 | Owner | `GET /auth/me` → `require_user_context_normal` (`password_change_allowed=False`) → `um_api.resolve_session` → `session_ops.py` raises if `user.must_change_password`. Transport has no domain logic. |
| 4 | Session / bootstrap admin | Login persisted a session (otherwise 401). `bootstrap_first_admin` sets `must_change_password=True`. **Not weakened.** |
| 5 | Coverage gap | `tests/backend/test_auth_api.py` and postgres-live auth tests **expect** login 200 → `/auth/me` 409 → change-password 204 → `/auth/me` 200. Realprocess expected `/auth/me` 200 immediately. Gap is the scenario handshake, not product auth. |
| 6 | Smallest test | Mock HTTP reproducing that handshake (`complete_bootstrap_admin_session`). A full OS-process backend test is CP08 itself. |

Decision: **harness/testdata, not product.** No Word, packaging, PG-guard, or RESET change.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r5-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  tests/backend/test_auth_api.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **28 passed** (`build/j04-m0-closure/cp08-r5-20260817T195540932Z`). Ambient J04/Word opt-ins unset before the run.

**No freeze. No CP08 retry in this checkpoint.** Overall **`NOT_READY`** at R5 close: handshake remediating;
Word not in scope for that checkpoint.

CP08-R5 commit: `34f39c0` — `test(j04-m0): complete bootstrap admin password-change handshake`

## FR11 — R1–R5 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), R5 (`34f39c0` / docs `164a7c9`), WR05 documentation (`034425f`), and the freeze
documentation. Focused gates are **93 passed**
(`build/j04-m0-closure/freeze-r5-20260817T195901962Z`): FR10 set plus R5 handshake tests and
`tests/backend/test_auth_api.py`. The frozen candidate is
`c263ff550a81eccfc5bb68f2ffd2e030e8e51427` (`c263ff5`). No product or test changes are
allowed after this freeze. CP08-V5 was executed once and **FAILED** at
`document_baseline_flow`. The R5 bootstrap handshake **held**. Word COM was **not reached**.
Overall **`NOT_READY`**: there is not yet a successful CP08 run. Historical CP08-V3 aborted
on the acceptance start contract, not Word COM. CP08-V4 start contract **held**. `ACCEPTED`
is not set.

## CP08-V5 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `c263ff550a81eccfc5bb68f2ffd2e030e8e51427`.
Lauf-SHA: `05aed9f`. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set.
No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v5-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `document_baseline_flow` — `version payload missing etag`. Backend log: `POST /documents/versions/create` **403**. R5 handshake **PASS** (`POST /auth/login` 200, `GET /auth/me` 409, `POST /auth/change-password` 204, `GET /auth/me` 200). Start contract **PASS**. Word **not reached**. Workspace `20260817T200418444108Z-8540fb06cf7846699a99cac847f51887` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

## CP08-R6 — Document-create 403 (test-only)

CP08-V5 stopped at `document_baseline_flow`. Backend log: `POST /documents/versions/create` **403**.
The fail log only said `version payload missing etag`. Investigation (read-only V5 evidence + code):

| # | Check | Finding |
| --- | --- | --- |
| 1 | 403 body | Not in V5 fail log. Product mapping: `PermissionDeniedError` → `{"detail":{"error":"forbidden",...}}`. |
| 2 | Actor | Create used `ctx.tokens["admin"]` (`j04acceptadmin`, Admin). QMB user was already seeded and used for the workflow profile. |
| 3 | Owner | `documents.api.create_document_version` requires effective QMB or delegated create. `_delegated_create_allowed` is unset in the acceptance run. Transport has no domain logic. |
| 4 | Coverage gap | HTTP fixtures call `set_user_qmb("admin", True)` then create as admin. Realprocess did not. Authorization tests create as `qmb`. |

Decision: **harness actor + diagnostics, not product.** Bootstrap admin is not granted QMB. Failures now include `status=` and `error=` before etag parse.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r6-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  tests/backend/test_documents_authorization_http.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **36 passed** (`build/j04-m0-closure/cp08-r6-20260818T042343176Z`). Ambient J04/Word opt-ins unset.

**No freeze. No CP08 retry in this checkpoint.** Overall **`NOT_READY`** at R6 close. Word not in scope. `ACCEPTED` is not set.

CP08-R6 commit: `e28a44d` — `test(j04-m0): use seeded QMB for document create and surface 403`

## FR12 — R1–R6 technical freeze

This checkpoint freezes R1 (`fbea360`), R2 (`30b73e9`), R3 (`c3d6587`), R4 (`5233b5d` /
`63dda17`), R5 (`34f39c0` / docs `164a7c9`), R6 (`e28a44d` / docs `1f72451`), WR05
documentation (`034425f`), and the freeze documentation. Focused gates are **108 passed**
(`build/j04-m0-closure/freeze-r6-20260818T042711993Z`): FR11 set plus R6 handshake/create tests
and `tests/backend/test_documents_authorization_http.py`. The frozen candidate is
`b63d9a16f87e8e9a12942d41101ee793d1fbb209` (`b63d9a1`). No product or test changes are
allowed after this freeze. CP08-V6 was executed once and **FAILED** at
`etag_concurrency_race`. Document create **PASS**. Word COM was **not reached**.
Overall **`NOT_READY`**: there is not yet a successful CP08 run. `ACCEPTED` is not set.

## CP08-V6 — Final acceptance attempt (FAILED / NOT_READY)

Executed once against CandidateSha `b63d9a16f87e8e9a12942d41101ee793d1fbb209`.
Lauf-SHA: `049c0fd`. Realprocess via `--j04-final-acceptance`. Word COM live opt-in was set.
No repair, no retry.

| Step | Result |
| --- | --- |
| PostgreSQL live | **PASS** — PG18 preflight; **51 passed**; `build/j04-m0-closure/cp08-v6-pg-live-runner.log` |
| Full real-process E2E | **FAILED** at `etag_concurrency_race` — harness `TypeError` (`sorted expected 1 argument, got 2`). R6 create **PASS** (`POST /documents/versions/create` 200, import/assign/start 200). Race HTTP on backend log: assign-roles **200** then **409**. Word **not reached**. Workspace `20260818T043346608779Z-d3a488be334042e7ab81a38da5b9ffb7` |
| Word COM live / Onedir / regression / Golive / visible client | **NOT RUN** |

`ACCEPTED` is not set.

## CP08-R7 — ETag-race harness (test-only)

CP08-V6 reached `etag_concurrency_race`. Backend assign-roles race was **200** then **409**.
The harness then raised `TypeError`: `sorted expected 1 argument, got 2` from
`sorted(int, int)`. That is a harness bug, not a product deviation. The fail detail was only
`TypeError` because the generic except stores `type(exc).__name__`.

Fix: `evaluate_etag_race_payloads()` passes both statuses as one iterable to `sorted()`.
Contract remains `[200, 409]`. Both worker bodies use `ETAG_RACE_STABLE_ASSIGNMENT`
(`editor` / `reviewer` / `approver`); `observer` is no longer a race winner. Product auth,
PG, Word, and packaging are unchanged.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-r7-$stamp"
$Py -m pytest `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/backend/test_documents_concurrency_http.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp $Base
```

Result: **54 passed** (`build/j04-m0-closure/cp08-r7-20260818T045911092Z`). Ambient J04/Word
opt-ins unset. `git diff --check` on the two test files: exit 0. Independent review confirmed
the R7 content diff and code; evidence contents were ACL-blocked in that review session.

CP08-R7 commit: `f5dcfa8` — `test(j04-m0): fix etag race harness evaluation`

**No freeze yet.** Next allowed sequence: new technical freeze, then exactly one CP08 run.
Overall **`NOT_READY`**. Word still **not reached**. `ACCEPTED` is not set.

## CP08-R2 remediation specification (real-process scenario)

Test-only scope. Replaces the `pytest.skip` stub with an ordered scenario in
`tests/acceptance/j04_m0_acceptance_scenario.py`. **No freeze.** PG live, full
`j04_final_acceptance` execution, Word COM live, and Onedir remain **NOT RUN** in R2.

### PG test environment and admin bootstrap

| Item | Contract |
| --- | --- |
| Guard | `preflight_isolated_postgres_target()` before any destructive work |
| Admin DSN | `QMTOOL_PG_TEST_ADMIN_DSN` from gitignored `.env`; never logged |
| Reset | `QMTOOL_PG_TEST_RESET` injected only for the pytest child / backend env |
| Provision | `prepare_live_environment()` + `migrate_usermanagement_schema(migrator_dsn)` |
| Runtime DSN | Backend receives `QMTOOL_PG_DSN = runtime_dsn` only (never admin DSN) |
| Bootstrap admin | `QMTOOL_BOOTSTRAP_ADMIN_USERNAME/PASSWORD` on first backend start; first `/auth/me` is 409 `password_change_required` until `POST /auth/change-password` (CP08-R5 handshake) |
| Directory users | Created via `POST /users` after bootstrap session is usable (`/auth/me` 200); user `qmb` has `is_qmb=True` |
| Document create | `POST /documents/versions/create` uses the seeded QMB token (CP08-R6); Admin is not treated as QMB |

### Two separate client processes and sessions

| Item | Contract |
| --- | --- |
| Homes | `client1-home` / `client2-home` under harness workspace |
| Processes | `j04_m0_client_worker.py` subprocesses only |
| Sessions | In-memory Bearer per worker; output uses `token_fingerprint` only |
| Proof | Distinct `QMTOOL_HOME` paths and token fingerprints in step `client_process_sessions` |

### ETag concurrency synchronization

| Item | Contract |
| --- | --- |
| Pattern | Two workers issue the same `If-Match` assign-roles mutation in parallel |
| Bodies | Both keep seeded `editor` / `reviewer` / `approver` (CP08-R7); no `observer` |
| Expected | Exactly one HTTP **200** and one HTTP **409**; harness `sorted([status_a, status_b])` |
| Transport | Worker `--action http` (no shared in-process `TestClient`) |

### M0 HTTP coverage (orchestrator + workers)

| Area | Step | Reference alignment |
| --- | --- | --- |
| Health/OpenAPI | `health_and_openapi` | Dev `/health`, `/openapi.json` |
| Artifacts | `artifacts_transport` | No `storage_key` in list/metadata |
| Signature | `signature_verify_password` | Import PNG + `/signature/verify-password` |
| Training read | `training_read_receipt` | Approve → open-released → confirm receipt |
| Comments / CR / lifecycle | `comments_lifecycle_change_requests` | Comment, change request, archive |
| Document baseline | `document_baseline_flow` | Create → import PDF → assign → start |

### Backend restart and persistence/session contract

| Item | Contract |
| --- | --- |
| Restart | `harness.stop_process("backend")` then start new backend on same `backend-home` |
| Documents | SQLite under backend home survives restart (`ARCHIVED` readback) |
| Sessions | Pre-restart Bearer tokens remain valid via `GET /auth/me` (PG-backed sessions) |
| Step | `persistence_and_session_contract` |

### Fail-closed preconditions, redaction, PID cleanup

| Item | Contract |
| --- | --- |
| Opt-in | `QMTOOL_J04_FINAL_ACCEPTANCE=I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN` |
| Port | `127.0.0.1:8000` must be free before backend start |
| PIDs | Harness tracks and terminates **only** self-spawned processes |
| Logs | `redact_log_text()` on all harness/scenario logs under `build/j04-m0-closure/` |
| Abort | First failing required step stops the scenario (`FAIL` result) |

### Word COM live boundary (explicitly not R2 execution)

| Item | Contract |
| --- | --- |
| Env | `QMTOOL_J04_WORD_COM_LIVE=I_UNDERSTAND_THIS_IS_A_REAL_WORD_COM_RUN` |
| R2 | Step `word_com_live_boundary` returns **SKIP** with documented reason |
| CP08 | Requires interactive Windows session; real `import-docx` only when opt-in set |
| Product | Uses existing `DispatchEx` isolation from CP03; no new COM entrypoint |

### CP08-R2 verification (implementation only)

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest `
  tests/acceptance/test_j04_m0_harness_unit.py `
  tests/acceptance/test_j04_m0_acceptance_scenario_unit.py `
  tests/acceptance/test_j04_m0_realprocess.py `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp08-r2
$Py -m pytest tests/acceptance/test_j04_m0_realprocess.py -m "j04_final_acceptance" -q
```

Result: **15 passed** + final gate **1 skipped** without opt-in (2026-08-17)

Changed files (test-only):

- `tests/acceptance/j04_m0_acceptance_scenario.py` — ordered scenario orchestrator
- `tests/acceptance/j04_m0_client_worker.py` — `--action http` for worker mutations
- `tests/acceptance/j04_m0_realprocess_harness.py` — `stop_process()` for restart step
- `tests/acceptance/test_j04_m0_acceptance_scenario_unit.py` — focused scenario unit tests
- `tests/acceptance/test_j04_m0_realprocess.py` — calls `run_acceptance_scenario()`

