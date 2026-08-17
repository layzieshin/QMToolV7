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
| Word readiness | Word COM `DispatchEx` probe (interactive) | BLOCKED | — | `CO_E_SERVER_EXEC_FAILURE` (0x80080005); freeze **not set** |
| CP09 | Human acceptance | TODO | — | Depends second CP08 + explicit human sign-off |

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
2. Word COM readiness in an interactive session — **BLOCKED** (`CO_E_SERVER_EXEC_FAILURE`)
3. New technical freeze — **blocked until Word readiness PASS**
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
| Bootstrap admin | `QMTOOL_BOOTSTRAP_ADMIN_USERNAME/PASSWORD` on first backend start |
| Directory users | Created via `POST /users` after bootstrap login |

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
| Expected | Exactly one HTTP **200** and one HTTP **409** with current etag in body |
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

