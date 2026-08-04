# Canonical Operations Entry

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

This is the single operational starting point for daily work, release checks, and incident handling.

## Mandatory Reading Order

1. `docs/DOCS_CANONICAL_INDEX.md` (priority and conflict resolution)
2. `docs/MODULE_INTEGRATION_POLICY.md` (module onboarding and integration rules)
3. `docs/GUI_SOURCE_OF_TRUTH.md` (active GUI source and constraints)
4. `docs/MODULES_DEVELOPER_GUIDE.md` (module ports/settings/events/contracts)
5. `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md` (normative domain invariants and registry contract)
6. `docs/MODULES_USER_GUIDE.md` (operational CLI usage and role-facing flows)

## Daily Start Flow

1. Run health and runtime checks:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database status`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main health`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor --strict` for production-hardening checks (`seed_mode=hardened` and hashed credential store).
2. Confirm login/session behavior with hardened credentials:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main login --username admin --password "<strong-password>"`
3. Verify required module settings visibility:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main settings list-modules`
4. For release/migration windows, execute migration gates from `docs/DEVGUIDE.md` and `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`.

## Release Gate Checklist (Blocking)

- Database status reports all seven databases as `current` with integrity `ok`.
- `scripts/database_migration_gate.py` is green and its JSON evidence is attached.
- Pre/post migration data-quality report attached.
- No increase in `doc_type=OTHER`.
- Invalid `doc_type/control_class/workflow_profile_id` combinations are `0`.
- Regression suite relevant to changed modules is green.
- Release owner records explicit Go/No-Go decision.
- CI reference: `.github/workflows/ci-gates.yml` enforces regression + migration gate script in automated runs.
- Consolidated local gate command:
  - `.\.venv\Scripts\python.exe scripts/golive_gate.py --output "<evidence-dir>/golive-gate.json"`
  - optional DB-backed checks: add `--documents-db-path "<documents.db>" --registry-db-path "<registry.db>" --baseline-other-count <n>`.

## Database Migration Window

1. Inspect without changing data:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database status`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database migrate --dry-run`
2. Run the controlled forward migration:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database migrate`
3. Verify:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database status`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor --strict`
4. List recovery points:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database backups`
5. Restore only under an explicit incident/release decision:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database restore --backup-id "<id>"`

The full contract and mandatory schema-change package are defined in
`docs/DATABASE_EVOLUTION_POLICY.md`.

## Registry Projection Recovery Entry

When registry projection drift is suspected:

1. Follow `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md` section:
   - `Registry projection recovery contract`
2. Capture incident ticket and evidence before/after reconciliation.
3. Re-run verification checks and attach results to release/incident record.
4. Optional drill automation command:
   - `.\.venv\Scripts\python.exe scripts/registry_recovery_drill.py --documents-db-path "<documents.db>" --registry-db-path "<registry.db>" --evidence-dir "<evidence-dir>" --rebuilt-registry-db-path "<rebuilt-registry.db>"`

## Security Defaults

- Use `init` with explicit strong password:
  - `.\.venv\Scripts\python.exe -m interfaces.cli.main init --non-interactive --admin-password "<set-strong-password>"`
- Keep hardened seed mode for production operations.
- Prefer `doctor --strict` (or set `QMTOOL_DOCTOR_STRICT=1`) in release/operational validation runs.
- Treat simple password examples in docs as local dev/smoke only.
- For production-like license validation, run with `QMTOOL_LICENSE_MODE=strict` to disable implicit dev license autogeneration.
- When `QMTOOL_RUNTIME_PROFILE=production`, startup enforces `usermanagement.seed_mode=hardened`.

## Settings Governance

Apply governance classes from `docs/DEVGUIDE.md`:

- `operational`
- `development`
- `governance_critical`

Do not apply ad-hoc runtime changes for `governance_critical` settings without release control.
