# AGENTS Project Rules

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

This document defines repository-specific engineering rules for AI-assisted and manual implementation.
It is aligned with the active runtime (`modules/*`, `qm_platform/*`, `interfaces/*`) and the CLI-first policy.

Related contracts:
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/OPERATIONS_CANONICAL.md`

## Core Objectives

- Preserve architecture stability and deterministic runtime behavior.
- Keep module boundaries explicit and contract-driven.
- Verify features CLI-first before GUI integration.
- Keep GUI as adapter/host layer, never as business source of truth.
- Maintain packaging safety for Windows EXE distribution.

## Non-Negotiable Rules

### Active Runtime Only

Only extend and use:
- `modules/*`
- `qm_platform/*`
- `interfaces/*`

Do not reintroduce removed legacy runtime paths.

### Business Logic Placement

Business logic belongs in module services and platform services.
Business logic must not be implemented in:
- GUI view/widget callbacks
- CLI command parsing/printing code
- ad-hoc helper scripts outside module/service boundaries

### Adapter Discipline (CLI/GUI)

CLI and GUI must:
- collect input
- call service/API ports
- render outputs/errors

CLI/GUI must not bypass service invariants or open alternate write paths.

### Contract-Driven Modules

Each module should expose:
- `contracts.py`
- `service.py`
- `module.py`
- optional `api.py`

State-changing operations must end in the authoritative module service.

### Public Surface Policy (Normative)

- The only supported external integration surface of a module is its declared `provided_ports`.
- Interfaces and other modules must call module behavior through these declared ports only.
- Importing non-contract internals across module boundaries is forbidden, even if technically possible.
- If a module exposes multiple provided ports, each port must have a clear scope:
  - authoritative write kernel
  - specialized read view
  - specialized workflow/operation view
- Port scope must be documented in `docs/MODULES_DEVELOPER_GUIDE.md`.

### Contract Versioning Policy

- Additive contract changes are allowed if existing callers remain valid.
- Breaking changes to contract dataclasses or port behavior require:
  - version bump in module contract,
  - migration notes in docs,
  - updated CLI/e2e tests covering old/new behavior impact.
- No silent semantic changes for existing port methods.

### Cross-Module Access

Allowed:
- module -> platform
- interface -> module API/service ports
- module -> other module only via declared ports/APIs

Avoid:
- importing internals of other modules
- cyclic dependencies
- hidden global state

Boundary enforcement minimum:
- keep architecture boundary tests active and updated for new modules/import paths,
- reject PRs that introduce cross-module internal imports.

### Settings and Events

- Module settings must be declared via settings contributions.
- Events must be versioned, structured, compact, and non-sensitive.
- Events support integration and traceability, but do not replace service state ownership.

## Testing Policy

For relevant changes, update or validate:
- qm_platform/runtime tests (ports, capabilities, startup guards, licensing if applicable)
- module tests (invariants, auth/status matrix, persistence behavior)
- CLI e2e tests (happy path + blocked/negative path)
- UI smoke tests when GUI composition changes

No workflow/state change is complete without executable test evidence.

## Packaging Policy

When changing paths/resources/runtime wiring:
- verify EXE packaging paths and resource resolution
- keep build scripts and smoke checks synchronized
- avoid GUI-only startup dependencies

## Delivery Checklist

Before finalizing a change:
- file belongs to correct layer
- service ownership and boundaries remain intact
- only declared public ports are used across modules/interfaces
- no hidden cross-module coupling introduced
- tests updated and green
- docs updated if contracts/behavior changed

## Preferred Implementation Flow

1. Define/adjust contracts.
2. Implement service behavior.
3. Wire runtime/module registration.
4. Expose CLI path.
5. Add/update tests.
6. Add GUI adapter last (if needed).
7. Validate packaging impact.
