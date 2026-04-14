# UI MVP (Legacy Tk) + PyQt Hinweis

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md`, `docs/GUI_SOURCE_OF_TRUTH.md`, `docs/PYQT_CONTRIBUTIONS_REFERENCE.md`

Die erste UI-Variante (Tk, Legacy/MVP) ist verfügbar unter:

- `interfaces/gui/main.py`

Start:

```bash
python -m interfaces.gui.main
```

Initialize first-run runtime structure (recommended before GUI/EXE start):

```bash
python -m interfaces.cli.main init --non-interactive --admin-password "<set-strong-password>"
```

Security note:
- Do not use default/demo credentials outside local development.
- Keep `seed_mode` hardened and rotate bootstrap credentials after initialization where required.

Runtime diagnostics:

```bash
python -m interfaces.cli.main doctor
```

Build onefile EXE (Legacy Tk):

```powershell
powershell -ExecutionPolicy Bypass -File "scripts/build_ui_exe.ps1"
```

Build plus EXE smoke:

```powershell
powershell -ExecutionPolicy Bypass -File "scripts/build_ui_exe.ps1" -RunSmoke
```

Resultat:

- `dist/QmToolUiMvp.exe`

## Aktuelle Haupt-GUI (PyQt)

Die aktive GUI-Weiterentwicklung läuft in `interfaces/pyqt/*`.

Start:

```bash
python -m interfaces.pyqt
```

PyQt onefile build:

```powershell
powershell -ExecutionPolicy Bypass -File "scripts/build_pyqt_onefile.ps1"
```

Resultat:

- `dist/QmToolPyQt.exe`

Run EXE smoke test (headless):

```powershell
dist/QmToolPyQt.exe
```

If execution from network path is blocked by local Windows security policy, copy to a local path first (for example `%TEMP%`) and run there.
To override runtime home explicitly (dev and EXE), set `QMTOOL_HOME` before start.

Module summaries:

- User perspective: `docs/MODULES_USER_GUIDE.md`
- Developer perspective: `docs/MODULES_DEVELOPER_GUIDE.md`
- Canonical operations entry: `docs/OPERATIONS_CANONICAL.md`

## Included MVP Functions (Legacy Tk only)

- Login / Logout (session-bound)
- Documents tab:
  - Create version
  - Assign roles
  - Start workflow
  - Complete editing
  - Review accept
  - Approval accept
  - Abort workflow
  - Archive
  - Load details
  - Pool list (`PLANNED`)
- Settings tab:
  - List modules with settings contribution
  - Get module settings
  - Set module settings via JSON
- Users tab:
  - Create user
  - List users
- Output:
  - permanent output panel at the bottom of the main window
  - optional separate always-on-top output popout

PyQt uses a different shell/navigation architecture and should not be described with the legacy tab/output pattern above.

## Notes

- The UI uses the same runtime ports/services as CLI and keeps authorization checks active.
- Signature-required transitions can use sign fields in the Documents tab.
- Output/errors are mirrored through one pipeline into bottom panel and optional popout.
