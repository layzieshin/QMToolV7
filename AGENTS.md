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
- One task = one hotspot or one use case; do not combine roadmap packages.

For completed implementation work, report the resulting execution path, changed files and their
responsibilities, exact verification commands and results, remaining limitations, and whether any
entrypoint, public surface, service, wrapper, helper, user action, or persistence path was introduced.

## Workflow and verification

The step-by-step workflow and the per-layer verification commands are defined once in
[`.cursor/rules/00-agent-workflow.mdc`](.cursor/rules/00-agent-workflow.mdc) (loaded automatically by Cursor).
Branch, commit, push, and pull-request behavior is defined once in
[`.cursor/rules/01-git-workflow.mdc`](.cursor/rules/01-git-workflow.mdc) (also auto-loaded).
Do not duplicate either rule set here. In short: work step by step, verify after each step, do not
proceed on failure, keep diffs small, and keep commit, push, pull request, and branch deletion
user-gated. Creating a local feature branch for an explicitly commissioned change remains allowed
and expected when required by the Git workflow rule.

## Environment (this repo)

- OS/shell: Windows / PowerShell — chain commands with `;`, not `&&`.
- Python: `3.14.x` (`pyproject.toml` `requires-python = ">=3.14,<3.15"`).
- Use the workspace venv explicitly: `.\.venv\Scripts\python.exe`.
- Tests: `.\.venv\Scripts\python.exe -m pytest`.
  Pytest uses `build/pytest-basetemp` by default via `pytest.ini`; a `WinError 5`
  under global Windows `%TEMP%` is an environment problem, not a product failure.
- No configured linter/typechecker (no ruff/flake8/mypy/pre-commit) — do not invent lint/typecheck steps.
- Do not invent npm/Vite commands until WEB00 lands them in-repo.

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
