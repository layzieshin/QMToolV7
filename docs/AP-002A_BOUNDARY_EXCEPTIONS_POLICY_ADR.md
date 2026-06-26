# AP-002A Boundary-Ausnahmen-Policy ADR

## Status
- Typ: ADR / Policy-Vorlage
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-002-Inventar: `docs/AP-002_PUBLIC_BOUNDARY_VIOLATIONS_INVENTORY.md`.
- AP-002 hat 285 Import-Funde klassifiziert:
  - Kategorie A: 41 echte Public-Boundary-Verstöße in aktiven CLI-/PyQt-Adaptern.
  - Kategorie B: 1 Cross-Module-Internal-Import in `modules/training/released_document_catalog_reader.py`.
  - Kategorie C: 33 zulässige Imports.
  - Kategorie D: 210 Fälle mit Supervisor-Entscheidungsbedarf, überwiegend Tests, Legacy-GUI und Runtime-Bootstrap.
  - Kategorie E: 0 Backend-Grenzfunde.
- Geltende Grundregel: Öffentliche Python-Zugriffe auf Fachmodule laufen grundsätzlich ausschließlich über `modules/<name>/api.py`.
- Direkte Cross-Module-Imports aus Modul-Internals bleiben verboten.
- Runtime-Sonderfälle dürfen nur ausdrücklich dokumentiert und eng begrenzt werden.
- Tests dürfen keine stillschweigende öffentliche Produktiv-API etablieren.
- Diese Vorlage trifft keine automatische Architekturentscheidung und startet kein Cleanup.

## Entscheidungsvorlage 1 — Testimport-Policy

### Optionen

| Testebene | Erlaubte Importform | Verbotene Importform | `contracts.py` direkt erlaubt? | Späterer Cleanup nötig? | Supervisor-Entscheidung bleibt |
| --- | --- | --- | --- | --- | --- |
| Unit-Test innerhalb desselben Moduls | Direkte Imports aus Internals desselben Moduls, z. B. Service, Repository, Storage, Contracts. | Imports aus Internals anderer Module. | Ja, wenn der Test klar Whitebox für dasselbe Modul ist. | Nein, wenn Testpfad und Modulzuordnung eindeutig sind. | Ja, falls der Test faktisch Adapter-/Integrationstest ist. |
| Cross-Module-Test | Bevorzugt öffentliche `modules/<name>/api.py` oder Runtime-Wiring. | Direkte Imports aus Internals fremder Module. | Nein, außer ausdrücklich als Whitebox-Vertragsprüfung freigegeben. | Ja, wenn der Test externe Modulgrenzen simuliert. | Ja, bei bestehenden Tests mit gemischtem Setup. |
| Integrationstest | Öffentliche APIs, Ports, Container/Wiring über freigegebene Runtime-Pfade. | Direkte Service-/Repository-/Storage-Imports als Ersatz für Runtime-Integration. | Grundsätzlich nein. | Ja, wenn Integrationstest Internals als Produktivfläche nutzt. | Ja, für historisch gewachsene Integrationsfixtures. |
| Smoke-/Compatibility-Test | Öffentliche APIs, CLI-/GUI-Entry-Points, Runtime-Smoke-Pfade. | Direkte Modul-Internals, sofern nicht ausdrücklich als Legacy-Kompatibilität dokumentiert. | Nein. | Ja oder als Legacy-Ausnahme markieren. | Ja, besonders bei `interfaces/gui/*` und alten Smoke-Tests. |
| Legacy-Test | Bestehende interne Imports können sichtbar markiert und eingefroren bleiben. | Neue interne Imports oder Erweiterung des Legacy-Pfads. | Nur als eingefrorener Bestand, nicht als Muster für neue Tests. | Nur nach separater Freigabe. | Ja, ob markieren, archivieren oder bereinigen. |

### Empfehlung
- Tests in drei Policy-Klassen einteilen:
  1. **Modul-Whitebox-Test**: darf Internals desselben Moduls importieren.
  2. **Adapter-/E2E-/Integrationstest**: muss über `api.py`, Ports oder Runtime-Wiring gehen.
  3. **Legacy-/Compatibility-Test**: darf bestehende interne Imports behalten, muss aber sichtbar markiert bleiben und darf nicht ausgebaut werden.
- `contracts.py` ist in neuen Adapter-/E2E-/Integrationstests nicht als externe Produktiv-API zu verwenden.
- Bestehende Testimporte werden nicht automatisch bereinigt; sie werden je Testebene später separat bewertet.

### Begründung
- Modul-Whitebox-Tests brauchen Zugriff auf interne Invarianten, ohne daraus eine öffentliche Produktivgrenze zu machen.
- Adapter- und E2E-Tests sollen die echte Modulgrenze prüfen und dürfen keine direkte interne Nutzungsfläche normalisieren.
- Legacy-/Compatibility-Tests sind historisch nützlich, aber keine Vorlage für neue Architektur.

### Risiken
- Zu strikte Regeln können bestehende Whitebox-Modultests unnötig erschweren.
- Zu lockere Regeln können `contracts.py`, `service.py` oder Repository-Klassen faktisch als öffentliche API etablieren.
- Gemischte Tests können falsch klassifiziert werden und brauchen manuelle Einordnung.

### Explizite Supervisor-Entscheidung nötig
Ja. Der Supervisor muss die Testklassen und deren erlaubte Importformen bestätigen, bevor Test-Cleanup-Pakete entstehen.

## Entscheidungsvorlage 2 — Runtime-Ausnahme Bootstrap

### Optionen
1. **Keine Ausnahme**: `qm_platform/runtime/bootstrap.py` darf nicht aus `modules/*/module.py` importieren.
2. **Eng begrenzte Runtime-Ausnahme**: Nur die Runtime-Composition-Root darf `create_<module>_module_contract()` aus `modules/<name>/module.py` importieren.
3. **Breite Runtime-Ausnahme**: Runtime-Code darf beliebige Modul-Internals für Wiring importieren.

### Empfehlung
- Option 2 wählen: eng begrenzte Runtime-Ausnahme.
- `qm_platform/runtime/bootstrap.py` darf ausschließlich Modul-Contract-Factories aus `modules/<name>/module.py` importieren, um Core-Module in der Runtime zu registrieren.
- Diese Ausnahme ist kein öffentlicher Modulzugriff für Fachlogik und keine Alternative zu `modules/<name>/api.py`.

### Begründung
- Das aktuelle Runtime-Wiring nutzt `core_module_contracts()` und registriert Module über `ModuleContract`.
- Diese Composition-Root-Funktion ist infrastrukturell, nicht fachlich.
- Eine enge Ausnahme bewahrt die Architekturgrenze und vermeidet künstliche Wrapper-APIs nur für Bootstrap.

### Grenzen der Ausnahme
- Erlaubt:
  - `qm_platform/runtime/bootstrap.py` importiert `create_<module>_module_contract()` aus `modules/<name>/module.py`.
  - Nur Contract-Erzeugung, Lizenz-Tag-Ermittlung und Runtime-Registrierung.
- Verboten:
  - Imports aus `service.py`, `repository.py`, `storage.py`, `sqlite_repository.py`, `contracts.py`, `*_ops.py` oder fachlichen Helpers in `qm_platform/*`.
  - Fachliche Use-Case-Aufrufe aus `qm_platform/runtime/bootstrap.py`.
  - Nutzung von `module.py` als allgemeine öffentliche Modul-API.
  - Ausweitung der Ausnahme auf Backend, GUI, CLI oder andere Module.

### Explizite Supervisor-Entscheidung nötig
Ja. Die Ausnahme sollte ausdrücklich als Runtime-Composition-Root-Ausnahme bestätigt und dokumentiert werden.

## Entscheidungsvorlage 3 — Legacy-GUI-Funde

### Optionen
1. **Nur markieren / einfrieren**: `interfaces/gui/*` bleibt Legacy/Test, bestehende Boundary-Verletzungen werden sichtbar gehalten, aber nicht bereinigt.
2. **Später archivieren**: Legacy-GUI wird nach separater Freigabe archiviert oder aus aktiven Smoke-Pfaden entfernt.
3. **Separater Legacy-Cleanup**: Boundary-Verletzungen in `interfaces/gui/*` werden in einem eigenen Paket bereinigt.

### Empfehlung
- Option 1 kurzfristig: markieren / einfrieren.
- Option 2 als spätere Supervisor-Entscheidung offenhalten.
- Option 3 nur wählen, wenn `interfaces/gui/*` weiterhin aktiv für Smoke-/Compatibility-Tests gebraucht wird.

### Begründung
- `interfaces/gui/main.py` enthält bereits einen `LEGACY FROZEN`-Hinweis und bezeichnet Boundary-Verletzungen als akzeptierten Bestand.
- Aktive GUI-Quelle ist `interfaces/pyqt/*`.
- Cleanup im Legacy-Pfad hätte Risiko und wenig Produktnutzen, solange der Pfad nicht fachlich weiterentwickelt wird.

### Risiken
- Bestehende Legacy-Funde können bei Suchläufen weiter als Verletzungen erscheinen.
- Wenn der Legacy-Pfad weiter in Smokes genutzt wird, können alte Imports den Zielzustand verwässern.
- Archivierung oder Entfernung braucht separate Freigabe, da bestehende Compatibility-Smokes betroffen sein könnten.

### Explizite Supervisor-Entscheidung nötig
Ja. Der Supervisor muss entscheiden, ob Legacy-GUI-Funde dauerhaft markiert bleiben, später archiviert oder separat bereinigt werden.

## Entscheidungsvorlage 4 — DTOs/Enums aus contracts.py

### Optionen
1. **Explizite Bereitstellung über `api.py`**: DTOs/Enums, die externe Adapter oder andere Module brauchen, werden ausdrücklich in `modules/<name>/api.py` verfügbar gemacht.
2. **Contracts strikt intern halten**: Externe Schichten erhalten eigene API-DTOs oder Methoden, ohne direkte Contract-Typen.
3. **Direkter `contracts.py`-Import bleibt erlaubt**: `contracts.py` wird als zweite öffentliche Importfläche akzeptiert.
4. **Re-Exports über `__init__.py` oder Wrapper-APIs**: DTOs werden über Package-Root oder zusätzliche Helper-APIs bereitgestellt.

### Empfehlung
- Option 1 als Standard wählen.
- Option 2 nur für bewusst stabile externe Client-/Backend-Verträge prüfen, wenn Modul-Contracts intern bleiben müssen.
- Option 3 ablehnen, weil sie der aktuellen P0-Regel widerspricht.
- Option 4 ablehnen, weil keine Re-Exports, Wrapper-APIs oder öffentlichen Helper-APIs neben `api.py` erlaubt sind.

### Begründung
- `api.py` ist die einzige öffentliche Python-Grenze je Fachmodul.
- Einige Module exportieren bereits DTOs/Enums über `api.py`, aber AP-002 zeigt, dass Adapter weiterhin direkt auf `contracts.py` zugreifen.
- Explizite `api.py`-Bereitstellung macht die öffentliche Fläche prüfbar und begrenzt.

### Risiken
- `api.py` kann zu breit werden, wenn jedes interne DTO ungeprüft exportiert wird.
- API-Stabilität wird wichtiger, sobald DTOs offiziell öffentlich sind.
- Tests und Adapter müssen später gezielt migriert werden; das ist Cleanup und nicht Teil dieser ADR-Vorlage.
- Unterschied zwischen internen Modul-DTOs und langfristigen Backend-/Client-Verträgen muss später separat betrachtet werden.

### Explizite Supervisor-Entscheidung nötig
Ja. Der Supervisor muss bestätigen, ob externe DTO-/Enum-Nutzung standardmäßig über `api.py` läuft und ob einzelne DTOs bewusst nicht öffentlich werden sollen.

## Spätere Cleanup-Paketschnitte

### Paket 1: CLI-Adapter-Boundary-Cleanup
- Ziel: Direkte `contracts.py`-Imports in `interfaces/cli/*` auf freigegebene `api.py`-Importe umstellen.
- Scope:
  - `interfaces/cli/commands/documents_commands.py`
  - `interfaces/cli/commands/signature_commands.py`
  - `interfaces/cli/commands/incident_management_commands.py`
  - `interfaces/cli/commands/settings_commands.py`
  - `interfaces/cli/commands/users_commands.py`
  - `interfaces/cli/parsers/documents_parsers.py`
- Risiko: mittel bis hoch, weil Parser/Command-Verträge und CLI-E2E-Flows betroffen sind.
- Erforderliche Vorentscheidung:
  - DTOs/Enums aus `contracts.py` werden über `api.py` verfügbar gemacht oder bewusst anders ersetzt.

### Paket 2: PyQt-Adapter-Boundary-Cleanup für Documents/Signature
- Ziel: Direkte `contracts.py`-Imports in aktiven PyQt-Documents-/Signature-Views, Presentern und Widgets entfernen.
- Scope:
  - `interfaces/pyqt/contributions/documents_workflow*`
  - `interfaces/pyqt/presenters/documents_*`
  - `interfaces/pyqt/widgets/*` mit Documents-/Signature-DTOs
  - `interfaces/pyqt/contributions/settings_sections/signature_settings_section.py`
- Risiko: hoch, weil aktive GUI-Flows, Signaturplatzierung und Dokumentenworkflow betroffen sind.
- Erforderliche Vorentscheidung:
  - API-Exportfläche für Documents-/Signature-DTOs und betroffene GUI-Smoke-Gates festlegen.

### Paket 3: Policy-gesteuerter Testimport-Cleanup
- Ziel: Nur solche Tests bereinigen, die nach bestätigter Testimport-Policy nicht als Modul-Whitebox-Tests gelten.
- Scope:
  - Adapter-/Interface-/E2E-nahe Tests zuerst.
  - Modul-Whitebox-Tests nur markieren oder ausnehmen, sofern freigegeben.
  - Legacy-/Compatibility-Tests separat ausweisen.
- Risiko: mittel, da viele Tests betroffen sind und falsche Klassifikation Testwert zerstören kann.
- Erforderliche Vorentscheidung:
  - Testimport-Policy je Testebene und Legacy-GUI-Behandlung bestätigen.

## Nicht entschieden
- Ob `qm_platform/runtime/bootstrap.py` dauerhaft als eng begrenzte Runtime-Ausnahme gelten soll.
- Welche Testebenen direkte Modul-Internals importieren dürfen.
- Ob Adapter-/E2E-/Integrationstests konsequent auf `api.py` umgestellt werden sollen.
- Ob `interfaces/gui/*` dauerhaft nur markiert, später archiviert oder separat bereinigt werden soll.
- Welche DTOs/Enums aus `contracts.py` explizit öffentlich über `api.py` bereitgestellt werden sollen.
- Ob einzelne interne Contracts nicht öffentlich werden sollen und dafür andere API-DTOs nötig sind.
- Wie der Docstring-Konflikt in `modules/usermanagement/api.py` behandelt werden soll.
- Ob spätere Cleanup-Pakete nach Adapter, Modul oder Testebene priorisiert werden.

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-002_PUBLIC_BOUNDARY_VIOLATIONS_INVENTORY.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `qm_platform/runtime/bootstrap.py`
  - `interfaces/gui/main.py`
  - `modules/documents/api.py`
  - `modules/signature/api.py`
  - `modules/incident_management/api.py`
  - `modules/training/api.py`
  - `modules/usermanagement/api.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Prüfung, ob `docs/AP-002A_BOUNDARY_EXCEPTIONS_POLICY_ADR.md` bereits existiert.
  - Keine zusätzlichen Code-Suchläufe nötig; AP-002-Inventar war vorhanden und lesbar.
- Keine Testsuite ausgeführt, weil AP-002A ein ADR-/Dokumentationspaket ist.
- Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-002A_BOUNDARY_EXCEPTIONS_POLICY_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll die empfohlene Testimport-Policy und die eng begrenzte Runtime-Bootstrap-Ausnahme ausdrücklich annehmen, ablehnen oder ändern, bevor ein Cleanup-Paket freigegeben wird.
