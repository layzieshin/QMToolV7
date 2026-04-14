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
python -m pip install -c constraints-py314.txt -r requirements.txt -r requirements-pyqt.txt
```

### Einstiegspunkte

| Zweck | Befehl (im Projektroot) |
|--------|-------------------------|
| CLI | `python -m interfaces.cli.main` |
| PyQt-GUI | `python -m interfaces.pyqt` |
| Tk-UI-MVP (Tests/Legacy) | `python -m interfaces.gui.main` |
| Erst-Init (nicht-interaktiv) | `python -m interfaces.cli.main init --non-interactive --admin-password "<passwort>"` |
| Diagnose | `python -m interfaces.cli.main doctor` |

### Tests

```text
$env:PYTHONPATH="."
python -m pytest
```

Hinweis: Auf einigen Umgebungen wird der Projektroot ohne gesetztes `PYTHONPATH` nicht immer automatisch als Import-Basis erkannt.
Zusatz: `docx2pdf` ist weiterhin Office/COM-abhängig und kann auf minimalen CI-/VM-Umgebungen eingeschränkt sein.

### Windows-Onefile-EXE (PyQt)

```text
powershell -ExecutionPolicy Bypass -File scripts\build_pyqt_onefile.ps1
```

Ausgabe: `dist\QmToolPyQt.exe` (lokaler Build unter `%LOCALAPPDATA%\QmToolPyQtBuild` wird bei Erfolg ins Projekt-`dist` kopiert). Bei Defender/Share-Problemen: Ausnahmen für den Build-Ordner siehe Kommentare in `qm_tool_pyqt.spec` / Build-Skript.

### Onefile-Schnelltest (PyQt)

1. EXE bauen:

```text
powershell -ExecutionPolicy Bypass -File scripts\build_pyqt_onefile.ps1
```

2. EXE starten:

```text
dist\QmToolPyQt.exe
```

3. Bei Startproblemen:
- zuerst `python -m interfaces.cli.main doctor` ausführen
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
- Start-Dashboard nutzt klickbare Arbeitskarten mit Navigation in `Dokumentenlenkung`, `Dokumente` und `Schulung`.
- Signaturbereich setzt Ausgabe automatisch (`_signiert.pdf`), blockiert existierende Zieldateien und bietet Canvas-Zeichnen für Signaturen.
- Audit-&-Logs-Ansicht nutzt Tabellen + Filter + CSV/PDF-Export auf Basis `log_query_service`.
- Onefile-Build erfolgreich getestet: `dist\QmToolPyQt.exe`.

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
