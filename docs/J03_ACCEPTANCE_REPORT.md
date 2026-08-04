# J03 Acceptance Report (R1 / R1.1)

Branch: `feature/j03-documents-workflow-profiles`
Worktree: `I:/Projekte/QMToolV7-j03`
Status: remediation packages J03-R1 + J03-R1.1 implemented; commit/push deferred.

## Execution path

```text
CLI / DocumentsWorkflowApi
  -> DocumentsService (require_confirmed_user_context + is_effective_qmb)
  -> WorkflowProfileRelationalStore
  -> SQLite documents DB (0002_workflow_profiles)

Bootstrap/Upgrade only:
  WorkflowProfileSeedReader -> atomic import_seed
  fresh DB: bundled seed
  pre-J03 DB: previously resolved profiles_file

Runtime adapter (single boundary):
  relational DRAFT  <->  runtime IN_PROGRESS
  modules/documents/workflow_profile_runtime_adapter.py
  used by WorkflowProfileVersionDefinition.to_runtime_profile()
```

## Binding resolution

```text
DocumentType -> document_type_definitions -> active definition
  -> highest version with effective_from <= now
```

Binding sources recorded in `document_type_definitions.binding_source`:

| Document type | Default profile | Override | Source |
|---|---|---|---|
| VA/AA/FB/LS | long_release | false | module.settings.doc_type_profile_rules |
| EXT | external_control | false | service.import_existing_pdf hardcoded path |
| OTHER | long_release | true | module.settings.doc_type_profile_rules |

### Workflow start binding (R1.1)

- Authoritative profile is always `state.workflow_profile_id`
- Service loads the runtime profile from the relational store
- Optional API/CLI `profile_id` is compatibility-check only (match or fail-closed)
- CLI/PyQt do not transmit a freely chosen start profile
- Profile override remains create-time only (`allows_profile_override`)

## Import rules (R1 / R1.2)

- No `document_headers` heuristic
- Bootstrap provenance is derived **inside Documents** from the generic
  `database_preflight_statuses` map captured **before** `runtime_preflight` migrate
  (platform stores immutable `DatabaseStatus` values only; no Documents import in bootstrap)
- Fresh install (`missing` / empty DB) → always bundled seed — even when a divergent local `profiles_file` exists under app-home
- Confirmed V1 (`current_version == 1` pending/current, or `adoptable_v1`) → previously resolved local `profiles_file`
- Already J03 schema (`current_version >= 2`) with empty/manipulated profile stock → fail-closed (no silent re-seed)
- Classification is per profile (`SEED` / `MIGRATED`)
- Package-only profiles are not auto-added on legacy migration
- Legacy `IN_PROGRESS` normalized to `DRAFT` before storage
- Import report rows include path, hashes, classification, status, block reason

## Runtime status vocabulary (R1.1)

- Relational profiles store start status `DRAFT`
- Document runtime, engine, and new `workflow_profile_json` snapshots use `IN_PROGRESS`
- Workflow start / reject-back-to-edit keep `IN_PROGRESS` semantics
- Existing snapshots are not migrated or rewritten on upgrade

## Authorization

- Public `UserContext` via `modules.usermanagement.api`
- `require_confirmed_user_context(actor)` then `is_effective_qmb(actor)`
- No duck typing, no `"unknown"` actor fallback
- ADMIN without effective QMB rejected

### Accepted UM public surface change (R1.1)

- New public helper: `require_confirmed_user_context` in `modules/usermanagement/api.py`
- Validates confirmed `UserContext` + non-empty identity fields only
- No new roles, permissions, assignments, or persistence
- Documents does not import `modules.usermanagement.contracts`
- Documents does not read private confirmation markers
- Contract tests: `tests/modules/test_usermanagement_require_confirmed_user_context.py`

## Transition model

- Relational first transition starts at `DRAFT` (not stored `DRAFT->IN_PROGRESS`)
- Runtime reconstruction maps that start to `IN_PROGRESS`
- Workflow start is not a status transition in the profile graph; runtime status becomes `IN_PROGRESS`
- Capability matrix: `docs/J03_WORKFLOW_ENGINE_CAPABILITY_MATRIX.md`
- Engine-evaluable policies only (`ONE_OF_POOL` / `NONE`); `ALL_ASSIGNED` rejected

## Changed-file / scope notes (R1.1)

Primary code:

- `modules/documents/workflow_profile_runtime_adapter.py` (new adapter boundary)
- `modules/documents/workflow_profile_store.py` (`to_runtime_profile` uses adapter)
- `modules/documents/workflow_use_cases.py`, `validation.py`, `signature_guard.py`, `contracts.py` (runtime `IN_PROGRESS` restored)
- `modules/documents/service.py`, `api.py` (start binding from `state.workflow_profile_id`)
- CLI/PyQt/legacy GUI start callers stop transmitting free profile choice
- `modules/usermanagement/api.py` (`require_confirmed_user_context` documented/accepted)
- Tests: `tests/modules/test_documents_j03_r11_runtime_compat.py`, UM contract tests, related matrix updates
- Docs: this report, capability matrix, architecture contract, modules developer guide

Out of scope (unchanged): J04, Outbox, Documents roles model, GUI comfort, general status migration `IN_PROGRESS→DRAFT`, commit/push.

## Verification commands and results (R1.2 / gate repair)

```powershell
git diff --check
# result: clean when last checked

$env:PYTHONPATH="."
I:\Projekte\QMToolV7\.venv\Scripts\python.exe -m pytest tests/interfaces/test_json_persistence_gate.py tests/platform/test_database_migration_gate.py -q
# result: passed

I:\Projekte\QMToolV7\.venv\Scripts\python.exe scripts/database_migration_gate.py --output "$env:TEMP\qmtool-migration-gate-j03.json"
# result: ok=true (manifest + JSON allowlist)

I:\Projekte\QMToolV7\.venv\Scripts\python.exe scripts/golive_gate.py --output "$env:TEMP\qmtool-golive-gate-j03.json"
# result: ok=true
```

## Known residual limits

- Desktop legacy runtime still has no persistent opaque session repository; positive profile-admin CLI is proven in-process with confirmed backend session (`tests/interfaces/test_documents_workflow_profile_cli.py`). Subprocess e2e remains fail-closed without session transport.
- `profiles_file` settings cleanup remains a separate package.
- No second profile API, no new roles/permissions model, no J04 instance/assignment/decision persistence.
- General document-status migration from runtime `IN_PROGRESS` to relational `DRAFT` is explicitly deferred.

## Explicit non-goals completed as non-goals

- No second runtime JSON truth
- No Documents backup mechanism beyond AP-027 V1→V2
- No PyQt profile administration
- No relational stored `IN_PROGRESS`
- No premature engine-wide status rename to `DRAFT`
