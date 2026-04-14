# PyQt Contributions Reference

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

This reference documents active PyQt contributions in `interfaces/pyqt/*` with their inputs, outputs, interfaces, and contract surfaces.

## Scope

- Source of truth: `interfaces/pyqt/*`
- Shell host: `interfaces/pyqt/shell/main_window.py`
- Registry: `interfaces/pyqt/registry/catalog.py`
- Contribution contract: `interfaces/pyqt/registry/contribution.py` (`QtModuleContribution`)

## Contribution matrix

| Contribution ID | View file | Inputs | Outputs | Interfaces (ports) | Contracts |
| --- | --- | --- | --- | --- | --- |
| `shell.home` | `interfaces/pyqt/contributions/home_view.py` | Dashboard refresh, card click | Navigates to target contribution; dashboard rows | `usermanagement_service`, `documents_pool_api`, `training_api` | `DocumentTaskItem`, `ReviewActionItem`, `RecentDocumentItem`, training assignment readmodels |
| `documents.workflow` | `interfaces/pyqt/contributions/documents_workflow_view.py` | Filters, row select, action-bar clicks, wizard submits | Document state transitions, metadata/header updates, artifact opens | `usermanagement_service`, `documents_service`, `documents_pool_api`, `documents_workflow_api` | `DocumentVersionState`, `DocumentHeader`, `DocumentStatus`, `DocumentType`, `ControlClass`, `RejectionReason` |
| `documents.pool` | `interfaces/pyqt/contributions/documents_pool_view.py` | Refresh, search/select, read/open | Released documents list and read action | `usermanagement_service`, `documents_pool_api` | `ReleasedDocumentItem`, `DocumentStatus`, artifact DTOs |
| `signature.workspace` | `interfaces/pyqt/contributions/signature_view.py` | Input/signature file pickers, canvas dialog, sign trigger, profile select | Ad-hoc sign result, profile preview, audit conflict feedback | `signature_api`, `usermanagement_service`, optional `audit_logger` | `SignRequest`, `SignResult`, `SignaturePlacementInput`, `LabelLayoutInput`, `UserSignatureTemplate` |
| `training.workspace` | `interfaces/pyqt/contributions/training_placeholder.py` | Assignment reload, read confirm, quiz start/submit, admin actions | Training overview updates, quiz sessions/results, admin assignment sync | `training_api`, `training_admin_api`, `usermanagement_service` | `TrainingAssignment`, `TrainingOverviewItem`, `OpenTrainingAssignmentItem`, `QuizSession`, `QuizResult` |
| `platform.settings_admin` | `interfaces/pyqt/contributions/settings_view.py` | Profile edits, password change, settings save/load, signature config edits, license input | Persisted module settings, signature profile updates, license updates | `usermanagement_service`, `settings_service`, `signature_api`, `license_service`, `app_home` | `AuthenticatedUser`, signature template/layout DTOs, module settings payloads |
| `platform.audit_logs` | `interfaces/pyqt/contributions/audit_logs_view.py` | Filter inputs, export actions, admin checks | Filtered tables, CSV/PDF exports, check results | `registry_api`, `documents_service`, `documents_pool_api`, `license_service`, `settings_service`, `log_query_service`, `app_home` | audit/log query rows from `qm_platform/logging/log_query_service.py` |
| `platform.admin_debug` | `interfaces/pyqt/contributions/admin_debug_view.py` | Manual reload button | Raw technical payload panel for admin-only debugging | `app_home`, `license_service` | runtime/license payload dictionaries (technical only) |

## Navigation and access rules

- Navigation source: `interfaces/pyqt/registry/catalog.py`
- Role/license filtering: `interfaces/pyqt/shell/main_window.py`
- Stable dashboard routing is contribution-ID based via `navigate_to_contribution(...)`.
- `Admin/Debug` is only shown for admin users and can be persistently toggled from shell settings.

## Presenter/controller split (current pattern)

- Presenter modules:
  - `interfaces/pyqt/presenters/home_presenter.py`
  - `interfaces/pyqt/presenters/documents_workflow_presenter.py`
  - `interfaces/pyqt/presenters/training_presenter.py`
  - `interfaces/pyqt/presenters/settings_presenter.py`
- Contribution widgets own rendering and signal wiring.
- Presenters own formatting/routing-policy/action-visibility helpers.

## Shared widgets and dialogs

- Reusable UI blocks:
  - `interfaces/pyqt/widgets/action_bar.py`
  - `interfaces/pyqt/widgets/filter_bar.py`
  - `interfaces/pyqt/widgets/drawer_panel.py`
  - `interfaces/pyqt/widgets/entity_cards.py`
  - `interfaces/pyqt/widgets/debug_panel.py`
- Dialog/wizard contracts:
  - `interfaces/pyqt/widgets/document_create_wizard.py`
  - `interfaces/pyqt/widgets/workflow_start_wizard.py`
  - `interfaces/pyqt/widgets/reject_reason_dialog.py`
  - `interfaces/pyqt/widgets/signature_canvas_dialog.py`

## Notes

- Contribution IDs with `platform.*` are UI identity keys and intentionally independent from Python package naming.
- Business logic remains in `modules/*`; PyQt contributions must call provided ports and must not bypass service invariants.
