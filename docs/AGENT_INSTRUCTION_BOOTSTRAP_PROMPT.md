# Agent Instruction Bootstrap Prompt

Use this prompt when onboarding Codex or Cursor to a repository that does not yet have
consolidated agent instructions. The prompt is **generic**; replace placeholders with facts
discovered in the target repo.

## How to use

1. Open a new agent session in the target repository.
2. Paste the prompt below (unchanged placeholders are fine — the agent should discover values).
3. Let the agent inspect the repo first, then produce short instruction files.
4. Review the generated `AGENTS.md` and optional `.cursor/rules/*.mdc` for conflicts with existing docs.

## Copyable bootstrap prompt

```text
You are setting up agent instructions for this repository. Do not change product behavior or
business logic in this task. Your deliverable is concise, non-contradictory guidance for future
agents.

## Phase 1 — Discover before writing

Inspect the repository and record facts (do not guess):

1. Repository layout: top-level directories, where business logic lives, where platform/runtime
   infrastructure lives, where UI/CLI/backend entrypoints live.
2. Canonical documentation: README, CONTRIBUTING, any docs index or architecture canon. Note
   document priority if one exists (P0/P1/P2 or equivalent).
3. Entrypoints: list every `main.py`, `__main__.py`, and documented launch command. Distinguish
   production entrypoints from scripts/tools.
4. Public API surfaces: module `api.py` files, backend public API, CLI command/parsers layout.
5. UI registries (if applicable): navigation catalogs, contribution registries, shared action bars,
   presenter layers, and where duplicate buttons would be a risk.
6. Build and test commands: Python version, venv path, pytest invocation, smoke/CI gates, packaging
   if documented.
7. Existing agent files: root `AGENTS.md`, `.cursor/rules/*`, `AGENTS.md` in subtrees, and any
   overlapping rules in CONTRIBUTING or dev guides.

Stop and ask if two docs disagree on boundaries, entrypoints, or verification commands.

## Phase 2 — Write short instruction files

### Primary Codex artifact (required)

Create or update **repository-root `AGENTS.md`** only. It must be short and operational:

- Mandatory search-before-create guardrails:
  - search existing entrypoints, public APIs, CLI commands, UI actions/registries before adding new ones
  - extend existing owners; do not add parallel similarly named buttons, menus, flows, or entrypoints
  - no new public surfaces, wrappers, `*_helper.py`, or parallel paths without explicit scope
  - stop and ask on unclear overlap; do not change behavior silently
- One-paragraph architecture essentials (layer ownership only; no long tutorials)
- Environment essentials (OS/shell, language version, test runner, venv if present)
- Links to canonical docs — do not duplicate long verification matrices here

Rules for `AGENTS.md`:

- Root `AGENTS.md` is the **project-wide** Codex entry point.
- Optional nested `AGENTS.md` files are allowed **only** for local subtrees with genuinely different rules.
- Do **not** create `.cursor/AGENTS.md` as a project-wide Codex substitute.

### Cursor-specific workflow (optional, only if `.cursor/` is used)

Add **at most a few** thematic `.cursor/rules/*.mdc` files. Suggested topics:

- step-by-step workflow (plan → one step → verify → report)
- per-layer verification command matrix
- architecture boundary reminders that are not already in root `AGENTS.md`

Cursor rules must **not** duplicate paragraphs from root `AGENTS.md`. Cross-link instead.

### Do not

- Rewrite historical/roadmap docs unless they actively mislead agents (wrong paths, wrong runners).
- Add lint/typecheck/toolchain steps that the repo does not already use.
- Combine multiple roadmap work packages into one implementation scope.

## Phase 3 — Optional consistency gates (if the repo uses pytest)

If appropriate after discovery, propose or add **minimal** automated gates, such as:

- allowed product entrypoint inventory under `<UI_ROOT>/` and `<BACKEND_ROOT>/`
- unique IDs/titles in UI navigation catalogs
- registration of top-level UI contributions in catalog/registry files
- no duplicate labels for centrally managed workflow action bars
- boundary scans for legacy import paths in active directories (`<PLATFORM_ROOT>/`, `<BACKEND_ROOT>/`, etc.)

Keep gates narrow and fix false positives rather than weakening boundary intent.

## Phase 4 — Final conflict check

Before finishing, verify:

- [ ] Exactly one source of truth for workflow steps and verification commands
- [ ] No contradiction between `AGENTS.md`, `.cursor/rules/*`, and CONTRIBUTING
- [ ] Documented entrypoints match discovered files
- [ ] UI reuse rule present: one user intent → one existing action/owner
- [ ] Canonical doc index (if any) references active steering docs without overriding architecture P0

Deliver a short summary listing files created/updated and any unresolved doc conflicts.
```

## Placeholder map (fill from discovery)

| Placeholder | Meaning |
| --- | --- |
| `<UI_ROOT>` | Primary UI package (e.g. `interfaces/pyqt/`) |
| `<BACKEND_ROOT>` | Backend transport host (e.g. `src/backend/`) |
| `<PLATFORM_ROOT>` | Runtime/platform infrastructure (e.g. `qm_platform/`) |

## QMToolV7 reference outcome

This repository already applied the bootstrap outcome:

- Root `AGENTS.md` — guardrails + architecture essentials
- `.cursor/rules/00-agent-workflow.mdc` — workflow and verification matrix
- `tests/interfaces/test_architecture_gates.py` — entrypoint, catalog, and UI action gates
- `.github/workflows/ci-gates.yml` — selected gates in CI

Use this file when bootstrapping **other** repositories; do not treat the QMTool paths above as
placeholders in the copyable prompt.
