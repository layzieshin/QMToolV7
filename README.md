# QmToolPyV4 / QMToolV7

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

Diese Arbeitskopie liegt unter **QMToolV7** (siehe `docs/QMToolV7_ENTWICKLUNG.md` für Pfad, Startbefehle und Build).

CLI-first modular quality management platform transitioning to a Web + PostgreSQL target
architecture (AP-029). The productive web end-user client is **not implemented yet** (WEB00 pending).

## Python version policy

- Supported runtime: `Python 3.14.x`
- Project policy source: `pyproject.toml` (`requires-python = ">=3.14,<3.15"`)
- Recommended local setup uses constraints for reproducible installs:
  `py -3.14 -m venv .venv`
  `.\.venv\Scripts\python.exe -m pip install -c constraints-py314.txt -r requirements.txt -r requirements-pyqt.txt -r requirements-dev.txt`

## Active entry points

- CLI (operator/test): `.\.venv\Scripts\python.exe -m interfaces.cli.main`
- Backend host (transport only): `.\.venv\Scripts\python.exe -m src.backend`
- First-run init: `.\.venv\Scripts\python.exe -m interfaces.cli.main init --non-interactive --admin-password "<password>"`
- Runtime diagnostics: `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor`
- Target end-user UI: `webclient/*` after WEB00 (not implemented yet — do not invent npm/Vite commands here)
- Legacy/reference PyQt GUI (frozen; no new product work): `.\.venv\Scripts\python.exe -m interfaces.pyqt`
- UI MVP (legacy/test-only Tk): `.\.venv\Scripts\python.exe -m interfaces.gui.main`
- Legacy PyQt production build (Ist packaging): `.\.venv\Scripts\python.exe packaging/build_onedir.py` — see [`packaging/README.md`](packaging/README.md)
- PyQt onefile build (**deprecated**): `powershell -ExecutionPolicy Bypass -File "scripts/build_pyqt_onefile.ps1"`

## Architecture overview

- `qm_platform/`: runtime container, lifecycle, settings, events, licensing, logging
- `modules/`: domain modules (`documents`, `signature`, `usermanagement`, `registry`, `training`, `incident_management`)
- `src/backend/`: HTTP transport host (`/api/v1` is the target browser boundary)
- `interfaces/`: CLI operator/test adapter; frozen PyQt/Tk legacy UI
- `webclient/`: sole new end-user UI source (planned; not present until WEB00)
- `tests/`: module, e2e CLI, and smoke/regression coverage
- Productive persistence target: PostgreSQL-only (SQLite limited to inventory/import/tests)

## Key docs

- `docs/DOCS_CANONICAL_INDEX.md`
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
- `docs/MASTER_ORCHESTRATION_ROADMAP.md`
- `docs/MODULE_INTEGRATION_POLICY.md` (module onboarding for contributors)
- `docs/OPERATIONS_CANONICAL.md`
- `docs/DATABASE_EVOLUTION_POLICY.md`
- `docs/LICENSE_SPEC.md`
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
- `docs/GUI_SOURCE_OF_TRUTH.md`
- `docs/GUI_ARCHITECTURE_PROJECT.md`
- `docs/TEST_SMOKE_GATES.md`
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/MODULES_USER_GUIDE.md`
- `docs/PYQT_CONTRIBUTIONS_REFERENCE.md` (P2 Legacy/History — frozen inventory)

## Notes

- New product UI work goes to `webclient/*` after WEB00; PyQt is frozen legacy/reference.
- Runtime settings and data are stored under `storage/` unless overridden by environment/config (Ist).
- Reproducible test invocation (PowerShell): ``.\.venv\Scripts\python.exe -m pytest``.
- `docx2pdf` remains environment-dependent (Windows + installed Office/COM availability).
- Ist PyQt output: `packaging/dist_output/QM-Tool/` and `QM-Tool.zip` (see `packaging/README.md`).
- Git client choice is IDE-independent (`PyCharm`, CLI, Cursor); CI gates remain the merge authority.
