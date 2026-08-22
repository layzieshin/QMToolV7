# AGENTS.md

Entry point for AI-assisted and human work in QMToolV7. For full engineering rules, use the canonical docs linked below.

## Agent guardrails (mandatory)

Before creating anything new, search the repo for an existing owner:

- Entrypoints: `README.md`, `CONTRIBUTING.md`, `interfaces/cli/main.py`, `src/backend/`, future `webclient/`
- Public APIs: `modules/<name>/api.py`, `src/backend/api.py`
- HTTP boundary (target): `/api/v1`
- CLI commands: `interfaces/cli/commands/`, `interfaces/cli/parsers/`
- Legacy/reference GUI only (frozen): `interfaces/pyqt/` — **do not add new product UI here**

## Change discipline

Before editing any non-trivial implementation, identify the existing behavior owner; trace the
current path from interface through public API or port and service to persistence or external
effect; locate protecting tests and similar implementations; and name the smallest required file set.
If the owner or overlap is unclear, stop and ask.

- Extend the existing owner. Unless the task explicitly requires it, do not add parallel implementations,
  duplicate public APIs, user actions, services, or persistence paths; compatibility layers, fallback
  implementations, temporary alternate paths, generic wrappers or `*_helper.py` files; entrypoints; or public surfaces.
- Do not create a module for behavior owned by an existing module, or a public API when the existing
  API can responsibly be extended. Do not bypass module APIs by importing services, repositories,
  wiring, storage, internal errors, internal contracts, or other implementation details.
- Do not perform unrelated refactoring, hide failures with broad exception handling, or silently
  change behavior. Update tests and docs with behavior changes.
- TODOs, placeholders, mocks, disabled tests, skipped implementation, and unrelated pre-existing
  failures are not completed work. Report unrelated failures separately; do not silently fix or hide them.
- One normal task = one hotspot or one use case; do not combine roadmap packages. An explicitly
  authorized `/execute-work-package` may contain several separately bounded, serially verified
  checkpoints under its owning package contract; it never permits blended checkpoint diffs or
  unrelated roadmap work.

For completed implementation work, report the resulting execution path, changed files and their
responsibilities, exact verification commands and results, remaining limitations, and whether any
entrypoint, public surface, service, wrapper, helper, user action, or persistence path was introduced.

## Workflow and verification

The step-by-step workflow and the per-layer verification commands are defined once in
[`.cursor/rules/00-agent-workflow.mdc`](.cursor/rules/00-agent-workflow.mdc) (loaded automatically by Cursor).
Branch, commit, push, and pull-request behavior is defined once in
[`.cursor/rules/01-git-workflow.mdc`](.cursor/rules/01-git-workflow.mdc) (also auto-loaded).
Do not duplicate either rule set here. In short: work step by step, verify after each step, do not
proceed on failure, and keep diffs small. An explicitly commissioned implementation includes its
local feature-branch commit after green gates and exact-path staging unless the user opts out.
Push, pull request, merge, and branch deletion remain separately user-gated. Creating a local
feature branch for an explicitly commissioned change remains allowed and expected when required by
the Git workflow rule.

For an approved larger package, the user may explicitly invoke `/execute-work-package <WP-ID>`.
That Cursor-native workflow, its role separation, bounded review loops, local runtime state, and
HUMAN_GATEs are documented in
[`docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md`](docs/CURSOR_AUTONOMOUS_WORK_PACKAGE_SYSTEM.md)
and supplemented by `.cursor/rules/02-autonomous-work-package.mdc`.

## Environment (this repo)

- OS/shell: Windows / PowerShell — chain commands with `;`, not `&&`.
- Python: `3.14.x` (`pyproject.toml` `requires-python = ">=3.14,<3.15"`).
- Use the workspace venv explicitly: `.\.venv\Scripts\python.exe`.
- Tests: `.\.venv\Scripts\python.exe -m pytest`.
  Pytest uses `build/pytest-basetemp` by default via `pytest.ini`; a `WinError 5`
  under global Windows `%TEMP%` is an environment problem, not a product failure.
- No configured linter/typechecker (no ruff/flake8/mypy/pre-commit) — do not invent lint/typecheck steps.
- Do not invent npm/Vite commands until WEB00 lands them in-repo.

## Destructive PostgreSQL live tests (Slot 2)

When a task requires `@pytest.mark.postgres` live tests, follow this section end-to-end.
Do **not** run bare `pytest -m postgres` — the runner is mandatory.

### Stale checkout and Git worktrees

Agents read files from the **opened workspace root only** — not from another clone path on disk.

If this Slot 2 section or `scripts/provision_j04_destructive_postgres.py` is missing, the checkout
is stale (common on long-lived feature branches or secondary worktrees such as `QMToolV7-main-clean`):

```powershell
git fetch origin
git merge origin/main
```

If `git checkout main` fails with **already used by worktree**, `main` is checked out in another
folder (for example `I:\Projekte\QMToolV7`). Either open that workspace, or stay on the current
branch and merge `origin/main` as above.

`.env` is **gitignored and per clone** — each workspace needs its own three `QMTOOL_PG_TEST_*` keys.
Re-running the provision script in one clone **rotates the test-admin password**; other clones need
a matching DSN update or their own re-provision before preflight will pass.

### Two slots (do not mix)

| Slot | Variables | Purpose |
| --- | --- | --- |
| **1 – Runtime/Lab** | `QMTOOL_PG_HOST/PORT/DATABASE/USER/PASSWORD` | Lab `192.168.0.4:5432/qmtool_test` — **never** for destructive tests |
| **2 – Destructive (J04)** | `QMTOOL_PG_TEST_*` | Isolated disposable cluster on a separate target |

Also documented in [`.env.example`](.env.example) and [`CONTRIBUTING.md`](CONTRIBUTING.md) (Lab section).

### Agent checklist (Slot 2)

1. Open gitignored `.env` in the repo root (template: [`.env.example`](.env.example)).
2. Confirm all three keys exist:
   - `QMTOOL_PG_TEST_ADMIN_DSN`
   - `QMTOOL_PG_TEST_EXPECTED_DATABASE` (`qmtool_j04_destructive_test`)
   - `QMTOOL_PG_TEST_EXPECTED_MAJOR` (local disposable cluster: `18`; CI: `16`)
3. If any key is missing → **provision once** (see below), then re-check.
4. Run tests **only** via `scripts/run_postgres_live_tests.py`.
5. If preflight prints `preflight: ...` and exits **2**, Slot 2 is not configured — go back to step 2.

**Do not store in `.env`:**
- `QMTOOL_PG_TEST_RESET` — the runner injects this only into the pytest child process
- Do not change Slot 1 lab keys for destructive work

Example Slot 2 block (password is local; never commit):

```text
QMTOOL_PG_TEST_ADMIN_DSN=postgresql://qmtool_j04_test_admin:<password>@127.0.0.1:5432/qmtool_j04_destructive_test
QMTOOL_PG_TEST_EXPECTED_DATABASE=qmtool_j04_destructive_test
QMTOOL_PG_TEST_EXPECTED_MAJOR=18
```

Guard checks in `tests/postgres_destructive_guard.py` (read-only preflight):
- Database name exactly `qmtool_j04_destructive_test`
- Cluster marker `j04_m0_destructive_pg16` (name is historical; works on PG18)
- PostgreSQL major ≥ 16 and exactly `QMTOOL_PG_TEST_EXPECTED_MAJOR`
- Target is not the runtime/lab endpoint (`192.168.0.4` / `qmtool_test`)
- Admin role has `CREATEROLE` + `CREATEDB`

### Provision Slot 2 (when keys are missing)

Fresh clone, branch cleanup, or empty `.env` — run once. Requires local PostgreSQL 16+ (here PG 18 on `127.0.0.1:5432`):

```powershell
.\.venv\Scripts\python.exe scripts/provision_j04_destructive_postgres.py --local-trust-bootstrap
```

Alternative when a superuser DSN is already known:

```powershell
$env:J04_PG_PROVISION_SUPERUSER_DSN = "postgresql://postgres:<password>@127.0.0.1:5432/postgres"
.\.venv\Scripts\python.exe scripts/provision_j04_destructive_postgres.py
```

Creates test admin, database, marker; appends the three Slot 2 keys to `.env`. Never writes `QMTOOL_PG_TEST_RESET`.

### Run destructive tests (canonical)

**Never** `pytest -m postgres` directly. Always:

```powershell
# Default live suite (runner default targets)
.\.venv\Scripts\python.exe scripts/run_postgres_live_tests.py

# Targeted files or single test
.\.venv\Scripts\python.exe scripts/run_postgres_live_tests.py `
  tests/platform/test_platform_blob_contract_live.py `
  tests/platform/test_postgres_schema_live.py

.\.venv\Scripts\python.exe scripts/run_postgres_live_tests.py `
  tests/modules/usermanagement/test_postgres_schema_live.py::test_provision_is_idempotent
```

**Runner flow** (`scripts/run_postgres_live_tests.py`):
1. Loads `.env` (Slot 2 DSN)
2. Read-only preflight (`preflight_isolated_postgres_target()`)
3. On success: starts pytest child with `QMTOOL_PG_TEST_RESET=I_UNDERSTAND_THIS_IS_DESTRUCTIVE` and `QMTOOL_PG_REQUIRED=1`
4. Cleans up restore databases (`qmtool_j04_restore_*`)

### J04 full realprocess gate (separate)

Do not invoke `tests/acceptance/test_j04_m0_realprocess.py` as a loose pytest target.

```powershell
$env:QMTOOL_J04_FINAL_ACCEPTANCE = "I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN"
.\.venv\Scripts\python.exe scripts/run_postgres_live_tests.py `
  --j04-final-acceptance `
  --basetemp build/j04-m0-closure/cp08-pytest-<stamp>
```

`--basetemp` must be a **new** path (must not already exist).

### Optional Compose sketch (not required)

`tests/postgres/compose.yaml` + `manage.ps1` — PG16 on `127.0.0.1:55432`. Local Windows setup here uses **PG18 on port 5432** instead. See [`tests/postgres/README.md`](tests/postgres/README.md) for operator details.

## Architecture essentials

- Business logic lives in `modules/*` services. `qm_platform/*` contains platform, runtime, logging,
  licensing, settings, events and integration infrastructure, but no fachliche QM business logic.
  Business logic never belongs in webclient, legacy PyQt widgets, CLI parsers, or backend transport code.
- External Python access to a module goes through `modules/<name>/api.py`; `contracts.py`,
  ports, capabilities, and events are internal/runtime integration mechanisms unless exposed by `api.py`.
- State-changing operations from outside a module must go through explicit public API contracts;
  internal services remain implementation details.
- Enforce auth/roles in the **service layer**, not in UI or CLI parsers.
- Ports/capabilities are wired via the container; register modules in `qm_platform/runtime/bootstrap.py`.
- `src/backend/*` is a transport host, not a fachliches Modul.
- Public backend imports go through `src/backend/api.py`.
- Backend code must not contain business logic and must not directly access fachliche repositories,
  storage, SQL, or module internals.
- Backend code may call fachliche use cases only through public module APIs.
- **New feature order:** service + `api.py` + HTTP `/api/v1` contract + tests, then `webclient/` adapter
  (after WEB00). CLI remains an operator/test adapter.
- **New productive persistence:** PostgreSQL-only; no SQLite product fallback.
- **GUI source of truth for new UI:** `webclient/*` (`docs/GUI_SOURCE_OF_TRUTH.md`). PyQt/Tk are
  frozen legacy/reference — no new product UI work there.
- Until WEB00, no productive web end-user client exists; do not claim unimplemented web features.

## Master orchestration roadmap

- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` is the active Web/PostgreSQL transition steering document.
- `docs/MASTER_ORCHESTRATION_ROADMAP.md` remains the broader roadmap companion; AP-029 owns the
  transition checkpoint order after J04-M0 acceptance.
- Agents must not start roadmap work packages unless explicitly asked.
- Do not combine multiple roadmap checkpoints in one implementation diff or commit. An explicitly
  authorized AP-029 macro may orchestrate several checkpoints serially only when every checkpoint
  keeps its own allowlist, evidence, reviewer verdict and local commit and the macro stops on the
  first unresolved checkpoint.
- ADR packages are documentation/decision packages only unless explicitly approved otherwise.

## Backend/multiuser migration

- Historical desktop paths may remain runnable as legacy reference during transition.
- Migration is use-case based and must not run half locally and half through backend.
- Productive target runtime is PostgreSQL-only (AP-029); SQLite is limited to inventory, import, and tests.
- Multiple clients must never directly share the same SQLite file.

## Build and packaging

- Ist production build (legacy desktop packaging): `.\.venv\Scripts\python.exe packaging/build_onedir.py`
  (onedir + ZIP). The legacy onefile script is deprecated.
- Target on-prem Windows service / HTTPS deployment is defined by OPS00 — not invent commands early.
- DOCX workflow requires Microsoft Word (COM) on Windows; import PDF directly otherwise.
- Native deps loaded dynamically (e.g. `fitz`/PyMuPDF) must stay bundled; the build runs `packaging/verify_bundle_imports.py` as a gate.

## Canonical project rules

When documents disagree, P0 overrules P1 and P2 (`docs/DOCS_CANONICAL_INDEX.md`).

- `CONTRIBUTING.md` — developer entry point (setup + documentation map)
- `docs/MODULE_INTEGRATION_POLICY.md` — module onboarding, ports, licensing, auth, testing minimums
- `docs/MODULES_DEVELOPER_GUIDE.md` — per-module ports/settings/events/contracts (Ist marked)
- `docs/TEST_SMOKE_GATES.md` — smoke gates and verification matrix
- `docs/AGENTS_PROJECT.md` — engineering rules and boundaries (P2; P0 wins on conflict)
- `docs/DEVGUIDE.md` — developer reference (P2; P0 wins on conflict)
