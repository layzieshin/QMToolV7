# Module Integration Policy

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

This document is the **single onboarding entry** for developers integrating new features or
modules into QMToolV7. For module-specific ports, settings, and events, see
`docs/MODULES_DEVELOPER_GUIDE.md` (Ist-/Legacy-Inventar is explicitly marked there).

Related P0 sources (authoritative detail):

- Architecture boundaries: `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`
- Module contracts and per-module tables: `docs/MODULES_DEVELOPER_GUIDE.md`
- Licensing: `docs/LICENSE_SPEC.md`
- Target GUI / web adapter model: `docs/GUI_SOURCE_OF_TRUTH.md`, `docs/GUI_ARCHITECTURE_PROJECT.md`
- Operations and release: `docs/OPERATIONS_CANONICAL.md`, `docs/TEST_SMOKE_GATES.md`
- Database target runtime: `docs/DATABASE_EVOLUTION_POLICY.md`

## 1. Scope and non-goals

### In scope

- In-repository module development under `modules/*`
- Registration in `qm_platform/runtime/bootstrap.py` (`core_module_contracts()`)
- Integration via explicit module APIs, **ports**, **capabilities**, **settings contributions**,
  **domain events**, backend/HTTP `/api/v1` contracts, and the central `webclient/` SPA
  (after WEB00)
- CLI as **operator/test adapter** (useful, not a prerequisite for web UI delivery)
- Offline licensing, local/server auth, structured logging, and audit trails
- **PostgreSQL-only** productive persistence for new product work (one DB per installation;
  schema/ownership per module)

### Out of scope (today / first pilot)

- New PyQt product UI or new PyQt contributions (PyQt is frozen legacy/reference)
- Runtime plugin loading or out-of-tree packages
- Public third-party API beyond the internal `/api/v1` browser/backend contract
- Multi-tenant administration in the first pilot
- Productive SQLite persistence or SQLite fallback
- Direct cross-schema SQL between fach modules
- Business logic in the browser
- Dedicated notification service (email, push, in-app inbox)
- Online license activation or revocation
- License issuing inside the customer application (use `tools/internal_license_issuer/` only)

## 2. Module onboarding checklist

Use this checklist when adding or extending a module. Every item is blocking before merge.

- [ ] **Layout** — `modules/<name>/` contains at minimum:
  - `contracts.py` (DTOs)
  - `api.py` (public facade for other modules/adapters)
  - `service.py` or focused ops modules (business logic)
  - `module.py` (`ModuleContract` + `start`/`stop`)
  - `wiring.py` (`register_<name>_ports`)
  - PostgreSQL migrations / schema ownership when persistence is required (target runtime)
- [ ] **Contract** — `ModuleContract` in `module.py` from `qm_platform/sdk/module_contract.py`:
  - `required_ports` / `provided_ports`
  - `required_capabilities` / `provided_capabilities`
  - optional `settings_contribution`, optional `license_tag`
- [ ] **Registration** — add `create_<name>_module_contract()` to `qm_platform/runtime/bootstrap.py` → `core_module_contracts()`
- [ ] **Public boundary** — external Python callers import only `modules/<name>/api.py`
- [ ] **Persistence** — productive new persistence is PostgreSQL-only; no SQLite product path;
  no cross-schema direct access between fach modules
- [ ] **HTTP** — browser-facing use cases expose `/api/v1` transport via the backend host
  without domain logic in transport code
- [ ] **Webclient** — after WEB00, integrate via central SPA generic/custom views; no module
  frontend bundle
- [ ] **Licensing** — if commercial gating is required, set `license_tag` and follow section 3
- [ ] **Auth** — enforce roles in **service layer**, not in UI or CLI parsers (section 4)
- [ ] **Logging / audit** — use correct logger type; fachliche Auditquelle is PostgreSQL append-only (target)
- [ ] **Events** — publish versioned domain events after successful commit
- [ ] **Settings** — declare `SettingsContribution`; tag governance class in `docs/MODULES_DEVELOPER_GUIDE.md`
- [ ] **CLI** — optional operator/test commands under `interfaces/cli/`; not a substitute for service tests
- [ ] **Tests** — section 8

## 3. Licensing integration

Normative detail: `docs/LICENSE_SPEC.md`.

| Concern | Rule |
| --- | --- |
| Customer app | Import and **validate** licenses only; never issue production licenses |
| Base license | Carries customer/machine metadata; **does not** block app startup |
| Module lock | Only modules with `license_tag` are gated (currently `training`) |
| Tag registration | `license_tag` on `ModuleContract`; discovery via `core_license_tags()` / `core_licensed_modules()` |
| Startup gate | `ensure_license()` in `qm_platform/runtime/lifecycle_checks.py` |
| Runtime gate | `LicenseGuard` / `LicensedPortProxy` on all public API entry points of licensed modules |
| UI | Nav decoration via `module_id` → licensed modules (legacy PyQt paths are frozen reference) |
| Dev mode | `QMTOOL_LICENSE_MODE=dev` auto-provisions local dev license |
| Production | `QMTOOL_LICENSE_MODE=production`; missing/invalid license → licensed modules blocked, app runs |
| Issuing | `python tools/internal_license_issuer/create_license.py create-license …` (internal only) |

When adding a new licensed module:

1. Set `license_tag="<tag>"` on `ModuleContract`.
2. Wrap provided APIs with `LicensedPortProxy` in `wiring.py` (see `modules/training/wiring.py`).
3. Add tests for blocked and allowed paths.
4. Update issuer workflow documentation if the tag is customer-facing.

## 4. User accounts and authorization

### Ports and capabilities

| Port | Purpose |
| --- | --- |
| `usermanagement_service` | Auth, session, user admin |

| Capability | Purpose |
| --- | --- |
| `auth.authenticate` | Credential verification |
| `auth.session.read` | Current session access |

### Roles

System roles: `Admin`, `QMB`, `User` (+ `is_qmb` flag). Production standard (mandatory for QM deployments):

- `seed_mode` = `hardened`
- `dev_mode` = `false`
- No known-default passwords in production datasets
- Bcrypt (or equivalent) for stored credentials

See `docs/MODULES_DEVELOPER_GUIDE.md` (usermanagement) and `docs/OPERATIONS_CANONICAL.md`.

Target browser sessions (DECIDED; implement in WEB00+): Same-Origin HTTPS, opaque
server-side PostgreSQL sessions, HttpOnly/Secure/appropriate SameSite cookie, CSRF for
mutating requests. No session token in `localStorage`/`sessionStorage`.
`organization_id` and actor identity come from server context, not authoritative browser input.

### Where to enforce

| Layer | Responsibility |
| --- | --- |
| **Service** | Authoritative role and business-rule checks |
| **CLI / Web / legacy UI** | Collect input, call ports/HTTP, render errors; never own authorization |
| **License** | Module entitlement (orthogonal to user role) |

**Order of checks (normative):** license entitlement first for licensed modules, then user role.

### CLI session (operator/test; current Ist path)

```bash
.\.venv\Scripts\python.exe -m interfaces.cli.main login --username <user> --password "<password>"
.\.venv\Scripts\python.exe -m interfaces.cli.main logout
```

Legacy desktop session file paths may still exist in current code; they are not the
target browser session model.

## 5. Logging, audit, and domain events

There is **no** separate notification module. Use the following matrix.

| Mechanism | Port | When to use | Storage (target vs Ist) |
| --- | --- | --- | --- |
| Technical logger | `logger` | Operational info/warning/error, diagnostics | technical logs (not fachliche Nachweisquelle) |
| Audit logger / audit store | `audit_logger` / PG audit | Compliance-relevant actions | **Target:** append-only PostgreSQL audit with actor, organization_id, request/correlation, time, object, action. **Ist/legacy file JSONL may still exist** and is not the target sole evidence source |
| Domain events | `event_bus` | Cross-module coupling after successful commit | In-process pub/sub only |

Never log secrets, passwords, session tokens, or private keys.

### Domain event rules

- Naming: `domain.<module>.<event>.v1`
- Publish **after** successful persistence (not as primary UI state)
- Payload: small, structured, non-sensitive
- Use `EventEnvelope.create(...)` from `qm_platform/events/event_envelope.py`
- Subscribe in `wiring.py` or module `start()` hook (only when module is licensed/started)

Reference implementation: `modules/documents/eventing.py` (`publish_event`, `emit_audit`).

## 6. Public boundaries and cross-module access

From `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`:

- The public Python import boundary of a module is `modules/<modul>/api.py`.
- Registered `RuntimeContainer` ports, declared `ModuleContract` capabilities, settings
  contributions, and domain events are runtime integration mechanisms, not alternative
  Python import surfaces.
- Forbidden from outside: `service.py`, repositories, `storage.py`, `errors.py`,
  `*_ops.py`, `module.py`, `wiring.py`, internal helpers, and concrete path/persistence/rendering/layout logic.
- Adapters (`interfaces/cli/*`, frozen `interfaces/pyqt/*`, future `webclient/*`) must not bypass service invariants.
- Cross-module access: public `api.py` contracts or explicit runtime wiring — **no** direct
  cross-schema SQL between fach modules.
- State-changing operations from outside a module must go through explicit public API
  contracts; internal services remain module implementation details.

## 7. Adapter integration

### HTTP / webclient (target; after WEB00)

1. Expose use case via `modules/<name>/api.py`
2. Add thin `/api/v1` transport in `src/backend/*` (no domain logic)
3. Consume from central `webclient/` SPA (generic views first; custom only when required)
4. Enforce Cookie/CSRF Same-Origin rules

### CLI (operator/test adapter)

1. Add parser under `interfaces/cli/parsers/`
2. Add command handler under `interfaces/cli/commands/`
3. Wire in `interfaces/cli/main.py`
4. Pattern: `build_container()` → `register_core_modules()` → `lifecycle.start()` → call port/API

### PyQt (frozen legacy — do not extend for product work)

Do **not** add new PyQt contributions. Historical contribution inventory:
`docs/PYQT_CONTRIBUTIONS_REFERENCE.md` (P2 Legacy/History).

## 8. Settings governance

- Every settings key MUST have a governance class in `docs/MODULES_DEVELOPER_GUIDE.md`:
  - `operational`
  - `development`
  - `governance_critical`
- CLI `settings set` on `governance_critical` keys requires `--acknowledge-governance-change`
- Registry: `qm_platform/settings/governance_critical_keys.py`

## 9. Testing requirements

Minimum before merge:

| Area | Tests |
| --- | --- |
| Module ports | `tests/modules/test_<module>_*.py` |
| Licensed module | blocked without license, allowed with valid license |
| Auth | role denial paths in service or e2e |
| Events | `tests/modules/test_*_event_contracts.py` pattern |
| Platform | `tests/platform/test_runtime_enforcement.py` if contract/licensing changes |
| CLI e2e | `tests/e2e_cli/` for operator-visible flows |
| HTTP / web (after WEB00) | `/api/v1` contract and web-foundation gates per `docs/TEST_SMOKE_GATES.md` |
| Licensing | `tests/platform/test_license_*.py`, issuer integration test |

Run locally:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Release gates: `docs/TEST_SMOKE_GATES.md`, `scripts/golive_gate.py`,
`.\.venv\Scripts\python.exe -m interfaces.cli.main doctor --strict`.

## 10. Release and bundle constraints

- Customer bundle must pass `packaging/verify_customer_bundle.py` (no private keys, no internal issuer)
- See `packaging/README.md` and `docs/LICENSE_SPEC.md`
- Legacy PyQt onedir build remains an Ist packaging path until OPS00 supersedes deployment:
  `.\.venv\Scripts\python.exe packaging/build_onedir.py`

## 11. Quick reference — integration surfaces

| Surface | Location | Consumer |
| --- | --- | --- |
| Public Python API | `modules/<m>/api.py` | Adapters, cross-module calls |
| HTTP boundary | `/api/v1` (target) | Browser SPA, internal clients |
| Runtime port | `container.get_port("<port>")` | Runtime-wired adapters/modules |
| Capability | string in `ModuleContract` | Startup validation |
| Settings | `settings_service.get_module_settings(module_id)` | Services, adapters |
| License check | `license_guard.ensure_module_allowed(tag)` | Licensed write/read APIs |
| Event publish | `event_bus.publish(envelope)` | Cross-module notifications |

## 12. Agent and contributor rule

When extending this repository:

- Do not add license issuing to the customer app or bundle
- Do not import module internals across boundaries
- Do not put business logic in webclient, legacy PyQt widgets, or CLI parsers
- Do not add new PyQt product UI
- Do not introduce productive SQLite persistence or SQLite fallback
- Prefer extending existing ports and patterns over new global singletons
- Follow `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` for transition order

For historical engineering notes, see P2 `docs/DEVGUIDE.md` and `docs/AGENTS_PROJECT.md` — P0 docs win on conflict.
