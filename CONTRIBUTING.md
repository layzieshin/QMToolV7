# Contributing to QMToolV7

Single entry point for developers. QMToolV7 is a CLI-first, modular quality-management platform
(domain modules under `modules/*`, runtime under `qm_platform/*`, adapters under `interfaces/*`).

For AI-assisted work, see [`AGENTS.md`](AGENTS.md) and `.cursor/rules/00-agent-workflow.mdc`.

## Setup and start

- Python `3.14.x` (`pyproject.toml` `requires-python = ">=3.14,<3.15"`).
- Install (PowerShell; chain with `;`, not `&&`):

```powershell
python -m pip install -c constraints-py314.txt -r requirements.txt -r requirements-pyqt.txt
```

Entry points (run from the project root):

| Purpose | Command |
| --- | --- |
| CLI | `python -m interfaces.cli.main` |
| PyQt GUI (current) | `python -m interfaces.pyqt` |
| First-run init | `python -m interfaces.cli.main init --non-interactive --admin-password "<password>"` |
| Diagnostics | `python -m interfaces.cli.main doctor` (`--strict` for production checks) |
| Tests | `$env:PYTHONPATH="."; python -m pytest` |
| Production build | `python packaging/build_onedir.py` |

## Documentation map ("I want X -> read Y")

Priority and conflict resolution: [`docs/DOCS_CANONICAL_INDEX.md`](docs/DOCS_CANONICAL_INDEX.md) (P0 overrules P1/P2).

- Add or extend a module -> [`docs/MODULE_INTEGRATION_POLICY.md`](docs/MODULE_INTEGRATION_POLICY.md)
- Module ports / settings / events / contracts -> [`docs/MODULES_DEVELOPER_GUIDE.md`](docs/MODULES_DEVELOPER_GUIDE.md)
- Architecture boundaries -> [`docs/ARCHITECTURE_REFACTOR_CANONICAL.md`](docs/ARCHITECTURE_REFACTOR_CANONICAL.md)
- GUI work (PyQt) -> [`docs/PYQT_CONTRIBUTIONS_REFERENCE.md`](docs/PYQT_CONTRIBUTIONS_REFERENCE.md), [`docs/GUI_ARCHITECTURE_PROJECT.md`](docs/GUI_ARCHITECTURE_PROJECT.md), [`docs/GUI_SOURCE_OF_TRUTH.md`](docs/GUI_SOURCE_OF_TRUTH.md)
- Licensing -> [`docs/LICENSE_SPEC.md`](docs/LICENSE_SPEC.md)
- Document-control domain -> [`docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`](docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md), [`docs/DOCUMENTS_CLI_REFERENCE.md`](docs/DOCUMENTS_CLI_REFERENCE.md)
- Operations and release -> [`docs/OPERATIONS_CANONICAL.md`](docs/OPERATIONS_CANONICAL.md), [`docs/TEST_SMOKE_GATES.md`](docs/TEST_SMOKE_GATES.md)
- Build and deployment -> [`packaging/README.md`](packaging/README.md)
- User-facing operations -> [`docs/MODULES_USER_GUIDE.md`](docs/MODULES_USER_GUIDE.md)
- Local setup detail -> [`docs/QMToolV7_ENTWICKLUNG.md`](docs/QMToolV7_ENTWICKLUNG.md)

Recommended reading order follows the "Mandatory Reading Order" in [`docs/OPERATIONS_CANONICAL.md`](docs/OPERATIONS_CANONICAL.md).

## Core rules (summary)

- Business logic in `modules/*` services and `qm_platform/*`; keep UI/CLI as thin adapters.
- Cross-module access only via a module's public boundary (`modules/<name>/api.py` + `contracts.py`).
- Enforce auth/roles in the service layer, not in widgets or CLI parsers.
- Verify features CLI-first before GUI integration.

## Tests and merge gates

- Run the smallest relevant layer (`tests/platform`, `tests/modules`, `tests/interfaces`, `tests/e2e_cli`),
  then broaden before finishing. Details: `.cursor/rules/00-agent-workflow.mdc`.
- Release/migration gates and CI authority: [`docs/OPERATIONS_CANONICAL.md`](docs/OPERATIONS_CANONICAL.md),
  [`docs/TEST_SMOKE_GATES.md`](docs/TEST_SMOKE_GATES.md).
- This repository has no configured linter/typechecker; do not add lint/typecheck steps ad hoc.
