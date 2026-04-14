# QmToolPyV4 / QMToolV7

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

Diese Arbeitskopie liegt unter **QMToolV7** (siehe `docs/QMToolV7_ENTWICKLUNG.md` für Pfad, Startbefehle und Build).

CLI-first modular quality management platform.

## Python version policy

- Supported runtime: `Python 3.14.x`
- Project policy source: `pyproject.toml` (`requires-python = ">=3.14,<3.15"`)
- Recommended local setup uses constraints for reproducible installs:
  `python -m pip install -c constraints-py314.txt -r requirements.txt -r requirements-pyqt.txt`

## Active entry points

- CLI: `python -m interfaces.cli.main`
- PyQt GUI (current): `python -m interfaces.pyqt`
- UI MVP (legacy/test-only): `python -m interfaces.gui.main`
- First-run init: `python -m interfaces.cli.main init --non-interactive --admin-password "<password>"`
- Runtime diagnostics: `python -m interfaces.cli.main doctor`
- PyQt onefile build: `powershell -ExecutionPolicy Bypass -File "scripts/build_pyqt_onefile.ps1"`

## Architecture overview

- `qm_platform/`: runtime container, lifecycle, settings, events, licensing, logging
- `modules/`: domain modules (`documents`, `signature`, `usermanagement`, `registry`, `training`)
- `interfaces/`: CLI and UI adapters (`pyqt` current, `gui` legacy)
- `tests/`: module, e2e CLI, and smoke/regression coverage

## Key docs

- `docs/DOCS_CANONICAL_INDEX.md`
- `docs/OPERATIONS_CANONICAL.md`
- `docs/CLI_FIRST_MIGRATION.md`
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
- `docs/GUI_SOURCE_OF_TRUTH.md`
- `docs/TEST_SMOKE_GATES.md`
- `docs/PYQT_CONTRIBUTIONS_REFERENCE.md`
- `docs/QMToolV7_ENTWICKLUNG.md`
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/MODULES_USER_GUIDE.md`

## Notes

- Legacy GUI-first architecture paths were removed as part of the CLI-first migration.
- Runtime settings and data are stored under `storage/` unless overridden by environment/config.
- Reproducible test invocation (PowerShell): ``$env:PYTHONPATH="."; python -m pytest``.
- `docx2pdf` remains environment-dependent (Windows + installed Office/COM availability).
- Current onefile output path for PyQt builds: `dist/QmToolPyQt.exe`.
- GUI source of truth: `interfaces/pyqt/*` (legacy Tk UI is only for compatibility tests).
- Existing UI smoke test coverage is currently legacy Tk-focused (`tests/interfaces/test_ui_mvp_smoke.py`); PyQt role-smokes are tracked in the current SRP/docs workstream.
- Git client choice is IDE-independent (`PyCharm`, CLI, Cursor); CI gates remain the merge authority.
