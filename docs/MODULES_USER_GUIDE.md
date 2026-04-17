# Modules User Guide

This guide explains how to use each module from an end-user perspective.

Security default note:
- Use strong, non-default credentials from first initialization.
- Any examples with simple passwords are for local dev/smoke only and must not be used in production.

For process/audit alignment details, see:
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
For implementation details, ports, and extension points, see:
- `docs/MODULES_DEVELOPER_GUIDE.md`
For project-level engineering and GUI integration rules, see:
- `docs/AGENTS_PROJECT.md`
- `docs/GUI_ARCHITECTURE_PROJECT.md`
- `docs/OPERATIONS_CANONICAL.md`

## usermanagement

### Purpose

Authenticate users, keep an active session, and manage user accounts.

Production note: QM-relevant deployments MUST follow the hardened seed and credential policy in `docs/MODULES_DEVELOPER_GUIDE.md` (usermanagement → “Production security standard”); repository defaults are for local development only.

### Typical workflows

- First-run init:
  - `python -m interfaces.cli.main init --non-interactive --admin-password "<your-password>"`
- Login:
  - `python -m interfaces.cli.main login --username admin --password "<your-password>"`
- Logout:
  - `python -m interfaces.cli.main logout`
- List users (QMB/Admin only):
  - `python -m interfaces.cli.main users list`
- Create user (QMB/Admin only):
  - `python -m interfaces.cli.main users create --username alice --password secret --role User`

### Frequent issues

- `BLOCKED: invalid credentials`:
  - Username/password mismatch.
- `BLOCKED: login required for users commands`:
  - Session is missing; login first.
- `BLOCKED: only QMB or ADMIN may execute users commands`:
  - Active user has insufficient role.

## documents

### Purpose

Manage document lifecycle from planning to archive with strict role and status checks.

### Typical workflows

- Create document version:
  - `python -m interfaces.cli.main documents create-version --document-id DOC-100 --version 1 --doc-type VA --control-class CONTROLLED --workflow-profile-id long_release`
- Update header metadata (QMB/Admin):
  - `python -m interfaces.cli.main documents header-set --document-id DOC-100 --department QC --site HQ`
- Assign workflow roles:
  - `python -m interfaces.cli.main documents assign-roles --document-id DOC-100 --version 1 --editors admin --reviewers user --approvers qmb`
- Start workflow:
  - `python -m interfaces.cli.main documents workflow-start --document-id DOC-100 --version 1`
- In der GUI (`Dokumentenlenkung`) bei `Bearbeitung annehmen`:
  - SOURCE_DOCX wird zuerst in SOURCE_PDF ueberfuehrt; ab dann ist SOURCE_PDF das aktive PDF-Asset.
  - Danach oeffnet sich der Signatur-Platzierungsdialog; ohne bestaetigte Platzierung wird der Schritt abgebrochen.
  - Aktionen (Vorbereitung, Platzierung, Abschluss) werden in der Audithistorie erfasst.
- Continue workflow (review/approval/archive) using role-appropriate accounts.
- Read central registry evidence:
  - `python -m interfaces.cli.main documents pool-get-register --document-id DOC-100`
- Read header metadata:
  - `python -m interfaces.cli.main documents header-get --document-id DOC-100`
- Read version metadata:
  - `python -m interfaces.cli.main documents metadata-get --document-id DOC-100 --version 1`
- Update version metadata:
  - `python -m interfaces.cli.main documents metadata-set --document-id DOC-100 --version 1 --title \"Updated title\" --custom-fields-json "{\"topic\":\"sterility\"}"`

### Metadata model quick note

- `document_id` ist die fachliche Dokumentenkennung (z. B. `VA-2024-001`) und bleibt über Versionen gleich.
- `doc_type` describes the fachliche Dokumentart (for filtering/reporting).
- `control_class` describes governance strictness.
- `workflow_profile_id` selects the concrete executable workflow within the chosen control class.
- `doc_type` and `control_class` are intentionally separate and both required for clear audit semantics.

### Signatur- und Artefaktregeln (GUI Dokumentenlenkung)

- `IN_PROGRESS -> IN_REVIEW`: Falls nur DOCX vorliegt, wird zuerst nach PDF konvertiert; signiert wird auf PDF.
- `IN_REVIEW -> IN_APPROVAL` und `IN_APPROVAL -> APPROVED`: Signatur arbeitet immer auf der zuletzt signierten PDF (`SIGNED_PDF`).
- Der Platzierungsdialog unterstuetzt Vorlagenliste + Vorlagenladen (Preset-Auswahl), damit wiederverwendbare Positionen direkt waehlbar sind.

### Frequent issues

- `BLOCKED: login required for documents commands`:
  - Login required for all document commands.
- `BLOCKED: only QMB or ADMIN may update document headers`:
  - Header writes are privileged operations.
- `BLOCKED: actor is not assigned as reviewer/approver`:
  - Current account is not in the assigned role set.
- `BLOCKED: profile control_class ... does not match document control_class ...`:
  - Chosen workflow profile does not fit selected governance class.
- `BLOCKED: custom fields must not override steering fields`:
  - `custom_fields_json` cannot contain lifecycle/role/registry steering keys.
- `BLOCKED: doc_type/control_class cannot be changed after first creation`:
  - Header steering fields are immutable once the document exists.
- `BLOCKED: validity dates can only be updated for APPROVED or ARCHIVED versions`:
  - `valid_until` / `next_review_at` are protected and cannot steer early workflow phases.
- Signature-required transition blocked:
  - Provide required sign parameters where transition requires signature.
- Signature-required GUI step blocked (`documents.workflow`):
  - For annual extension and required transitions, a callable signature backend is mandatory; if unavailable, the action is intentionally aborted.
- `Keine PDF-Datei fuer Signatur gefunden` / DOCX fallback errors:
  - Ensure a PDF artifact exists first; DOCX->PDF fallback requires Windows + `docx2pdf` and an available MS Word installation.

### Migration note for users

- Older entries may temporarily show `doc_type=OTHER` after migration.
- This means the exact fachliche type was unknown historically and should be refined during data cleanup.
- Governance behavior remains stable through `control_class` + `workflow_profile_id`.

## signature

### Purpose

Place visible signatures on PDF files (visual mode, dry-run or output).

### Typical workflows

- Quick dry-run:
  - `python -m interfaces.cli.main sign visual --input in.pdf --signature-png sig.png --page 0 --x 100 --y 100 --width 120 --signer-user admin --password "<strong-password>" --dry-run`
- Import signature asset (PNG/GIF):
  - `python -m interfaces.cli.main sign import-asset --owner-user-id admin --input sig.gif`
- Create reusable signature template:
  - `python -m interfaces.cli.main sign template-create --owner-user-id admin --name std --asset-id <asset_id> --x 120 --y 120 --width 120`
- Sign via template:
  - `python -m interfaces.cli.main sign template-sign --template-id <template_id> --input in.pdf --signer-user admin --password "<strong-password>"`

### Frequent issues

- `BLOCKED: password required`:
  - Signature policy requires password and none was passed.
- Input/output path errors:
  - Verify PDF and PNG file paths.
- Template/asset ownership mismatch:
  - Ensure template creator and asset owner use the same user principal.

## training

### Purpose

Assign mandatory document reading, collect read confirmations, run quizzes, and track training status per user/document version.

### Typical workflows

- Admin/QMB: create category and map documents/users:
  - `python -m interfaces.cli.main training admin-category-create --category-id SOP_CORE --name "Core SOPs"`
  - `python -m interfaces.cli.main training admin-category-assign-document --category-id SOP_CORE --document-id DOC-100`
  - `python -m interfaces.cli.main training admin-category-assign-user --category-id SOP_CORE --user-id user`
- Admin/QMB: sync assignments from approved docs:
  - `python -m interfaces.cli.main training admin-sync`
- User: list open training inbox items:
  - `python -m interfaces.cli.main training list-required`
- User: confirm released-document read receipt:
  - `python -m interfaces.cli.main training confirm-read --document-id DOC-100 --version 1`
- Admin/QMB: import quiz JSON for document version:
  - `python -m interfaces.cli.main training admin-quiz-import --document-id DOC-100 --version 1 --input quiz_doc100_v1.json`
- User: run quiz:
  - `python -m interfaces.cli.main training quiz-start --document-id DOC-100 --version 1`
  - `python -m interfaces.cli.main training quiz-answer --session-id <session_id> --answers-json "[0,2,1]"`
- User: submit comment:
  - `python -m interfaces.cli.main training comment-add --document-id DOC-100 --version 1 --comment "Abschnitt 4 bitte präzisieren"`

### Frequent issues

- `BLOCKED: no active assignment for this document version`:
  - Assignment sync was not run or user/category mapping is missing.
- `BLOCKED: document version is not approved`:
  - Read confirmations are only accepted for released (`APPROVED`) versions.
- `BLOCKED: quiz set not found for document version`:
  - Admin quiz import for this document/version is missing.
- Superseded version behavior:
  - Older active assignments become `SUPERSEDED`; only latest approved version remains active requirement.

## settings/ui

### Purpose

Central settings read/write and UI-based orchestration of module features.

### Typical workflows

- Check runtime readiness:
  - `python -m interfaces.cli.main doctor`
- List modules with settings:
  - `python -m interfaces.cli.main settings list-modules`
- Read module settings:
  - `python -m interfaces.cli.main settings get --module documents`
- Write module settings (QMB/Admin):
  - `python -m interfaces.cli.main settings set --module signature --values-json "{\"require_password\": true, \"default_mode\": \"visual\"}"`
- Start UI:
  - `python -m interfaces.gui.main`

### Frequent issues

- `BLOCKED: only QMB or ADMIN may set settings`:
  - Active user lacks rights to persist settings.
- Network path executable blocked (Windows):
  - If running EXE from a network share fails, copy EXE to a local path first.
