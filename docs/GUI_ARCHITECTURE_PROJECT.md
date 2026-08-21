# GUI Architecture (Project-Specific)

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

This document defines how GUI functionality integrates into the modular runtime without
violating contracts or service ownership.

## Guiding Principle

GUI is a host/adapter layer.
Business truth stays in module services.

For non-pure-UI behavior, the order for **new** product work is:
1. service logic
2. tests
3. HTTP `/api/v1` contract (after backend transport exists for the use case)
4. webclient adapter

CLI remains an operator/test adapter. It is **not** a prerequisite for shipping web UI
once WEB00 exists, but CLI/operator paths stay valuable for ops and verification.

## Target Web Architecture (DECIDED; WEB00 not implemented yet)

- Central Vue 3 + TypeScript SPA under `webclient/`
- Vite toolchain; Vuetify only behind a QM-owned component layer
- SPA owns shell, router, theme, i18n, auth/connection state, and shared components
- Modules contribute versioned data contracts, capabilities, and `allowed_actions`
- Browser calls **only** Same-Origin `/api/v1`
- Authorization remains in the service layer; no business logic in the browser
- Generic-first views (list / detail / form / history)
- Custom views only for genuine specialty flows (e.g. PDF viewer, signature placement)
- No per-module frontend bundles

Until WEB00 completes, do not claim a productive web end-user client exists.

## Runtime Alignment

Active adapters and hosts:
- `qm_platform/*` for runtime/services
- `modules/*` for business behavior
- `src/backend/*` as HTTP transport host (no domain logic)
- `interfaces/cli/*` as operator/test adapter
- `webclient/*` as the only **new** end-user UI source (planned; not implemented as of GOV00)

Frozen legacy/reference adapters:
- `interfaces/pyqt/*` — frozen legacy/reference desktop UI (no new product work)
- `interfaces/gui/*` — legacy/test Tk path only

No parallel runtime and no parallel product UI workflow.

## Web Host Responsibilities (target)

- app boot, router, theme, i18n
- session/connection state against `/api/v1`
- navigation and module view hosting via generic or approved custom views
- shared error/output presentation
- permission feedback from server-provided `allowed_actions`

## Module UI Responsibilities (target)

Modules may provide:
- versioned DTOs / capabilities exposed via public APIs and HTTP contracts
- declarations that map to generic views
- rare custom-view requirements for specialty flows

Modules must not provide:
- separate frontend bundles
- workflow/state invariants in the browser
- authorization rules in the browser
- direct persistence or filesystem access from the client

## Service Responsibilities

Services remain authoritative for:
- lifecycle/status transitions
- role and permission checks
- persistence orchestration
- event publication
- invariant enforcement
- settings governance enforcement (`governance_critical` changes require explicit acknowledge path)

## Legacy PyQt Inventory (frozen; not onboarding)

Historical PyQt structure (reference only — no new contributions):

```text
interfaces/pyqt/
├─ main.py
├─ shell/main_window.py
├─ registry/catalog.py
├─ contributions/*
├─ presenters/*
├─ sections/*
└─ widgets/*
```

See `docs/PYQT_CONTRIBUTIONS_REFERENCE.md` (Legacy/History P2) for the frozen contribution
matrix. Do not treat that document as current product onboarding.

## Hard Prohibitions

- no business logic in UI callbacks or Vue components
- no direct DB writes from any GUI layer
- no bypass of module service APIs
- no second productive end-user UI path beside `webclient/` for new work
- no new PyQt contributions or parallel PyQt/Web fach workflows
- no server filesystem paths exposed to the browser

## Validation Requirements

- affected service and HTTP/CLI tests remain green
- after WEB00: web foundation and contract tests for composition changes
- packaging/deployment checks updated when host paths/resources change
- settings write paths must preserve governance acknowledge semantics (no bypass)
