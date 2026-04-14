# GUI Architecture (Project-Specific)

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

This document defines how GUI functionality is integrated into the current modular runtime without violating contracts, CLI-first verification, or service ownership.

## Guiding Principle

GUI is a host/adapter layer.
Business truth stays in module services.

For non-pure-UI behavior, the order remains:
1. service logic
2. tests
3. CLI path
4. GUI adapter

## Runtime Alignment

GUI and CLI use the same runtime container and ports:
- `qm_platform/*` for runtime/services
- `modules/*` for business behavior
- `interfaces/pyqt/*` and `interfaces/cli/*` as active adapters
- `interfaces/gui/*` only as legacy/test adapter

No parallel runtime, no parallel startup path.

## Recommended Integration Strategy

Use a central GUI host shell with embedded module contributions.

### Host Responsibilities

- app boot and runtime container initialization
- navigation and module view hosting
- shared output/error pipeline
- session-aware orchestration and permission feedback

### Module UI Responsibilities

Module UI components may provide:
- view widgets
- presenter/viewmodel adapters
- optional contribution registration objects

Module UI components must not contain:
- workflow/state invariants
- authorization rules
- direct persistence writes that bypass services

### Service Responsibilities

Services remain authoritative for:
- lifecycle/status transitions
- role and permission checks
- persistence orchestration
- event publication
- invariant enforcement
- settings governance enforcement (`governance_critical` changes require explicit acknowledge path)

## Contribution Model

Preferred target structure for growing GUI modularity:

```text
interfaces/pyqt/
├─ main.py
├─ shell/main_window.py
├─ registry/catalog.py
├─ contributions/*
└─ widgets/*

modules/<module>/ui/
├─ contribution.py
├─ view.py
└─ presenter.py
```

Current implementation is already on this PyQt structure and should be expanded there only.

## PyQt Guidance (Current Stack)

- One `QMainWindow` shell hosts contribution views.
- Module views are `QWidget` contributions resolved via `registry/catalog.py`.
- Role/license visibility is handled in shell orchestration.
- Technical raw/debug payloads are separated from task-oriented fachliche views.
- Contribution-level inputs/outputs/ports/contracts are documented in `docs/PYQT_CONTRIBUTIONS_REFERENCE.md`.

## Legacy Tk Path (Compatibility Only)

Tk remains available for compatibility/smoke but is not the active GUI evolution path.

## Hard Prohibitions

- no business logic in button callbacks
- no direct DB writes from GUI layer
- no bypass of module service APIs
- no second startup/runtime path
- no fragmented per-module output channels

## Validation Requirements for GUI Changes

- affected service and CLI tests remain green
- UI smoke tests updated where composition changes
- runtime/packaging checks updated when paths/resources change
- GUI settings write path must pass the same governance acknowledge semantics as CLI (no bypass).
