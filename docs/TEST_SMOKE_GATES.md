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
- `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q`
- Manueller Role-Smoke:
  - Admin: `Start`, `Dokumentenlenkung`, `Dokumente`, `Signatur`, `Schulung`, `Einstellungen`, `Audit & Logs`, `Admin/Debug`
  - QMB: wie Admin ohne `Admin/Debug`
  - User: ohne Admin-/QMB-only Bereiche

### Track B SRP prep/splits
- `.\.venv\Scripts\python.exe -m pytest tests/modules -q`
- `.\.venv\Scripts\python.exe -m pytest tests/platform -q`
- optional fokussierte Läufe je betroffener Komponente

## Nachweisformat

Für jedes Paket im PR-/Änderungsprotokoll:
- Paketname
- Vorher-Resultat
- Nachher-Resultat
- Offene Altfehler (falls vorhanden)
- Smoke-Ergebnis (Rollen, kurz)

## Aktueller Stand (historischer Snapshot, 2026-04)

Die folgenden Zahlen stammen aus einem früheren Gate-Run und dienen nur als Referenz.
Für aktuelle Verifikation immer die Befehle in `.cursor/rules/00-agent-workflow.mdc` und CI ausführen.

- `.\.venv\Scripts\python.exe -m pytest tests/modules -q` -> 60 passed (1 known pypdf deprecation warning)
- `.\.venv\Scripts\python.exe -m pytest tests/platform -q` -> 25 passed
- `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q` -> 8 passed
- Win32-DB-Lock-Flakes in den betroffenen Modultests wurden durch explizites Connection-Closing behoben.

## One-Run Abschluss (GUI)

- Dokumentenlenkung: JSON-Detailfelder entfernt, menschenlesbare Überblick/Workflow/Verlauf-Tabellen aktiv.
- Start-Dashboard: klickbare Karten + direkte Navigation auf Zielmodule aktiv.
- Signaturbereich: Ausgabe-Pfad wird automatisch als `_signiert.pdf` gesetzt, readonly geführt und Dateikonflikt blockiert.
- Audit & Logs: Fachliche und technische Tabellen mit Filter- und Export-Aktionen (CSV/PDF) aktiv.
- Shell: Persistenter `Admin/Debug`-Toggle über `QSettings` umgesetzt (nur Admin umschaltbar).
- Packaging-Sanity: `.\.venv\Scripts\python.exe packaging/build_onedir.py` erfolgreich; Ausgabe `packaging/dist_output/QM-Tool/` + `QM-Tool.zip`; `verify_bundle_imports.py` bestätigt `fitz`/PyMuPDF im Bundle.

## Role-Smoke (fokussiert)

- Ausgeführt: `.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_pyqt_navigation_smoke.py -q`
- Ergebnis: `3 passed`
- Abgedeckt:
  - Hauptnavigation enthält alle erwarteten Einträge.
  - Rollenrestriktionen sind korrekt (`Audit & Logs` = Admin/QMB, `Admin/Debug` = Admin).
  - Benutzerverwaltung ist nicht mehr Top-Level, sondern in Einstellungen eingebettet.

## Gate-Matrix (Akribischer Lauf)

- Block A (Widgets/Shell):
  - `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q` -> 8 passed
  - Navigation Smoke -> 3 passed
- Block B/C (Dokumentenlenkung/Dashboard/Signatur/Training/Audit):
  - `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q` -> 8 passed
- Block D (Final):
  - `.\.venv\Scripts\python.exe -m pytest tests/interfaces -q` -> 8 passed
  - `.\.venv\Scripts\python.exe -m pytest tests/platform -q` -> 25 passed
  - `.\.venv\Scripts\python.exe -m pytest tests/modules -q` -> 60 passed (1 known pypdf deprecation warning)
  - Packaging: `.\.venv\Scripts\python.exe packaging/build_onedir.py` erfolgreich; `packaging/dist_output/QM-Tool.zip`; Import-Gate `verify_bundle_imports.py` grün
