# CLI-First Migration Guardrails (Phase 0)

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

This file defines mandatory guardrails before implementing the new `documents` module.

## Active Architecture

- Active runtime path is `interfaces/cli` + `interfaces/pyqt` + `qm_platform/*` + `modules/*`.
- Module wiring must stay contract-driven via `ModuleContract`.
- Startup and runtime checks must be enforced by lifecycle guards (ports, capabilities, license, settings contribution).

## Deprecated Architecture (Do Not Extend)

- `main.py` GUI startup path.
- `framework/gui/*` runtime path.
- Legacy `core/*` application context path for new features.
- Legacy `documents/*` implementation path.
- Legacy `word_meta/gui/main.py` standalone GUI entry path.

New work must not introduce new dependencies on deprecated paths.

## Database Baseline

- Core runtime features target `databases/qm-tool.db`.
- Future document management persistence will use a dedicated `documents.db`.
- No implicit startup dependency on legacy document databases.

## Phase 0 gates (historic, migration period)

During the tranche that retired legacy top-level packages, the following were **mandatory**:

1. **CLI-only verification for that phase**: GUI and legacy starters were explicitly out of scope for migration sign-off; all automated verification and boundary tests targeted the CLI bootstrap path.
2. Platform/module tests are green for active runtime paths.
3. Boot path does not require legacy AppContext wiring.
4. Legacy tests that validate removed behavior are quarantined or skipped with clear rationale.
5. Boundary tests prevent legacy imports from re-entering active modular paths.

This does **not** mean the product forbids a GUI forever; it bounded what counted as “done” for that migration step.

## Current supported entry paths (post-migration)

- **CLI** (`interfaces/cli`) and **PyQt GUI** (`interfaces/pyqt`) are supported adapters on the **same** runtime model (`qm_platform/*`, `modules/*`).
- **Legacy Tk GUI** (`interfaces/gui`) remains compatibility/test-only and is not the primary UI development path.
- **CLI-first engineering** remains the default for feature development and regression: new behavior should be testable from CLI before GUI work depends on it.
- **Do not** reintroduce deprecated starters listed under “Deprecated Architecture”.

## Notes

- This migration is intentionally incremental.
- Legacy top-level paths were removed after integration verification (`core/`, `documents/`, `framework/`, `word_meta/`, old `signature/` package).
- New work must stay in `modules/*`, `qm_platform/*`, and `interfaces/*`.
