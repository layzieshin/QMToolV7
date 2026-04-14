# Modules Developer Guide

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

This guide summarizes each module for implementation and extension work.

Normative architecture contract for document control:
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
User-facing module operations:
- `docs/MODULES_USER_GUIDE.md`
Project engineering rules:
- `docs/AGENTS_PROJECT.md`
Project GUI architecture:
- `docs/GUI_ARCHITECTURE_PROJECT.md`

## usermanagement

### Ports / capabilities

- Provided port: `usermanagement_service`
- Provided capabilities: `auth.authenticate`, `auth.session.read`

### Settings

- Contribution in `modules/usermanagement/module.py`
- Key: `users_db_path` (default: `storage/platform/users.db`)
- Key: `seed_mode` (repository default: `legacy_defaults`; see production standard below)
- Key: `dev_mode` (repository default: `true`; local seed convenience toggle)

| Key | Governance class | Notes |
| --- | --- | --- |
| `users_db_path` | operational | Storage location; change with backup/migration plan. |
| `seed_mode` | governance_critical | Controls whether development-style seed accounts exist. |
| `dev_mode` | development | Enables local dev seeding shortcuts; disable for production-like runs. |

### Production security standard (normative)

For QM-relevant or production deployments, the following is **mandatory product policy**, not an optional enhancement:

- **`seed_mode` MUST be `hardened`**: no implicit creation of well-known demo accounts; bootstrap only via controlled init (e.g. `python -m interfaces.cli.main init` with explicit admin credentials).
- **`dev_mode` MUST be `false`** for production-like and release validation runs.
- **No known-default passwords** in production datasets.
- **Credential storage**: passwords MUST NOT remain at rest as reversible plaintext for production go-live in regulated environments. The repository uses one-way bcrypt verification for persisted credentials; preserve this behavior for all new auth code paths and migrations.
- **Role model**: system roles (`Admin`, `QMB`, `User`, …) are part of the **mandatory** authorization surface for documents and platform operations—not a future add-on. New roles or finer RBAC must extend this model, not bypass it.

The repository defaults (`seed_mode=legacy_defaults`, `dev_mode=true`) exist for **local development and smoke** only and MUST NOT be relied on for production configuration.

### Persistence / files

- SQLite users DB via `SQLiteUserRepository`
- Session file: `storage/platform/session/current_user.json`
- Schema: `modules/usermanagement/schema.sql`

### Events

- Auth:
  - `domain.usermanagement.auth.succeeded.v1`
  - `domain.usermanagement.auth.failed.v1`
- Session:
  - `domain.usermanagement.session.login.v1`
  - `domain.usermanagement.session.logout.v1`
- User ops:
  - `domain.usermanagement.user.created.v1`
  - `domain.usermanagement.user.password_changed.v1`

### Tests / extension points

- `tests/modules/test_usermanagement_persistence.py`
- Additional tests MUST cover hardened seed, legacy-password migration behavior, and bcrypt verification paths.

## documents

### Ports / capabilities

- Provided ports:
  - `documents_service`
  - `documents_pool_api`
  - `documents_workflow_api`
- Provided capabilities:
  - `documents.workflow.manage`
  - `documents.version.manage`
- Required port: `signature_api`
- Required port: `registry_projection_api`

Contract framing:
- Authoritative kernel: `documents_service` (state machine + invariants).
- Specialized read view: `documents_pool_api`.
- Specialized write/workflow view: `documents_workflow_api`.
- Business state ownership remains in documents only.
- Write-owner rule: all business writes must end in `documents_service`; adapters must not bypass service invariants.

### Settings

- Contribution in `modules/documents/module.py`
- Keys:
  - `default_profile_id`
  - `allow_custom_profiles`
  - `profiles_file`
  - `documents_db_path`
  - `artifacts_root`

### Persistence / files

- SQLite document DB (`documents_db_path`)
- Artifact storage filesystem (`artifacts_root`)
- Schema: `modules/documents/schema.sql`
- Profile config: `modules/documents/workflow_profiles.json`
- Master/Version split:
  - `document_headers`
  - `document_versions`
- Semantic split:
  - `doc_type` = fachliche Dokumentart (`VA`, `AA`, `FB`, `LS`, `EXT`, `OTHER`)
  - `control_class` = Lenkungsklasse (`CONTROLLED`, `CONTROLLED_SHORT`, `EXTERNAL`, `RECORD`)
  - `workflow_profile_id` = ausführbares Profil passend zur `control_class`
- Metadata operations:
  - Header read/write via service/API (`get_header`, `update_document_header`)
  - Version metadata update via service/API (`update_version_metadata`)

### Events

- Intake / template:
  - `domain.documents.artifact.imported.v1`
  - `domain.documents.template.created.v1`
- Workflow:
  - `domain.documents.workflow.started.v1`
  - `domain.documents.editing.completed.v1`
  - `domain.documents.review.accepted.v1`
  - `domain.documents.review.rejected.v1`
  - `domain.documents.approval.accepted.v1`
  - `domain.documents.approval.rejected.v1`
  - `domain.documents.workflow.aborted.v1`
  - `domain.documents.validity.extended.v1`
  - `domain.documents.archived.v1`
  - `domain.documents.assignments.updated.v1`

### Tests / extension points

- Matrices:
  - `tests/modules/test_documents_authorization_matrix.py`
  - `tests/modules/test_documents_variants_matrix.py`
  - `tests/modules/test_documents_event_contracts.py`
- CLI/e2e:
  - `tests/e2e_cli/test_documents_cli.py`
  - `tests/e2e_cli/test_documents_cli_authorization_matrix.py`

### Migration notes (developer)

- Legacy interpretation where `doc_type` encoded governance is deprecated.
- New model:
  - `doc_type`: business classification
  - `control_class`: governance strictness
  - `workflow_profile_id`: technical profile
- Backfill behavior (runtime compatibility):
  - unknown historical fachlicher Typ => `doc_type=OTHER`
  - governance preserved in `control_class`
- Required follow-up:
  - data cleanup to replace `OTHER` with precise business type where known.

### Migration runbook + rollout gates

- Execute pre/post data-quality report for:
  - `doc_type=OTHER` count
  - `control_class` distribution
  - invalid `doc_type/control_class/workflow_profile_id` combinations
- Enforce Go/No-Go criteria:
  - no increase in `OTHER`
  - zero invalid combinations
  - regression suite green
- Keep evidence with release ticket (SQL output + test logs).

## signature

### Ports / capabilities

- Provided ports:
  - `signature_service`
  - `signature_api`
- Required capability: `auth.authenticate`
- Provided capabilities:
  - `signature.visual.sign`
  - `signature.api.fixed_position`

### Settings

- Contribution in `modules/signature/module.py`
- Keys:
  - `require_password`
  - `default_mode`
  - `templates_db_path`
  - `assets_root` (encrypted signature blobs)
  - `master_key_path`

### Persistence / files

- SQLite template/asset metadata DB (`templates_db_path`)
- Encrypted signature asset blobs under `assets_root`
- Master key file at `master_key_path`
- Schema: `modules/signature/schema.sql`

### Events

- `domain.signature.sign.requested.v1`
- `domain.signature.sign.dry_run.v1`
- Module lifecycle started/stopped events

### Tests / extension points

- `tests/modules/test_signature_service_v2.py`
- `tests/modules/test_module_events.py`
- `tests/modules/test_signature_templates.py`
- Legacy top-level `signature/` package has been removed; all runtime signing logic is now in `modules/signature/*`.
- Signature assets are imported as PNG/GIF and normalized to encrypted PNG blobs.
- User signature templates are persisted separately and can be used by standalone CLI signing flows.

## registry

### Ports / capabilities

- Provided ports:
  - `registry_service`
  - `registry_api`
  - `registry_projection_api`
- Provided capabilities:
  - `documents.registry.read`
  - `documents.registry.write`

### Settings

- Contribution in `modules/registry/module.py`
- Key:
  - `registry_db_path`

### Persistence / files

- SQLite registry DB (`registry_db_path`)
- Schema: `modules/registry/schema.sql`

### Events

- `domain.registry.module.started.v1`
- `domain.registry.module.stopped.v1`

### Tests / extension points

- `tests/modules/test_registry_module.py` (includes deterministic projection replay checks aligned with the recovery contract’s rebuild primitive)
- Registry is updated deterministically by `documents` transitions.
- `registry_api` is read-focused; projection writes are only exposed via `registry_projection_api` for the documents module.
- `registry_projection_api` rejects non-documents sources (`source_module_id` guard).
- Rejected projection attempts are logged and published as `domain.registry.projection.rejected.v1`.

## settings/ui

### Runtime services

- `settings_service` (`qm_platform/settings/settings_service.py`)
- `settings_registry` (`qm_platform/settings/settings_registry.py`)
- `settings_store` (`qm_platform/settings/settings_store.py`)

### Settings governance classification

Use the following classification for all module settings keys:

- `operational`: runtime paths, storage locations, diagnostics toggles
- `development`: local-only shortcuts and smoke defaults
- `governance_critical`: business/process steering values that impact compliance behavior

Policy:
- `governance_critical` changes are release-controlled (review + evidence), not ad-hoc runtime edits.
- `operational` changes are allowed for `ADMIN`/`QMB` with traceability.
- `development` values must remain explicitly non-production.
- CLI enforcement: `settings set` requires `--acknowledge-governance-change` when any `governance_critical` key is changed.
- Technical key mapping source: `qm_platform/settings/governance_critical_keys.py`.

### CLI adapters

- `interfaces/cli/main.py`:
  - `init` (first-run path bootstrap + idempotent admin seed)
  - `doctor` (runtime readiness check for paths/settings/db/license/admin)
  - signature templates/assets:
    - `sign import-asset`
    - `sign template-create`
    - `sign template-list`
    - `sign template-sign`
  - training:
    - `training list-required`
    - `training confirm-read`
    - `training quiz-start`
    - `training quiz-answer`
    - `training comment-add`
    - `training admin-*`
  - `settings list-modules`
  - `settings get --module ...`
  - `settings set --module ... --values-json ...`
  - Documents metadata/register:
    - `documents header-get`
    - `documents header-set`
    - `documents metadata-get`
    - `documents metadata-set`
    - `documents pool-get-register`

### UI adapters

- Active PyQt adapter:
  - `interfaces/pyqt/main.py` (entry)
  - `interfaces/pyqt/shell/main_window.py` (shell host, role/license navigation handling)
  - `interfaces/pyqt/registry/catalog.py` (contribution registry)
  - `interfaces/pyqt/contributions/*` (module-facing screens)
  - `interfaces/pyqt/widgets/*` (shared UI building blocks)
- Legacy Tk adapter (compatibility/smoke only):
  - `interfaces/gui/main.py`
  - `--smoke-test` for headless validation

### Tests

- UI smoke:
  - `tests/interfaces/test_ui_mvp_smoke.py`
- users/settings CLI:
  - `tests/e2e_cli/test_users_and_settings_cli.py`

## Contract quick reference (inputs / outputs / interfaces / contracts)

### usermanagement

- Inputs
  - `login(username, password)`, `create_user(username, password, role)`, `change_password(username, new_password)`
  - profile/admin updates via `update_user_profile(...)` and `update_user_admin_fields(...)`
- Outputs
  - `AuthenticatedUser` DTOs or `None` for failed authentication
  - persisted session file (`storage/platform/session/current_user.json`)
  - domain events for auth/session/user changes
- Interfaces
  - provided: `usermanagement_service`
  - required: `event_bus` (optional), `UserRepository` (optional)
- Contracts
  - `modules/usermanagement/contracts.py`: `AuthenticatedUser`
  - `modules/usermanagement/repository.py`: repository interface for persistence
  - `modules/usermanagement/sqlite_repository.py`: SQLite-backed contract implementation

### documents

- Inputs
  - workflow/write operations via `DocumentsWorkflowApi` (`create_document_version`, `start_workflow`, `accept_review`, `accept_approval`, metadata/header updates)
  - read/list operations via `DocumentsPoolApi` (`list_tasks_for_user`, `list_recent_documents_for_user`, `list_current_released_documents`)
- Outputs
  - `DocumentVersionState`, `DocumentHeader`, readmodel DTO lists (`DocumentTaskItem`, `ReviewActionItem`, `RecentDocumentItem`, `ReleasedDocumentItem`)
  - artifacts in `artifacts_root` and persisted rows in `documents_db_path`
  - workflow/domain events
- Interfaces
  - provided: `documents_service`, `documents_pool_api`, `documents_workflow_api`
  - required: `signature_api`, `registry_projection_api`
- Contracts
  - `modules/documents/contracts.py`: states, enums, readmodel DTOs
  - `modules/documents/api.py`: adapter API boundaries
  - `modules/documents/readmodel_use_cases.py`: read-side SRP split used by service
- `modules/documents/workflow_use_cases.py`: write/workflow SRP split used by `DocumentsService`

### signature

- Inputs
  - `SignatureApi.sign_with_fixed_position(SignRequest)`
  - `import_signature_asset(owner_user_id, source_path)`
  - template APIs: `create_user_signature_template`, `list_user_signature_templates`, `sign_with_template`
- Outputs
  - `SignResult`, `SignatureAsset`, `UserSignatureTemplate`
  - signed PDF output path resolved by `modules/signature/output_path_policy.py`
  - audit + domain events for signing flows
- Interfaces
  - provided: `signature_service`, `signature_api`
  - required: `auth.authenticate` capability, optional crypto signer port
- Contracts
  - `modules/signature/contracts.py`: `SignRequest`, `SignResult`, template/layout DTOs
  - `modules/signature/api.py`: external API surface
  - `modules/signature/sqlite_repository.py` + `schema.sql`: template/asset metadata persistence
- `modules/signature/template_use_cases.py`: template/asset SRP split used by `SignatureServiceV2`

### registry

- Inputs
  - projection writes via `registry_projection_api.upsert_from_documents(...)`
  - read access via `RegistryApi.get_entry(...)`, `list_entries()`
- Outputs
  - `RegistryEntry` snapshots in registry SQLite store
  - projection rejection events for invalid source module IDs
- Interfaces
  - provided: `registry_service`, `registry_api`, `registry_projection_api`
  - required: document projection payloads from documents service
- Contracts
  - `modules/registry/contracts.py`: `RegistryEntry`
  - `modules/registry/projection_api.py`: constrained write interface
  - `modules/registry/api.py`: read interface

### training

- Inputs
  - user flow via `TrainingApi` (`list_open_assignments_for_user`, `confirm_read`, `start_quiz`, `submit_quiz_answers`, `add_comment`)
  - admin flow via `TrainingAdminApi` (`create_category`, assignments sync, quiz import)
- Outputs
  - `TrainingAssignment`, `TrainingOverviewItem`, `OpenTrainingAssignmentItem`, `QuizSession`, `QuizResult`, `TrainingComment`
  - encrypted quiz blobs in `quiz_blob_root`, assignments in `training_db_path`
  - training domain events (`read.confirmed`, `quiz.completed`, `comment.created`)
- Interfaces
  - provided: `training_service`, `training_api`, `training_admin_api`
  - required: `documents_pool_api`, `usermanagement_service`
- Contracts
  - `modules/training/contracts.py`: assignment/quiz/category DTOs
  - `modules/training/api.py`: user/admin API boundaries
  - `modules/training/service.py`: orchestration over repository + quiz blob store
- `modules/training/assignment_use_cases.py`: assignment/read-confirmation SRP split used by `TrainingService`

## training

### Ports / capabilities

- Provided ports:
  - `training_service`
  - `training_api`
  - `training_admin_api`
- Required ports:
  - `documents_pool_api`
  - `usermanagement_service`
- Provided capabilities:
  - `training.assignment.manage`
  - `training.quiz.execute`

### Settings

- Contribution in `modules/training/module.py`
- Keys:
  - `training_db_path`
  - `quiz_blob_root`
  - `quiz_master_key_path`

### Persistence / files

- SQLite training DB (`training_db_path`)
- Encrypted quiz blobs (`quiz_blob_root`)
- Schema: `modules/training/schema.sql`

### Events

- `domain.training.module.started.v1`
- `domain.training.module.stopped.v1`
- `domain.training.read.confirmed.v1`
- `domain.training.quiz.completed.v1`
- `domain.training.comment.created.v1`

### Tests / extension points

- `tests/modules/test_training_service.py`
- `tests/modules/test_training_event_contracts.py`
- `tests/modules/test_training_module_ports.py`
- `tests/e2e_cli/test_training_cli.py`
