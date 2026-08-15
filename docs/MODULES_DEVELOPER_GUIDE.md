# Modules Developer Guide

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

This guide summarizes each module for implementation and extension work.

**New module onboarding checklist:** `docs/MODULE_INTEGRATION_POLICY.md`

Public Python imports for module behavior go through `modules/<module>/api.py`.
`contracts.py` files are internal DTO/type sources unless a module `api.py` explicitly
exposes the needed names.

Normative architecture contract for document control:
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
User-facing module operations:
- `docs/MODULES_USER_GUIDE.md`
Project engineering rules:
- `docs/AGENTS_PROJECT.md`
Project GUI architecture:
- `docs/GUI_ARCHITECTURE_PROJECT.md`

## container (prototype)

The `container` module is a backend-only generic Object/Artifact tree. Its
binding architecture contract is
`docs/container-module/ARCHITECTURE_CONTRACT.md`; the planned GM-01–GM-25
coverage is in `docs/container-module/REQUIREMENTS_TRACEABILITY.md`.

### Ports / capabilities

- Provided port: `container_api` (public commands and queries via
  `modules/container/api.py`)
- Required ports: confirmed `usermanagement_service`, `event_bus`,
  `audit_logger`, `settings_service`, backend-owned storage/clock/ID seams as
  the implementation requires
- Provided capabilities: `container.object.manage`,
  `container.artifact.manage`, `container.reference.manage`,
  `container.export.manage`, `container.blueprint.manage`
- Registration: backend composition only; `ModuleContract` remains required,
  but desktop `core_module_contracts()` does not register this module.

### Settings and governance

| Key | Governance class | Notes |
| --- | --- | --- |
| `container_db_path` | `operational` | SQLite path opened only by the backend process. |
| `artifact_files_root` | `operational` | Backend-owned Artifact file root; no client path access. |
| `max_depth` | technical invariant, not an admin setting | Pseudo-hard limit `32`; change only through code/deployment configuration. |
| `license_tag` | — | `none` for the prototype. |

### Persistence

Container metadata is persisted in SQLite at `container_db_path`; physical
Artifact files are stored below `artifact_files_root`. The desktop and other
clients must not open the SQLite file or share direct file access. Template
versions, stable UIDs, revisions, audit records, references, immutable
snapshots, hashes and Tombstones are explicit persisted data; schema changes
are forward-only and never silently migrate existing instances.

`ModuleBlueprintDraft` gruppiert mehrere lokale Template-Schlüssel, bestimmt
genau ein Object-Root und wird serverseitig auf fehlende Ziele, Zyklen,
Lifecycle- und Feldinvarianten geprüft. Veröffentlichung erzeugt und publiziert
alle Template-Versionen atomar in berechneter Abhängigkeitsreihenfolge;
`module_blueprints` und `module_blueprint_templates` halten die fachliche
Modulzuordnung relational fest.

### Events

Versioned domain events are published only after the successful persistence
commit, including `domain.container.object.created.v1`,
`domain.container.object.archived.v1`, `domain.container.artifact.created.v1`,
`domain.container.artifact.finalized.v1`,
`domain.container.artifact.signed.v1` and
`domain.container.artifact.corrected.v1` sowie
`domain.container.module_blueprint.published.v1`. Events notify about committed domain
changes and are not a request/response surface.

### Tests / extension points

- Module/API and invariant tests: `tests/modules/container/`
- Planned GM matrix and concrete test names:
  `docs/container-module/REQUIREMENTS_TRACEABILITY.md`
- Architecture boundary test: `tests/architecture/test_container_backend_boundary.py`
- The prototype requires positive GM-01–GM-25 coverage, negative invariant
  tests, permission-filtered search tests, post-commit event tests and
  immutability/template-version regressions.

## usermanagement

### Ports / capabilities

- Provided port: `usermanagement_service`
- Provided capabilities: `auth.authenticate`, `auth.session.read`

### Settings

- Contribution in `modules/usermanagement/module.py`
- Key: `users_db_path` (default: `storage/platform/users.db`)
- Key: `seed_mode` (repository default: `legacy_defaults`; see production standard below)
- Key: `dev_mode` (repository default: `true`; local seed convenience toggle)

### Public API surface note (J03-accepted)

- `modules/usermanagement/api.py` exports `require_confirmed_user_context(actor) -> UserContext`.
- Scope: validate an already confirmed public `UserContext` with non-empty `user_id` / `session_id` / `request_id`.
- Non-scope: no new roles, permissions, assignments, or persistence.
- Documents profile admin combines it with `is_effective_qmb`; ADMIN without effective QMB remains rejected.
- Documents must not import `modules.usermanagement.contracts` and must not read private confirmation markers.

| Key | Governance class | Notes |
| --- | --- | --- |
| `users_db_path` | operational | Storage location; change with backup/migration plan. |
| `seed_mode` | governance_critical | Controls whether development-style seed accounts exist. |
| `dev_mode` | development | Enables local dev seeding shortcuts; disable for production-like runs. |

### Production security standard (normative)

For QM-relevant or production deployments, the following is **mandatory product policy**, not an optional enhancement:

- **`seed_mode` MUST be `hardened`**: no implicit creation of well-known demo accounts; bootstrap only via controlled init (e.g. `.\.venv\Scripts\python.exe -m interfaces.cli.main init` with explicit admin credentials).
- **`dev_mode` MUST be `false`** for production-like and release validation runs.
- **No known-default passwords** in production datasets.
- **Credential storage**: passwords MUST NOT remain at rest as reversible plaintext for production go-live in regulated environments. The repository uses one-way bcrypt verification for persisted credentials; preserve this behavior for all new auth code paths and migrations.
- **Role model**: system roles (`Admin`, `QMB`, `User`, …) are part of the **mandatory** authorization surface for documents and platform operations—not a future add-on. New roles or finer RBAC must extend this model, not bypass it.

The repository defaults (`seed_mode=legacy_defaults`, `dev_mode=true`) exist for **local development and smoke** only and MUST NOT be relied on for production configuration.

### Persistence / files

- SQLite users DB via `SQLiteUserRepository`
- Session file: `storage/platform/session/current_user.json`
- Schema migration: `modules/usermanagement/migrations/0001_initial.sql`

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
- PyQt workflow adapter (`interfaces/pyqt/contributions/documents_workflow_view.py`) behandelt signaturpflichtige Uebergaenge und Jahresverlaengerung als harte Signaturschritte; ohne callable `signature_api.sign_with_fixed_position` darf kein erfolgreicher Abschluss signalisiert werden.

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
- Released-PDF-Dateinamensregel (`DocumentsService._build_released_filename`): Umlaute werden transliteriert (`ae/oe/ue/ss`), unsichere Zeichen entfernt, leerer Titel faellt auf `Dokument` zurueck.
- Schema migration: `modules/documents/migrations/0001_initial.sql`
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

### Identity rule (documents)

- `document_id` ist die fachliche Kennung und wird vom Aufrufer geliefert.
- Keine automatische UUID-Erzeugung fuer `document_id` in Adaptern oder Services.
- UUIDs sind nur fuer interne/opake IDs wie `artifact_id` oder `event_id` erlaubt.

### Signature/Artifact execution rules

- `IN_PROGRESS -> IN_REVIEW`: `SOURCE_DOCX` wird bei Bedarf in `SOURCE_PDF` ueberfuehrt, dann signiert.
- `IN_REVIEW -> IN_APPROVAL` und `IN_APPROVAL -> APPROVED`: kanonischer Input ist `SIGNED_PDF` der aktuellen Version.
- GUI und PDF-Renderer verwenden gemeinsame Layout-Mathematik aus `modules/signature/layout_math.py`, damit Preview und finales PDF deckungsgleich bleiben.
- `SignaturePlacementDialog` bleibt der gemeinsame Dialog (inkl. `template_list_provider`/`template_load_callback` fuer Preset-Auswahl).

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
- Schema migration: `modules/signature/migrations/0001_initial.sql`

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
- Schema migration: `modules/registry/migrations/0001_initial.sql`

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
- CLI/PyQt settings writes require a confirmed context resolved through the authoritative PostgreSQL session path. Legacy desktop compositions have no opaque-session repository and are intentionally read-only; `QMTOOL_SESSION_TOKEN` or the `session_token` port is only useful in a runtime that can resolve it through that path.
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
  - `settings set --module ... --values-json ...` (fail-closed in the legacy desktop runtime; a later transport package connects it to the authoritative backend session; governance keys still need `--acknowledge-governance-change`)
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

## Contract quick reference (inputs / outputs / runtime interfaces / internal contracts)

The file paths below document implementation ownership. They do not create additional
external Python import boundaries beyond each module's `api.py`.

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
- Internal contracts/files
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
- Internal contracts/files
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
- Internal contracts/files
  - `modules/signature/contracts.py`: `SignRequest`, `SignResult`, template/layout DTOs
  - `modules/signature/api.py`: public API surface
  - `modules/signature/sqlite_repository.py` + registered migration chain: template/asset metadata persistence
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
- Internal contracts/files
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
- Internal contracts/files
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
- Schema migration: `modules/training/migrations/0001_initial.sql`

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

## incident_management

Architecture contract: `docs/INCIDENT_MANAGEMENT_ARCHITECTURE_CONTRACT.md`

### Ports / capabilities

- Provided ports:
  - `incident_management_api`
- Required ports:
  - `logger`, `audit_logger`, `event_bus`, `settings_service`, `usermanagement_service`, `app_home`
- Provided capabilities:
  - `incident_management.incident.manage`
  - `incident_management.capa.manage`
  - `incident_management.review.manage`
- License tag: `incident_management`

### Settings

- Contribution in `modules/incident_management/module.py`

| Key | Governance class | Notes |
| --- | --- | --- |
| `incident_db_path` | operational | SQLite store path |
| `artifacts_root` | operational | Attachment and report storage |
| `categories` | operational | Incident category list |
| `label_groups` | operational | Label grouping config |
| `criticality_groups` | governance_critical | Resolved on assess (event `criticality_group`); not a second role source |
| `standard_deadlines` | governance_critical | Default due dates for actions (`immediate_action_days`, `corrective_action_days`, `preventive_action_days`, `qmb_review_days`) |
| `effectiveness_delay` | governance_critical | Days until planned effectiveness review when no explicit date |
| `capa_required_rules` | governance_critical | CAPA trigger rules in `capa_rules.derive_capa_required` |
| `report_templates` | governance_critical | Default template IDs on `ReportResult.report_template_id` |

Leitung (module-internal role) is assigned via `assign_module_role` / `module_role_assignments` in the incident DB — not via a parallel settings list.

Module settings may be changed by **Admin or QMB** through `incident_management_api.set_module_settings`. Governance-critical keys require `acknowledge_governance_change=True` (platform `SettingsService` gate).

### Events

- `domain.incident_management.incident.submitted.v1`
- `domain.incident_management.inquiry.opened.v1` / `.answered.v1`
- `domain.incident_management.incident.assessed.v1`
- `domain.incident_management.capa.required.v1` / `.updated.v1`
- `domain.incident_management.action.created.v1` / `.completed.v1`
- `domain.incident_management.effectiveness.planned.v1` / `.reviewed.v1`
- `domain.incident_management.leadership.forwarded.v1` / `.acknowledged.v1`
- `domain.incident_management.management_review.created.v1` / `.in_discussion.v1` / `.acknowledged.v1`
- `domain.incident_management.report.generated.v1`
- `domain.incident_management.incident.closed.v1` / `.archived.v1`

### Tests / extension points

- `tests/modules/test_incident_management_*.py`
- `tests/e2e_cli/test_incident_management_cli_*.py`
- `tests/interfaces/test_incident_management_pyqt_navigation_smoke.py`
