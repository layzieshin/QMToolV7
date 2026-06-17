# Module Integration Policy

Status: Canonical (P0)  
Valid from: 2026-06-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

This document is the **single onboarding entry** for developers integrating new features or modules into QMToolV7. It consolidates mandatory integration rules that are otherwise spread across P0/P2 docs. For module-specific ports, settings, and events, see `docs/MODULES_DEVELOPER_GUIDE.md`.

Related P0 sources (authoritative detail):

- Architecture boundaries: `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`
- Module contracts and per-module tables: `docs/MODULES_DEVELOPER_GUIDE.md`
- Licensing: `docs/LICENSE_SPEC.md`
- PyQt contributions: `docs/PYQT_CONTRIBUTIONS_REFERENCE.md`, `docs/GUI_ARCHITECTURE_PROJECT.md`
- Operations and release: `docs/OPERATIONS_CANONICAL.md`, `docs/TEST_SMOKE_GATES.md`

## 1. Scope and non-goals

### In scope

- In-repository module development under `modules/*`
- Registration in `qm_platform/runtime/bootstrap.py` (`core_module_contracts()`)
- Integration via **ports**, **capabilities**, **settings contributions**, **domain events**, **CLI**, and **PyQt contributions**
- Offline licensing, local auth, structured logging, and audit trails

### Out of scope (today)

- Runtime plugin loading or out-of-tree packages
- HTTP/REST API layer for third parties
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
  - `schema.sql` when persistence is required
- [ ] **Contract** — `ModuleContract` in `module.py` from `qm_platform/sdk/module_contract.py`:
  - `required_ports` / `provided_ports`
  - `required_capabilities` / `provided_capabilities`
  - optional `settings_contribution`, optional `license_tag`
- [ ] **Registration** — add `create_<name>_module_contract()` to `qm_platform/runtime/bootstrap.py` → `core_module_contracts()`
- [ ] **Public boundary** — external callers import only `modules/<name>/api.py` and `contracts.py` (see `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`)
- [ ] **Licensing** — if commercial gating is required, set `license_tag` and follow section 3; register tag is auto-discovered via `core_license_tags()`
- [ ] **Auth** — enforce roles in **service layer**, not in widgets or CLI parsers (section 4)
- [ ] **Logging** — use correct logger type per section 5
- [ ] **Events** — publish versioned domain events after successful commit (section 5)
- [ ] **Settings** — declare `SettingsContribution`; tag each key with governance class in `docs/MODULES_DEVELOPER_GUIDE.md`
- [ ] **CLI** — add command + parser under `interfaces/cli/`; verify CLI-first before PyQt
- [ ] **PyQt** (if UI needed) — `QtModuleContribution` + entry in `interfaces/pyqt/registry/catalog.py`
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
| GUI | Nav decoration via `module_id` → licensed modules; settings import in `license_section.py` |
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

### Where to enforce

| Layer | Responsibility |
| --- | --- |
| **Service** | Authoritative role and business-rule checks |
| **CLI/GUI** | Collect input, call ports, render errors; `requires_login` / `allowed_roles` on contributions |
| **License** | Module entitlement (orthogonal to user role) |

**Order of checks (normative):** license entitlement first for licensed modules, then user role. Example: module licensed but user lacks role → hidden/denied by role. User has role but module not licensed → blocked by license.

### CLI session

```bash
python -m interfaces.cli.main login --username <user> --password "<password>"
python -m interfaces.cli.main logout
```

Session file: `storage/platform/session/current_user.json` under `QMTOOL_HOME`.

## 5. Logging, audit, and domain events

There is **no** separate notification module. Use the following matrix.

| Mechanism | Port | When to use | Storage |
| --- | --- | --- | --- |
| Technical logger | `logger` | Operational info/warning/error, diagnostics | `storage/platform/logs/platform.log` (JSONL) |
| Audit logger | `audit_logger` | Compliance-relevant actions (who did what, result) | `storage/platform/logs/audit.log` (JSONL) |
| Domain events | `event_bus` | Cross-module coupling after successful commit | In-process pub/sub only |

### Domain event rules

- Naming: `domain.<module>.<event>.v1`
- Publish **after** successful persistence (not as primary UI state)
- Payload: small, structured, non-sensitive
- Use `EventEnvelope.create(...)` from `qm_platform/events/event_envelope.py`
- Subscribe in `wiring.py` or module `start()` hook (only when module is licensed/started)

Reference implementation: `modules/documents/eventing.py` (`publish_event`, `emit_audit`).

### License-related audit actions

Log imports via `audit_logger` (GUI already emits `license.import.file` / `license.import.code`). Do not log private keys or full license payloads in technical logs.

## 6. Public boundaries and cross-module access

From `docs/ARCHITECTURE_REFACTOR_CANONICAL.md`:

- External imports: `modules/<modul>/api.py` + `contracts.py` only
- Forbidden from outside: `service.py`, repositories, internal helpers
- Adapters (`interfaces/cli/*`, `interfaces/pyqt/*`) must not bypass service invariants
- Cross-module access: **declared ports** and **capabilities**, not direct internal imports
- State-changing operations must end in the authoritative module service

## 7. Adapter integration (CLI-first)

### CLI

1. Add parser under `interfaces/cli/parsers/`
2. Add command handler under `interfaces/cli/commands/`
3. Wire in `interfaces/cli/main.py`
4. Pattern: `build_container()` → `register_core_modules()` → `lifecycle.start()` → call port/API

### PyQt

1. Implement `contributions()` in `interfaces/pyqt/contributions/<name>.py`
2. Register in `interfaces/pyqt/registry/catalog.py`
3. Optional presenter in `interfaces/pyqt/presenters/`
4. Set `requires_login`, `allowed_roles`, `module_id` on `QtModuleContribution`
5. Do **not** duplicate business rules in widgets

**Order:** CLI + tests first, then PyQt contribution.

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
| Auth | role denial paths in service or CLI e2e |
| Events | `tests/modules/test_*_event_contracts.py` pattern |
| Platform | `tests/platform/test_runtime_enforcement.py` if contract/licensing changes |
| CLI e2e | `tests/e2e_cli/` for user-visible flows |
| Licensing | `tests/platform/test_license_*.py`, issuer integration test |

Run locally:

```bash
python -m unittest discover -s tests -p "test_*.py" -q
```

Release gates: `docs/TEST_SMOKE_GATES.md`, `scripts/golive_gate.py`, `python -m interfaces.cli.main doctor --strict`.

## 10. Release and bundle constraints

- Customer bundle must pass `packaging/verify_customer_bundle.py` (no private keys, no internal issuer)
- See `packaging/README.md` and `docs/LICENSE_SPEC.md`
- PyQt build: `python packaging/build_onedir.py`

## 11. Quick reference — integration surfaces

| Surface | Location | Consumer |
| --- | --- | --- |
| Module port | `container.get_port("<port>")` | CLI, PyQt, other modules |
| Public API | `modules/<m>/api.py` | Adapters, cross-module calls |
| Capability | string in `ModuleContract` | Startup validation |
| Settings | `settings_service.get_module_settings(module_id)` | Services, adapters |
| License check | `license_guard.ensure_module_allowed(tag)` | Licensed write/read APIs |
| Event publish | `event_bus.publish(envelope)` | Cross-module workflows |

## 12. Agent and contributor rule

When extending this repository:

- Do not add license issuing to the customer app or bundle
- Do not import module internals across boundaries
- Do not put business logic in PyQt widgets or CLI parsers
- Prefer extending existing ports and patterns over new global singletons

For historical engineering notes, see P2 `docs/DEVGUIDE.md` and `docs/AGENTS_PROJECT.md` — P0 docs win on conflict.
