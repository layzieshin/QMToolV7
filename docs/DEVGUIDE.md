# Developer Guide (Modular Platform)

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

This guide is the fixed implementation reference for all new modules in this repository.

Additional project rule sets:
- `docs/AGENTS_PROJECT.md`
- `docs/GUI_ARCHITECTURE_PROJECT.md`
- `docs/OPERATIONS_CANONICAL.md`

## 1) Architecture Principles

- Build business features in `modules/*`, not in interface layers.
- Keep UI/CLI as adapters; business rules live in services and contracts.
- Use explicit runtime dependencies (ports/capabilities), not global state.
- Prefer deterministic startup checks (fail-fast on missing contract requirements).

Core runtime entry points:
- `qm_platform/runtime/container.py`
- `qm_platform/runtime/lifecycle.py`
- `qm_platform/runtime/bootstrap.py`
- `qm_platform/sdk/module_contract.py`

## 2) Repository Layout

- `qm_platform/`
  - `runtime/`: container, lifecycle, compatibility, health
  - `sdk/`: module contracts and settings contribution contracts
  - `logging/`: structured logger + audit logger
  - `events/`: event envelope + event bus
  - `settings/`: settings registry/service/store
  - `licensing/`: license validation, policy, guard
- `modules/`
  - one folder per module (`usermanagement`, `signature`, ...)
- `interfaces/cli/`
  - CLI composition and commands
- `tests/`
  - `qm_platform/`, `modules/`, `e2e_cli/`

## 3) Module Contract (Authoritative)

Each module must define `ModuleContract` from `qm_platform/sdk/module_contract.py`.

Required fields:
- identity: `module_id`, `version`, `min_platform_version`, `max_platform_version`
- ports: `required_ports`, `provided_ports`
- capabilities: `required_capabilities`, `provided_capabilities`
- optional integrations: `settings_contribution`, `license_tag`
- lifecycle hooks: `register`, `start`, `stop`

Runtime enforcement in `qm_platform/runtime/lifecycle.py` checks:
- required ports
- required capabilities
- license access (when `license_tag` is set)
- provided ports after module start
- settings contribution registration/validation

## 4) Add a New Module (Checklist)

Create:
- `modules/<module>/contracts.py`
- `modules/<module>/service.py`
- `modules/<module>/module.py`
- optional `modules/<module>/api.py`

Steps:
1. Define typed request/result contracts (dataclasses).
2. Implement service with explicit injected dependencies.
3. Define `create_<module>_module_contract()` in `module.py`.
4. Register module in `qm_platform/runtime/bootstrap.py`.
5. Add CLI adapter if needed in `interfaces/cli/main.py`.
6. Add tests in all relevant layers.

## 5) Port vs Capability

- **Port**: concrete runtime dependency in container (`container.get_port("...")`).
- **Capability**: declared functional promise (`domain.action`) checked at startup.

Conventions:
- capability names: `domain.module.action` or `domain.action`
- event names: `domain.<module>.<event>.v1`

## 6) Settings Integration

Use `SettingsContribution` in the module contract whenever module settings exist.

Do:
- Provide schema + defaults.
- Keep defaults backward-compatible.
- Read settings via `settings_service.get_module_settings(module_id)`.

Do not:
- Register settings ad-hoc in multiple places outside contract-driven flow.

### Settings governance model (normative)

Classify settings into three groups:

1. **Operational settings**
   - runtime paths, log/DB locations, diagnostics behavior
   - may be changed by authorized operators (`ADMIN`/`QMB`) with audit trace

2. **Development settings**
   - local smoke convenience values
   - must be clearly marked as non-production
   - must not weaken production defaults

3. **Governance-critical business settings**
   - workflow/profile steering and other compliance-relevant controls
   - require release-controlled change process (ticket + review + evidence)
   - must not be changed ad-hoc during production operation

Minimum policy:
- every module settings key MUST be tagged to one of the three groups in developer docs (authoritative per-module tables: `docs/MODULES_DEVELOPER_GUIDE.md`),
- CLI `settings set` usage in production must follow role and change-control policy; `governance_critical` keys require the same evidence as any compliance-impacting config change, not ad-hoc edits.

## 7) Licensing Integration

If module requires a license:
- set `license_tag` in `ModuleContract`.
- ensure operations that mutate state are behind module/service guards.
- keep license tags discoverable through runtime bootstrap (`qm_platform/runtime/bootstrap.py`) so new licensed modules are automatically reflected by dev licensing utilities.

CLI wiring currently creates a local dev license for deterministic local startup in:
- `interfaces/cli/main.py`
- controlled by `QMTOOL_LICENSE_MODE` (`dev`/`auto` enables local dev autoprovisioning; other values disable implicit generation).

Internal licensing tool (not customer-facing):
- `python scripts/license_generate.py --output <license.json> --private-key-pem <issuer.pem> --key-id <id> --license-id <id> --issued-to <name> --customer-id <id> --expires-at <iso8601> --enable-module <tag> [--enable-module <tag> ...]`

## 8) Event Bus Usage

Publish minimum lifecycle/business events:
- module started/stopped
- operation succeeded/failed

Use `EventEnvelope.create(...)` from:
- `qm_platform/events/event_envelope.py`

Keep payloads small, structured, and non-sensitive.

## 9) CLI-First Workflow

Primary local verification commands:
- `python -m interfaces.cli.main health`
- `python -m interfaces.cli.main login --username admin --password "<strong-password>"`
- `python -m interfaces.cli.main sign visual --help`

All feature work should be testable from CLI before GUI integration.

## 9.1) Release-Blocking Migration Gates (Normative)

For migrations that affect documents schema/semantics, release is blocked until all gates are satisfied:

- pre/post data-quality report attached to release evidence
- `doc_type=OTHER` count does not increase vs baseline
- invalid `doc_type/control_class/workflow_profile_id` combinations are `0`
- full relevant regression suite is green

Required evidence artifacts:
- SQL report output
- test run logs
- explicit Go/No-Go decision record

CI recommendation:
- execute migration-gate checks as a dedicated pipeline step,
- fail pipeline on any gate violation.
- reference workflow in repository: `.github/workflows/ci-gates.yml`.
- optional consolidated local gate:
  - `python scripts/golive_gate.py --output "<evidence-dir>/golive-gate.json"`.
- reference implementation command:
  - `python scripts/migration_gates_documents.py --documents-db-path "<path-to-documents.db>" --profiles-path "modules/documents/workflow_profiles.json" --baseline-other-count <pre-migration-count>`
  - optional registry drift checks: add `--registry-db-path "<path-to-registry.db>"`.

## 10) Testing Matrix (Required)

For each module change:
- **Platform tests**: runtime guards/enforcement
- **Module tests**: service behavior and errors
- **CLI e2e tests**: command-level happy path + at least one negative path

Current references:
- `tests/platform/test_runtime_enforcement.py`
- `tests/platform/test_capability_registry.py`
- `tests/platform/test_license_service.py`
- `tests/modules/test_signature_service_v2.py`
- `tests/e2e_cli/test_startup_and_guards.py`
- `docs/DOCUMENTS_TEST_COVERAGE.md` (documents action-role-status matrix and test mapping)
- `docs/MODULES_USER_GUIDE.md` (module usage from user perspective)
- `docs/MODULES_DEVELOPER_GUIDE.md` (module contracts/settings/events/tests overview)

## 11) Module Template (Copy/Paste)

```python
from platform.sdk.module_contract import ModuleContract, SettingsContribution

def register_<module>_ports(container) -> None:
    # create service/api and register provided ports
    pass

def start_<module>(container) -> None:
    pass

def stop_<module>(container) -> None:
    pass

def create_<module>_module_contract() -> ModuleContract:
    settings = SettingsContribution(
        module_id="<module>",
        schema_version=1,
        schema={"type": "object"},
        defaults={},
        scope="module_global",
        migrations=[],
    )
    return ModuleContract(
        module_id="<module>",
        version="1.0.0",
        min_platform_version="1.0.0",
        max_platform_version=None,
        required_ports=["logger", "event_bus", "settings_service"],
        provided_ports=["<module>_service"],
        required_capabilities=[],
        provided_capabilities=["<module>.ready"],
        settings_contribution=settings,
        license_tag=None,
        register=register_<module>_ports,
        start=start_<module>,
        stop=stop_<module>,
    )
```

## 12) Legacy Migration Playbook

When migrating legacy code (`core/`, `documents/`, old `signature/`):
1. Define new typed contracts in `modules/<module>/contracts.py`.
2. Wrap legacy internals in a new service (adapter style).
3. Route CLI paths to new module service.
4. Add parity tests before deleting legacy callsites.
5. Remove legacy dependencies only after green qm_platform/module/e2e tests.

Keep migration incremental and test-driven.

Repository status note:
- The CLI-first migration is complete for the legacy top-level runtime paths.
- New changes must not re-introduce dependencies on removed legacy packages.

