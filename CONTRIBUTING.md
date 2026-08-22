# Contributing to QMToolV7

Single entry point for developers. QMToolV7 is a modular quality-management platform
(domain modules under `modules/*`, runtime under `qm_platform/*`, adapters under
`interfaces/*` and future `webclient/*`) transitioning to Web + PostgreSQL per
[`docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`](docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md).

For AI-assisted work, see [`AGENTS.md`](AGENTS.md) and `.cursor/rules/00-agent-workflow.mdc`.

## Setup and start

- Python `3.14.x` (`pyproject.toml` `requires-python = ">=3.14,<3.15"`).
- Use the workspace venv explicitly: `.\.venv\Scripts\python.exe`.
- Install (PowerShell; chain with `;`, not `&&`):

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-py314.txt -r requirements.txt -r requirements-pyqt.txt -r requirements-dev.txt
```

Entry points (run from the project root):

| Purpose | Command |
| --- | --- |
| CLI (operator/test) | `.\.venv\Scripts\python.exe -m interfaces.cli.main` |
| Backend host | `.\.venv\Scripts\python.exe -m src.backend` |
| First-run init | `.\.venv\Scripts\python.exe -m interfaces.cli.main init --non-interactive --admin-password "<password>"` |
| Diagnostics | `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor` (`--strict` for production checks) |
| Tests | `.\.venv\Scripts\python.exe -m pytest` |
| Ist packaging (legacy desktop) | `.\.venv\Scripts\python.exe packaging/build_onedir.py` |
| Legacy PyQt GUI (frozen reference) | `.\.venv\Scripts\python.exe -m interfaces.pyqt` |
| Target web UI | `webclient/` after WEB00 — not implemented yet; do not invent npm/Vite commands |

### Lokaler PostgreSQL-Labserver (AP-028 / Übergang)

- Vorlage: [`.env.example`](.env.example) → lokale `.env` (gitignored) mit `QMTOOL_PG_PASSWORD`.
- Host `192.168.0.4`, Port `5432`, DB `qmtool_test`, User `qmtool`.
- Backend zusätzlich: `QMTOOL_LICENSE_MODE=dev` und bei leerer User-Tabelle
  `QMTOOL_BOOTSTRAP_ADMIN_USERNAME` / `QMTOOL_BOOTSTRAP_ADMIN_PASSWORD`
  (nicht `admin`/`admin`).
- Details: [`docs/AP-028_M3_POSTGRES_SCHEMA.md`](docs/AP-028_M3_POSTGRES_SCHEMA.md) (Abschnitt „Lokaler Lab-Testserver“).
- Productive target runtime is PostgreSQL-only (AP-029); lab usage is not a SQLite fallback license.

### J04 Slot-2 destructive PostgreSQL (lokal, gitignored)

- Vorlage: [`.env.example`](.env.example) — **nicht** `QMTOOL_PG_TEST_RESET` speichern.
- Einmalig / nach Branch-Bereinigung: [`tests/postgres/README.md`](tests/postgres/README.md)
  (`scripts/provision_j04_destructive_postgres.py`, dann `scripts/run_postgres_live_tests.py`).
- Slot 1 (`QMTOOL_PG_HOST` / Lab `192.168.0.4`) und Slot 2 (`QMTOOL_PG_TEST_*`) getrennt halten.

## Documentation map ("I want X -> read Y")

Priority and conflict resolution: [`docs/DOCS_CANONICAL_INDEX.md`](docs/DOCS_CANONICAL_INDEX.md) (P0 overrules P1/P2).

- Transition order / checkpoints -> [`docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`](docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md)
- Add or extend a module -> [`docs/MODULE_INTEGRATION_POLICY.md`](docs/MODULE_INTEGRATION_POLICY.md)
- Module ports / settings / events / contracts -> [`docs/MODULES_DEVELOPER_GUIDE.md`](docs/MODULES_DEVELOPER_GUIDE.md)
- Architecture boundaries -> [`docs/ARCHITECTURE_REFACTOR_CANONICAL.md`](docs/ARCHITECTURE_REFACTOR_CANONICAL.md)
- New end-user UI (web) -> [`docs/GUI_SOURCE_OF_TRUTH.md`](docs/GUI_SOURCE_OF_TRUTH.md), [`docs/GUI_ARCHITECTURE_PROJECT.md`](docs/GUI_ARCHITECTURE_PROJECT.md)
- Frozen PyQt inventory (not onboarding) -> [`docs/PYQT_CONTRIBUTIONS_REFERENCE.md`](docs/PYQT_CONTRIBUTIONS_REFERENCE.md)
- Database target / Ist SQLite -> [`docs/DATABASE_EVOLUTION_POLICY.md`](docs/DATABASE_EVOLUTION_POLICY.md)
- Licensing -> [`docs/LICENSE_SPEC.md`](docs/LICENSE_SPEC.md)
- Document-control domain -> [`docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`](docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md), [`docs/DOCUMENTS_CLI_REFERENCE.md`](docs/DOCUMENTS_CLI_REFERENCE.md)
- Operations and release -> [`docs/OPERATIONS_CANONICAL.md`](docs/OPERATIONS_CANONICAL.md), [`docs/TEST_SMOKE_GATES.md`](docs/TEST_SMOKE_GATES.md)
- Build and deployment -> [`packaging/README.md`](packaging/README.md)
- User-facing operations -> [`docs/MODULES_USER_GUIDE.md`](docs/MODULES_USER_GUIDE.md)
- Local setup detail -> [`docs/QMToolV7_ENTWICKLUNG.md`](docs/QMToolV7_ENTWICKLUNG.md)

Recommended reading order follows the "Mandatory Reading Order" in [`docs/OPERATIONS_CANONICAL.md`](docs/OPERATIONS_CANONICAL.md).

## Core rules (summary)

- Fachliche business logic in `modules/*` services only; `qm_platform/*` is platform infrastructure. Keep UI/CLI as thin adapters.
- Before adding entrypoints, UI actions, or public APIs: search existing owners first (`AGENTS.md` guardrails).
- External Python access to modules goes through `modules/<name>/api.py`; runtime ports,
  capabilities and events are integration mechanisms, not alternative import surfaces.
- State-changing operations from outside a module must use explicit public API contracts.
- Enforce auth/roles in the service layer, not in UI or CLI parsers.
- New features: service/API/HTTP contract and tests first, then `webclient/` (after WEB00).
- New productive persistence is PostgreSQL-only; no SQLite product fallback.
- Do not add new PyQt product UI.

## Tests and merge gates

- Run the smallest relevant layer (`tests/platform`, `tests/modules`, `tests/interfaces`, `tests/e2e_cli`, `tests/docs`),
  then broaden before finishing. Details: `.cursor/rules/00-agent-workflow.mdc`.
- Release/migration gates and CI authority: [`docs/OPERATIONS_CANONICAL.md`](docs/OPERATIONS_CANONICAL.md),
  [`docs/TEST_SMOKE_GATES.md`](docs/TEST_SMOKE_GATES.md).
- This repository has no configured linter/typechecker; do not add lint/typecheck steps ad hoc.
