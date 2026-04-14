# Test And Smoke Gates

Status: Canonical (P0)  
Valid from: 2026-04-13  
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`

Verpflichtende Vorher/Nachher-Gates für SRP- und Doku-Pakete.

## Paket-Gate (allgemein)

1. Vor Änderung:
   - Relevante Tests ausführen und Ergebnis notieren.
2. Nach Änderung:
   - Dieselben Tests erneut ausführen.
3. Abweichung:
   - Failures klassifizieren: neu eingeführt vs. bereits vorhanden.
4. Smoke:
   - Für GUI-Änderungen mindestens Login/Navigation pro Rolle validieren.

## Empfohlene Testmatrix

### Docs-only Paket
- Kein Code-Test zwingend.
- Konsistenzcheck gegen aktuelle Entry-Points/Navigation.

### Track A PyQt low-risk SRP
- `python -m pytest tests/interfaces -q`
- Manueller Role-Smoke:
  - Admin: `Start`, `Dokumentenlenkung`, `Dokumente`, `Signatur`, `Schulung`, `Einstellungen`, `Audit & Logs`, `Admin/Debug`
  - QMB: wie Admin ohne `Admin/Debug`
  - User: ohne Admin-/QMB-only Bereiche

### Track B SRP prep/splits
- `python -m pytest tests/modules -q`
- `python -m pytest tests/platform -q`
- optional fokussierte Läufe je betroffener Komponente

## Nachweisformat

Für jedes Paket im PR-/Änderungsprotokoll:
- Paketname
- Vorher-Resultat
- Nachher-Resultat
- Offene Altfehler (falls vorhanden)
- Smoke-Ergebnis (Rollen, kurz)

## Aktueller Stand (letzter Gate-Run)

- `python -m pytest tests/modules -q` -> 60 passed (1 known pypdf deprecation warning)
- `python -m pytest tests/platform -q` -> 25 passed
- `python -m pytest tests/interfaces -q` -> 8 passed
- Win32-DB-Lock-Flakes in den betroffenen Modultests wurden durch explizites Connection-Closing behoben.

## One-Run Abschluss (GUI)

- Dokumentenlenkung: JSON-Detailfelder entfernt, menschenlesbare Überblick/Workflow/Verlauf-Tabellen aktiv.
- Start-Dashboard: klickbare Karten + direkte Navigation auf Zielmodule aktiv.
- Signaturbereich: Ausgabe-Pfad wird automatisch als `_signiert.pdf` gesetzt, readonly geführt und Dateikonflikt blockiert.
- Audit & Logs: Fachliche und technische Tabellen mit Filter- und Export-Aktionen (CSV/PDF) aktiv.
- Shell: Persistenter `Admin/Debug`-Toggle über `QSettings` umgesetzt (nur Admin umschaltbar).
- Packaging-Sanity: `powershell -ExecutionPolicy Bypass -File "scripts/build_pyqt_onefile.ps1"` erfolgreich, Ausgabe `dist/QmToolPyQt.exe`.

## Role-Smoke (fokussiert)

- Ausgeführt: `python -m pytest tests/interfaces/test_pyqt_navigation_smoke.py -q`
- Ergebnis: `3 passed`
- Abgedeckt:
  - Hauptnavigation enthält alle erwarteten Einträge.
  - Rollenrestriktionen sind korrekt (`Audit & Logs` = Admin/QMB, `Admin/Debug` = Admin).
  - Benutzerverwaltung ist nicht mehr Top-Level, sondern in Einstellungen eingebettet.

## Gate-Matrix (Akribischer Lauf)

- Block A (Widgets/Shell):
  - `python -m pytest tests/interfaces -q` -> 8 passed
  - Navigation Smoke -> 3 passed
- Block B/C (Dokumentenlenkung/Dashboard/Signatur/Training/Audit):
  - `python -m pytest tests/interfaces -q` -> 8 passed
- Block D (Final):
  - `python -m pytest tests/interfaces -q` -> 8 passed
  - `python -m pytest tests/platform -q` -> 25 passed
  - `python -m pytest tests/modules -q` -> 60 passed (1 known pypdf deprecation warning)
  - Packaging: `scripts/build_pyqt_onefile.ps1` erfolgreich, EXE `dist/QmToolPyQt.exe`
