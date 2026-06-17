# AGENTS.md

Entry point for AI-assisted and human work in QMToolV7. For full engineering rules, use the canonical docs linked below.

## Workflow and verification

The step-by-step workflow and the per-layer verification commands are defined once in
[`.cursor/rules/00-agent-workflow.mdc`](.cursor/rules/00-agent-workflow.mdc) (loaded automatically by Cursor).
Do not duplicate them here. In short: work step by step, verify after each step, do not proceed on failure, keep diffs small.

## Environment (this repo)

- OS/shell: Windows / PowerShell — chain commands with `;`, not `&&`.
- Python: `3.14.x` (`pyproject.toml` `requires-python = ">=3.14,<3.15"`).
- Tests: `$env:PYTHONPATH="."; python -m pytest`.
- No configured linter/typechecker (no ruff/flake8/mypy/pre-commit) — do not invent lint/typecheck steps.

## Architecture essentials

- Business logic lives in `modules/*` services and `qm_platform/*`, never in PyQt widgets or CLI parsers.
- Cross-module access only via a module's public boundary: `modules/<name>/api.py` + `contracts.py`.
- Enforce auth/roles in the **service layer**, not in widgets or CLI parsers.
- Ports/capabilities are wired via the container; register modules in `qm_platform/runtime/bootstrap.py`.
- Verify features CLI-first, then GUI.
- GUI source of truth is `interfaces/pyqt/*` only (`docs/GUI_SOURCE_OF_TRUTH.md`); `interfaces/gui/*` is legacy/test.

## Build and packaging

- Production build: `python packaging/build_onedir.py` (onedir + ZIP). The legacy onefile script is deprecated.
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
