# Container-Arbeitsbereich – Single-Unit-Bedienanleitung

## Ziel

Der Arbeitsbereich zeigt ein veröffentlichtes Container-Modul aus Sicht eines
Endnutzers. Navigation, Objektbaum, Suche, dynamische Datenfelder,
Statusübergänge, Nachweise und Dateien werden aus der vom Backend gelieferten
Moduldefinition aufgebaut. Die Weboberfläche ist eine UX- und
Integrationsblaupause; die kanonische Produkt-GUI des QM-Tools bleibt PyQt.

Die Single-Unit-Demo startet Backend und Weboberfläche in einem lokalen Prozess
und verwendet eine isolierte SQLite-Datenbank. Dadurch lässt sich der komplette
Pfad testen, ohne eine laufende QMTool-Installation zu benötigen.

## Voraussetzungen

- Python 3.12 und die Projektabhängigkeiten sind installiert.
- Der Befehl wird im Repository-Wurzelverzeichnis ausgeführt.
- Port `8765` ist lokal frei.
- Der Browser läuft auf demselben Rechner.
- Die Demo wird nicht nach außen freigegeben. Sie bindet bewusst nur an
  `127.0.0.1` und ersetzt die Produktionsanmeldung durch eine klar markierte
  lokale Testidentität.

Für die spätere Einbindung in das QM-Tool setzt dieselbe UI-Architektur voraus:

1. Das Container-Modul ist in der Backend-Komposition verdrahtet und seine
   Migration wurde über den zentralen Database-Evolution-Pfad ausgeführt.
2. `container_api`, backend-eigene Artifact-Ablage, Event Bus, Audit/Logging,
   Settings und der Usermanagement-Service stehen als Runtime-Ports bereit.
3. Ein echter Request wird durch Usermanagement zu einem bestätigten
   `UserContext` aufgelöst. Der Client sendet keine Rollen und erzeugt keinen
   eigenen Actor.
4. UI und API werden gleich-origin oder über eine entsprechend abgesicherte
   Produktintegration bereitgestellt. Das Backend bleibt für jede
   Berechtigungs- und Policyentscheidung maßgeblich.

Die Single-Unit-Demo erfüllt dieselben Modul- und HTTP-Grenzen, ersetzt aber
Punkt 3 ausschließlich lokal durch `issue_local_demo_context()`.

## 1. Demo starten

Windows/PowerShell:

```powershell
.\.venv\Scripts\python.exe -m src.backend.container_demo --app-home .\build\container-demo --port 8765
```

Linux/macOS:

```bash
python -m src.backend.container_demo --app-home build/container-demo --port 8765
```

Im Browser öffnen:

```text
http://127.0.0.1:8765/container/demo
```

`/container/demo` leitet auf `/container/app` weiter. Oben muss der Hinweis
**„Single-Unit-Testbetrieb · lokale Identität · keine
Produktionsanmeldung“** erscheinen. **Modulwerkstatt** öffnet die
administrative Testoberfläche, **API** die Swagger-Dokumentation.

## 2. Beim ersten Start ein Modul veröffentlichen

Ein frisches `--app-home` enthält noch kein fachliches Modul. Dann zeigt der
Arbeitsbereich **„Noch kein Modul veröffentlicht“**.

1. Auf **Modulwerkstatt öffnen** klicken.
2. Im mitgelieferten Gerätemanagement-Beispiel den Modulschlüssel bei Bedarf
   eindeutig machen, etwa `device-management-test-01`.
3. Auf **Prüfen** klicken und die grüne serverseitige Rückmeldung abwarten.
4. Auf **Veröffentlichen** klicken und bestätigen.
5. Links unten **Endnutzeransicht öffnen →** wählen.
6. Im Arbeitsbereich auf **Aktualisieren** klicken, falls das Modul nicht
   bereits angezeigt wird.

Das veröffentlichte Modul und spätere Testdaten bleiben bei einem Neustart mit
demselben `--app-home` erhalten.

## 3. Modul und Objektbaum bedienen

- Unter **Module** links ein veröffentlichtes Modul auswählen.
- Die Modulstartseite zeigt Beschreibung, Bausteinanzahl und sichtbare
  Haupteinträge.
- Mit **＋ Neuer Haupteintrag** ein dynamisches Formular öffnen, Pflichtfelder
  ausfüllen und **Anlegen** wählen.
- Der neue Eintrag erscheint unter **Inhalte**. Einträge lassen sich über den
  Pfeil ein- und ausklappen und durch Anklicken öffnen.

Welche Module, Root-Objekte und Anlegeoptionen erscheinen, entscheidet
`GET /container/runtime-modules` serverseitig für die bestätigte Sitzung.
Unsichtbare Felder und nicht zulässige Übergänge werden nicht an die UI
geliefert.

## 4. Daten pflegen

1. Einen Eintrag im Baum öffnen.
2. **Bearbeiten** wählen.
3. Text, Zahlen, Datum, Ja/Nein, Einfach- oder Mehrfachauswahl bzw. Referenz-UID
   eintragen.
4. **Speichern** wählen.

Der Request enthält die aktuelle Revision. Wurde derselbe Eintrag inzwischen
geändert, lehnt das Backend den veralteten Stand ab; **Aktualisieren** lädt die
neue Revision.

## 5. Untereinträge anlegen

Wenn die Strukturdefinition und die Berechtigung es erlauben:

1. Im geöffneten Eintrag **＋ Untereintrag** wählen.
2. Bei mehreren zulässigen Bausteinen den Typ auswählen.
3. Felder ausfüllen und **Anlegen** wählen.

Automatisch erzeugte feste Untereinträge erscheinen ebenfalls im Baum. Das
Backend erzwingt Kardinalität, maximale Tiefe und feste Struktur; die
Oberfläche bildet Ablehnungen nur verständlich ab.

## 6. Status ändern und Verlauf prüfen

Zulässige Übergänge stehen als Schaltflächen mit dem Zielstatus neben den
anderen Aktionen. Bei einem Übergang fordert das Formular die im Blueprint
festgelegte Begründung bzw. Signaturbedeutung an. Nicht zulässige Übergänge
werden nicht dargestellt und bleiben unabhängig davon backendseitig gesperrt.

Unter **Aktivitätsverlauf** auf **Verlauf laden** klicken, um die sichtbaren
Audit-Einträge des Objekts abzurufen. **Archivieren** macht einen Objektzweig
schreibgeschützt; **Reaktivieren** steht nur bei entsprechender
Backendentscheidung zur Verfügung.

## 7. Nachweise und Dateien

1. Im Objekt unter **Nachweise & Dateien** auf **＋ Nachweis** klicken.
2. Nachweistyp auswählen, Metadaten ausfüllen und **Anlegen** wählen.
3. Die Nachweiskarte öffnen.
4. Optional Metadaten ändern oder über **Datei hinzufügen** eine lokale Datei
   mit höchstens 10 MB hochladen.
5. Den Download über **Laden** gegenprüfen.
6. Mit **Finalisieren** den unveränderlichen Snapshot erzeugen.
7. Optional **Signieren** und eine Signaturbedeutung angeben.
8. Für einen finalisierten Nachweis kann **Korrektur anlegen** eine neue,
   explizit verknüpfte Arbeitskopie erzeugen.

Nach der Finalisierung blendet die UI Schreibfelder aus. Die Unveränderlichkeit
wird zusätzlich und verbindlich im Container-Service geprüft.

## 8. Suche und Export

- In **Im Modul suchen …** einen Wert eines als `searchable` veröffentlichten
  Feldes eingeben und Enter drücken. Die UI begrenzt die permission-gefilterten
  Treffer auf die Template-Versionen des ausgewählten Moduls.
- **Export** lädt den sichtbaren Objekt-Unterbaum über den öffentlichen
  Export-Endpunkt als ZIP-Datei. Die Export-Policy wird im Backend geprüft.

## 9. Fehlerbild und Zurücksetzen

| Beobachtung | Prüfung |
| --- | --- |
| Kein Modul sichtbar | In der Modulwerkstatt veröffentlichen; danach **Aktualisieren**. |
| Aktion fehlt | `allowed_actions` bzw. die actor-gefilterte Laufzeitprojektion erlaubt sie nicht. |
| „Revision wurde geändert“ | Ansicht aktualisieren und Eingabe auf Basis der neuen Revision wiederholen. |
| Nachweis nicht bearbeitbar | Prüfen, ob er finalisiert oder sein Objekt archiviert ist. |
| Daten nach Neustart weg | Mit demselben absoluten bzw. relativen `--app-home` starten. |

Für einen vollständigen lokalen Reset den laufenden Demo-Prozess beenden und
ausschließlich den bewusst gewählten Ordner `build/container-demo` entfernen.
Keine Produktions- oder andere Testablage löschen.

## 10. Architekturgrenze des Prototyps

- Die statischen Routen `/container/app` und `/container/admin` werden nur von
  `src.backend.container_demo` eingebunden. Die Produktionsform von
  `src.backend.api.create_app` stellt weiterhin ausschließlich authentifizierte
  Container-HTTP-Routen bereit.
- Die Weboberfläche importiert keine Modul-Infrastruktur, öffnet keine
  Datenbank und kennt keine Rollencodes. Sie verwendet ausschließlich
  öffentliche HTTP-DTOs, `allowed_actions` und stabile Fehlercodes.
- Die Demo ist noch keine produktive Auth-, Mandanten-, Signatur- oder
  Deploymentlösung. Für die Produktintegration bleiben Session-Auflösung,
  CSRF-/Browser-Sicherheitskonzept, PyQt-Einbettung bzw. freigegebener Web-Host
  und die im Arbeitsplan dokumentierten Usermanagement-/ACL-Lücken offen.

## Verifizierter Dokumentationspfad

Die Anleitung wird gegen die echte Route, sichtbare Beschriftungen,
HTTP-Projektion, Restart-Persistenz und Produktionsabgrenzung geprüft:

- `tests/backend/test_container_user_ui.py`
- `tests/backend/test_container_runtime_routes.py`
- `tests/modules/container/test_container_m6_runtime_projection.py`
- `tests/backend/test_container_blueprint_routes.py`

Zusätzlich werden beide JavaScript-Dateien mit `node --check`, die Python-
Quellen mit `compileall`, die Migrationen mit dem Database-Migration-Gate und
der Single-Unit-Prozess per HTTP-Smoke-Test geprüft.
