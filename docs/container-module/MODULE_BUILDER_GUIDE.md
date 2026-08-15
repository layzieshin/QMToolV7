# Modulwerkstatt – Bedien- und Prüfanleitung

## Zweck und Sicherheitsgrenze

Die Modulwerkstatt ist eine lokale administrative Testoberfläche für das
backend-only Container-Modul. Mit ihr wird ein fachliches Modul aus
Objekt-, Nachweis-, Feld-, Struktur- und Lifecycle-Bausteinen zusammengestellt.
Die Oberfläche ist eine UX-Blaupause: blockbasierte Bearbeitung in der Mitte,
Navigation links und Eigenschaften/Serverprüfung rechts.

Sie wird ausschließlich durch `src.backend.container_demo` eingebunden. Die
produktive Backend-App und die bestehende PyQt-GUI erhalten dadurch keine
zweite GUI-Quelle. Die Demo besitzt einen bestätigten lokalen Admin-Kontext
ohne Produktionsanmeldung und darf deshalb nicht im Netzwerk veröffentlicht
werden; der Start bindet ausschließlich an `127.0.0.1`.

## 1. Starten

Im Repository unter Windows/PowerShell:

```powershell
.\.venv\Scripts\python.exe -m src.backend.container_demo --app-home .\build\container-demo --port 8765
```

Anschließend im Browser öffnen:

```text
http://127.0.0.1:8765/container/admin
```

Oben muss der dunkle Hinweis **„Lokale Testoberfläche · keine
Produktionsanmeldung“** sichtbar sein. Swagger bleibt parallel unter
`http://127.0.0.1:8765/docs` verfügbar.

## 2. Grundaufbau

| Bereich | Bedienung |
| --- | --- |
| Linke Seitenleiste | Wechsel zwischen **Struktur** und **Testlauf**, Auswahl der Bausteine und Anzeige bereits veröffentlichter Module. |
| Mittlere Arbeitsfläche | Notion-artige Blöcke für Datenfelder, Unterstrukturen, Status und Übergänge. |
| Rechte Eigenschaften | Name, technischer Schlüssel, Art, Haupteintrag, Erstellerrollen und verbindliches Ergebnis der Serverprüfung. |
| Obere Aktionsleiste | JSON-**Import/Export**, **Prüfen** und **Veröffentlichen**. |

Der aktuelle Entwurf wird nach jeder Änderung im lokalen Browserspeicher
gesichert. Das ist nur Entwurfskomfort; die veröffentlichte Definition liegt
relational im Container-Backend.

## 3. Modul benennen

1. Den großen Seitentitel anklicken und einen verständlichen Namen eingeben,
   beispielsweise `Gerätemanagement`.
2. Darunter den Zweck als freien Text beschreiben.
3. Im Metafeld **Schlüssel** einen dauerhaften technischen Schlüssel setzen.
   Er beginnt mit einem Kleinbuchstaben und enthält ausschließlich `a-z`,
   `0-9`, `_` oder `-`, beispielsweise `device-management-test-01`.

Ein veröffentlichter Modulschlüssel kann nicht erneut verwendet werden. Für
einen weiteren Test wird ein neuer Schlüssel gewählt. Das verhindert
versehentliche Doppelveröffentlichungen.

## 4. Bausteine anlegen

Über **＋ Objekt** bzw. **＋ Nachweis** in der linken Seitenleiste werden neue
Bausteine angelegt.

- **Objekt**: rekursiv strukturierbarer Container, zum Beispiel Gerät,
  Wartungen oder Reparaturen.
- **Nachweis**: Artifact-Template für fachliche Nachweise und optional mehrere
  Dateien, zum Beispiel Wartungsbericht oder Serviceprotokoll.

Nach Auswahl eines Bausteins werden rechts Name, technischer Schlüssel,
Bausteinart und Erstellerrollen bearbeitet. Genau ein Objekt wird als
**Haupteintrag** markiert. Aus diesem Template erzeugt der spätere Testlauf
das erste fachliche Objekt.

## 5. Datenfelder zusammenstellen

1. Den gewünschten Baustein links auswählen.
2. In **Datenfelder** auf **＋ Feld** klicken.
3. Einen eindeutigen technischen Feldschlüssel eintragen, etwa
   `serial_number`.
4. Den Feldtyp auswählen.
5. Unter dem Feld die benötigten Eigenschaften aktivieren.
6. Mit `↑` und `↓` die Reihenfolge ändern oder mit `×` entfernen.

Unterstützte Feldtypen:

| Gruppe | Typen |
| --- | --- |
| Text | Kurzer Text, langer Text |
| Zahl | Ganzzahl, Dezimalzahl |
| Zeit/Wahrheit | Ja/Nein, Datum, Datum & Uhrzeit |
| Auswahl | Einfachauswahl, Mehrfachauswahl; Werte werden kommasepariert gepflegt |
| Referenz | Benutzer-, Objekt- und Nachweisverweis |

Feldeigenschaften wie **Pflichtfeld**, **Suchbar**, **Druckbar**,
**Prüfrelevant**, **Historisiert**, **Verlinkbar**, **Bearbeitbar** und
**Sichtbar** werden vollständig an das Backend übertragen. Die Oberfläche
entscheidet daraus keine Berechtigungen oder Fachregeln selbst.

## 6. Unterstruktur verbinden

Unterstrukturen stehen nur bei Objekt-Bausteinen zur Verfügung.

1. Zuerst mindestens zwei Objekt-Bausteine anlegen, beispielsweise `Gerät`
   und `Wartungen`.
2. `Gerät` auswählen und unter **Unterstruktur** auf **＋ Verbindung** klicken.
3. Als Ziel `Wartungen` auswählen.
4. Minimum/Maximum festlegen.
5. Optional **Automatisch anlegen** aktivieren.
6. Den Strukturmodus wählen:
   - **Flexibel**: Unterobjekte dürfen gemäß Berechtigung verschoben werden.
   - **Fest**: automatisch erzeugter Strukturknoten bleibt fest gebunden.
   - **Wartung**: fachlich markierter Wartungszweig.

Kreisbezüge wie `A → B → A` werden bei **Prüfen** serverseitig abgelehnt. Das
gilt auch für automatisch anzulegende Pflicht-Unterobjekte mit eigenen
Pflichtfeldern: Ohne Defaultwerte könnten diese Felder bei der automatischen
Anlage nicht ausgefüllt werden. Die notwendige Veröffentlichungsreihenfolge
berechnet das Backend automatisch.

## 7. Status und Übergänge definieren

Ohne Statusblöcke verwendet ein Template automatisch `ACTIVE`.

1. Mit **＋ Status** mindestens einen weiteren Status ergänzen.
2. Einen Status als **Startstatus** markieren.
3. Ab zwei Statuswerten mit **＋ Übergang** einen erlaubten Wechsel anlegen.
4. Quell- und Zielstatus sowie erlaubte Rollen festlegen.
5. Bei Bedarf **Begründung** und/oder **Signatur** verpflichtend machen.

Das Backend prüft eindeutige Statuswerte, genau einen Startstatus, gültige
Übergänge und die Rollen später bei jeder Zustandsänderung erneut.

## 8. Prüfen

Auf **Prüfen** klicken. Die rechte Spalte zeigt anschließend entweder:

- **Bereit zur Veröffentlichung** samt berechneter Reihenfolge oder
- eine konkrete Liste offener Punkte.

Typische Ablehnungen sind ein doppelter Schlüssel, ein fehlender
Haupteintrag, ein Verweis auf einen gelöschten Baustein, eine Kreisstruktur
oder ein unvollständiger Lifecycle. Diese Prüfung wird vom öffentlichen
Container-Use-Case geliefert; grüne Darstellung im Browser allein reicht
nicht aus.

## 9. Import und Export

- **Export** lädt den aktuellen, noch bearbeitbaren Entwurf als JSON herunter.
- **Import** liest einen solchen JSON-Entwurf ein und lässt ihn anschließend
  sofort vom Backend prüfen.
- **Beispiel wiederherstellen** in der rechten Spalte ersetzt ausschließlich
  den lokalen Entwurf durch ein Gerätemanagement-Beispiel.

Import/Export erzeugen noch keine veröffentlichten Templates und umgehen
keine Servervalidierung.

## 10. Veröffentlichen

1. Nach erfolgreicher Prüfung auf **Veröffentlichen** klicken.
2. Den Bestätigungsdialog akzeptieren.
3. Auf die grüne Rückmeldung **Modul veröffentlicht** warten.

Alle Templates, Felder, Rollen, Strukturen und Lifecycles werden in einer
einzigen Datenbanktransaktion angelegt und in Abhängigkeitsreihenfolge
veröffentlicht. Bei einem Fehler bleibt kein halb veröffentlichtes Modul
zurück. Veröffentlichte Template-Versionen sind unveränderlich.

## 11. Menschlicher Funktionstest

1. Links auf **Testlauf** wechseln.
2. Die für den Haupteintrag angezeigten Felder ausfüllen. Pflichtfelder sind
   mit `*` markiert.
3. Auf **… anlegen** klicken.
4. UID, Status und Revision der erzeugten Testinstanz kontrollieren.

Das Objekt wird tatsächlich über `POST /container/objects` unter dem echten
WorkspaceRoot der lokalen Demo angelegt. Automatisch konfigurierte feste
Unterobjekte werden dabei ebenfalls vom Service erzeugt. Weitere fachliche
Operationen können anschließend in Swagger geprüft werden.

## 12. Zurücksetzen und Neustart

- Ein Browser-Neustart erhält den lokalen Entwurf.
- Ein Backend-Neustart mit demselben `--app-home` erhält veröffentlichte
  Module und Testinstanzen.
- Nur für einen vollständigen lokalen Neustart darf der konkret gewählte
  Demo-Ordner `build/container-demo` entfernt und neu gestartet werden.

## Verifizierter Dokumentationspfad

Der oben beschriebene Ablauf wird durch folgende automatisierte Nachweise
abgesichert:

| Dokumentierter Schritt | Automatisierter Nachweis |
| --- | --- |
| Demo-only Route und sichtbare Bedienelemente | `tests/backend/test_container_admin_ui.py` |
| Verschachtelte Eingaben und Serverprüfung | `tests/backend/test_container_blueprint_routes.py::test_blueprint_http_nested_validation_is_strict` |
| Prüfen → Veröffentlichen → Auflisten → Root-Objekt → Auto-Child | `tests/backend/test_container_blueprint_routes.py::test_blueprint_http_validate_publish_list_and_create_root` |
| Atomarität, Zyklen, Berechtigung und Persistenz | `tests/modules/container/test_container_m5_blueprints.py` |
| Neustart der Oberfläche | `tests/backend/test_container_admin_ui.py::test_admin_builder_survives_demo_restart` |

Zusätzlich werden die JavaScript-Datei mit `node --check`, das Python-Paket
mit `compileall` sowie Migration, Manifest und Packaging-Daten im finalen Gate
geprüft.
