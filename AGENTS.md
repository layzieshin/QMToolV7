# AGENTS.md

Entry point for AI-assisted and human work in QMToolV7. For full engineering rules, use the canonical docs linked below.

## Agent guardrails (mandatory)

Before creating anything new, search the repo for an existing owner:

- Entrypoints: `README.md`, `CONTRIBUTING.md`, `interfaces/cli/main.py`, `interfaces/pyqt/`, `src/backend/`
- Public APIs: `modules/<name>/api.py`, `src/backend/api.py`
- GUI actions: `interfaces/pyqt/registry/catalog.py`, `interfaces/pyqt/contributions/`, `interfaces/pyqt/sections/`, `interfaces/pyqt/presenters/`
- CLI commands: `interfaces/cli/commands/`, `interfaces/cli/parsers/`

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
Do not duplicate them here. In short: work step by step, verify after each step, do not proceed on failure, keep diffs small.

## Environment (this repo)

- OS/shell: Windows / PowerShell — chain commands with `;`, not `&&`.
- Python: `3.14.x` (`pyproject.toml` `requires-python = ">=3.14,<3.15"`).
- Use the workspace venv explicitly: `.\.venv\Scripts\python.exe`.
- Tests: `.\.venv\Scripts\python.exe -m pytest`.
- No configured linter/typechecker (no ruff/flake8/mypy/pre-commit) — do not invent lint/typecheck steps.

## Architecture essentials

- Business logic lives in `modules/*` services. `qm_platform/*` contains platform, runtime, logging,
  licensing, settings, events and integration infrastructure, but no fachliche QM business logic.
  Business logic never belongs in PyQt widgets, CLI parsers, or backend transport code.
- External Python access to a module goes through `modules/<name>/api.py`; `contracts.py`,
  ports, capabilities, and events are internal/runtime integration mechanisms unless exposed by `api.py`.
- State-changing operations from outside a module must go through explicit public API contracts;
  internal services remain implementation details.
- Enforce auth/roles in the **service layer**, not in widgets or CLI parsers.
- Ports/capabilities are wired via the container; register modules in `qm_platform/runtime/bootstrap.py`.
- `src/backend/*` is a transport host, not a fachliches Modul.
- Public backend imports go through `src/backend/api.py`.
- Backend code must not contain business logic and must not directly access fachliche repositories,
  storage, SQL, or module internals.
- Backend code may call fachliche use cases only through public module APIs.
- Verify features CLI-first, then GUI.
- GUI source of truth is `interfaces/pyqt/*` only (`docs/GUI_SOURCE_OF_TRUTH.md`); `interfaces/gui/*` is legacy/test.

## Master orchestration roadmap

- `docs/MASTER_ORCHESTRATION_ROADMAP.md` is the active roadmap and work-package steering document.
- Agents must treat it as the planning reference for backend/multiuser migration, MVP prioritization,
  and work-package order.
- Do not start roadmap work packages unless explicitly asked.
- Do not combine multiple roadmap packages in one task.
- ADR packages are documentation/decision packages only unless explicitly approved otherwise.

## Backend/multiuser migration

- The existing desktop app must remain runnable during migration.
- Migration is use-case based.
- A use case must never run half locally and half through backend.
- For already backend-migrated use cases, SQLite may only be opened by the backend process.
- Not-yet-migrated legacy use cases may remain local until their migration.
- Multiple clients must never directly share the same SQLite file.

## Build and packaging

- Production build: `.\.venv\Scripts\python.exe packaging/build_onedir.py` (onedir + ZIP). The legacy onefile script is deprecated.
- DOCX workflow requires Microsoft Word (COM) on Windows; import PDF directly otherwise.
- Native deps loaded dynamically (e.g. `fitz`/PyMuPDF) must stay bundled; the build runs `packaging/verify_bundle_imports.py` as a gate.

## Canonical project rules

When documents disagree, P0 overrules P1 and P2 (`docs/DOCS_CANONICAL_INDEX.md`).

- `CONTRIBUTING.md` — developer entry point (setup + documentation map)
- `docs/MODULE_INTEGRATION_POLICY.md` — module onboarding, ports, licensing, auth, testing minimums
- `docs/MODULES_DEVELOPER_GUIDE.md` — per-module ports/settings/events/contracts
- `docs/TEST_SMOKE_GATES.md` — smoke gates and verification matrix
- `docs/AGENTS_PROJECT.md` — engineering rules and boundaries (P2; P0 wins on conflict)
- `docs/DEVGUIDE.md` — developer reference (P2; P0 wins on conflict)
