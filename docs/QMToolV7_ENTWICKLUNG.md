# QMToolV7 — Arbeitskopie für Weiterentwicklung

Dieses Verzeichnis ist die **schlanke Projekt-Arbeitskopie** (aus QmToolPyV4 übernommen) für Entwicklung, Tests, Dokumentation und Build der aktuellen Architektur (CLI-first, modulare Domäne, PyQt-Shell).

## Pfad

- Empfohlener UNC-Pfad: `\\SERVINGLUNATIX\extstorage\Projekte\QMToolV7`
- Lokal kann derselbe Pfad anders gemappt sein; als Projektroot immer dieses Verzeichnis verwenden.

## Was hier bewusst fehlt (wird bei Bedarf erzeugt)

- **`storage/`**, **`databases/`**, **`dist/`**, **`build/`** — entstehen beim ersten Lauf, bei Init oder beim PyInstaller-Build.
- Keine produktiven Nutzerdaten im Repo; Entwicklung mit frischer oder eigener `QMTOOL_HOME`-Umgebung.

## Schnellstart

### Python-Version

- Unterstützt und CI-getestet: `Python 3.14.x`
- Verbindliche Projektvorgabe: `pyproject.toml` mit `requires-python = ">=3.14,<3.15"`

### Abhängigkeiten

```text
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints-py314.txt -r requirements.txt -r requirements-pyqt.txt -r requirements-dev.txt
```

### Einstiegspunkte

| Zweck | Befehl (im Projektroot) |
|--------|-------------------------|
| CLI | `.\.venv\Scripts\python.exe -m interfaces.cli.main` |
| PyQt-GUI | `.\.venv\Scripts\python.exe -m interfaces.pyqt` |
| Tk-UI-MVP (Tests/Legacy) | `.\.venv\Scripts\python.exe -m interfaces.gui.main` |
| Erst-Init (nicht-interaktiv) | `.\.venv\Scripts\python.exe -m interfaces.cli.main init --non-interactive --admin-password "<passwort>"` |
| Diagnose | `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor` |

### Tests

```text
.\.venv\Scripts\python.exe -m pytest
```

Hinweis: `pytest.ini` setzt den Projektroot als Import-Basis; nutze trotzdem den expliziten `.venv`-Interpreter.
Zusatz: `docx2pdf` ist weiterhin Office/COM-abhängig und kann auf minimalen CI-/VM-Umgebungen eingeschränkt sein.

### Windows-Build (PyQt, Onedir + ZIP)

Primärer Produktions-Build (siehe `packaging/README.md`):

```text
.\.venv\Scripts\python.exe packaging/build_onedir.py
```

Ausgabe: `packaging/dist_output/QM-Tool/` (Ordner mit `QM-Tool.exe`, `_internal/`) und `packaging/dist_output/QM-Tool.zip`. Der Build führt automatisch `packaging/verify_customer_bundle.py` und `packaging/verify_bundle_imports.py` als Gates aus.

Hinweis: Das frühere Onefile-Skript `scripts/build_pyqt_onefile.ps1` (`dist\QmToolPyQt.exe`) ist **deprecated** und sollte nicht mehr für Releases verwendet werden.

### Schnelltest (PyQt)

1. Bundle bauen: `.\.venv\Scripts\python.exe packaging/build_onedir.py`
2. EXE starten: `packaging\dist_output\QM-Tool\QM-Tool.exe`
3. Bei Startproblemen:
- zuerst `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor` ausführen
- Lizenz-/Modulstatus in der GUI unter `Einstellungen -> Lizenzverwaltung` prüfen
- auf Netzwerkpfaden ggf. EXE lokal testen (Defender/Policy-Einfluss)

## Aktuelle PyQt-Hauptnavigation (Stand GUI-Feinschliff)

- `Start`
- `Dokumentenlenkung`
- `Dokumente`
- `Signatur`
- `Schulung`
- `Einstellungen`
- `Audit & Logs` (rollenabhängig)
- `Admin/Debug` (nur Admin)

Hinweis: `Benutzerverwaltung` ist kein eigener Hauptnavigationspunkt mehr und wird innerhalb von `Einstellungen` eingebettet.
Zusatz: `Admin/Debug` ist für Admins persistent ein-/ausblendbar (`Ansicht -> Admin/Debug anzeigen`).

## Letzter One-Run Fortschritt

- Dokumentenlenkung nutzt lesbare Tabellen statt JSON-Rohsichten in Überblick/Workflow/Verlauf.
- Dokumentenlenkung erzwingt Signaturausfuehrung fuer signaturpflichtige Uebergaenge und fuer Jahresverlaengerung; ohne Signatur-API wird der Schritt sauber blockiert.
- Signatur-Fallback sucht PDF-Artefakte bevorzugt aus aktuellen Artefakten; DOCX->PDF-Fallback nutzt `docx2pdf` unter Windows und meldet fehlende Voraussetzungen klar.
- Start-Dashboard nutzt klickbare Arbeitskarten mit Navigation in `Dokumentenlenkung`, `Dokumente` und `Schulung`.
- Signaturbereich setzt Ausgabe automatisch (`_signiert.pdf`), blockiert existierende Zieldateien und bietet Canvas-Zeichnen für Signaturen.
- Audit-&-Logs-Ansicht nutzt Tabellen + Filter + CSV/PDF-Export auf Basis `log_query_service`.
- Produktions-Build auf Onedir + ZIP umgestellt: `packaging/dist_output/QM-Tool/` und `QM-Tool.zip` (Onefile deprecated).

## Dokumentation (Überblick)

| Thema | Datei |
|--------|--------|
| Module, Ports, Governance | `docs/MODULES_DEVELOPER_GUIDE.md` |
| CLI-Nutzung | `docs/DOCUMENTS_CLI_REFERENCE.md`, `docs/MODULES_USER_GUIDE.md` |
| Betrieb / kanonische Abläufe | `docs/OPERATIONS_CANONICAL.md` |
| Architektur / Migration | `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`, `docs/CLI_FIRST_MIGRATION.md` |

## CI

Workflow-Definition: `.github/workflows/ci-gates.yml` (gleicher Stand wie im Ursprungsrepo; bei Bedarf Pfade/Runner anpassen).
Der Workflow prüft Python `3.11` bis `3.14`; für Entwicklungsarbeit ist `3.14` die Referenzversion.

## Git-Workflow in IDEs

Git-Operationen können mit `PyCharm`, CLI oder Cursor durchgeführt werden. Maßgeblich für Qualität und Merge-Freigabe sind weiterhin die CI-Gates.
