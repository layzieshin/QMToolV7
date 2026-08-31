# QMToolV7 — WEBCLIENT UX SPECIFICATION

Status: Canonical (P0)
**Dokumenttyp:** Produkt-/UX-Spezifikation für den Webclient
**Gültig ab:** UX00
**Zielphase:** WEB01 und alle nachfolgenden Webclient-Arbeitspakete
**Sprache:** Deutsch als erste Produktsprache; technische IDs/Contracts Englisch
**Adressaten:** Entwickler, Cursor-/Codex-Agenten, Reviewer, UX-/QA-Verantwortliche
**Zweck:** Eine so konkrete und missverständnisarme Bauanleitung liefern, dass ein Implementierungsagent Ansichten nicht „frei interpretiert“, sondern reproduzierbar gemäß Produktentscheidung umsetzt.

WEB00 hat die zentrale Webclient-Foundation geliefert. Die vollständige Documents-/Signature-
Produkt-UI ist erst Gegenstand von WEB01 und darf vor dessen Gates nicht als implementiert gelten.

---

# 0. Wie dieses Dokument zu lesen ist

Dieses Dokument beschreibt **wie QMToolV7 im Browser aussehen, reagieren und bedient werden soll**. Es ersetzt keine Fachlogik, keine Backend-Contracts und keine Transition-Governance. Das außerhalb des Repositories übergebene UX-Handoff bleibt Rekonstruktionsquelle und ist **keine zweite Source of Truth**.

Bei Widersprüchen gilt folgende Quellenpriorität:

1. aktuelle kanonische P0-Regeln im Repository;
2. aktuelle P1-Transition-Governance im Repository;
3. diese P0-Spezifikation für reine Produkt-UX und Interaktion;
4. historische oder externe UX-/Visual-Unterlagen ausschließlich als nicht-normative Referenz.

Es ergänzt insbesondere:

- `docs/GUI_SOURCE_OF_TRUTH.md`
- `docs/GUI_ARCHITECTURE_PROJECT.md`
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
- `docs/MASTER_ORCHESTRATION_ROADMAP.md`
- `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`
- `docs/MODULE_INTEGRATION_POLICY.md`
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/WEBCLIENT_UX_CONTRACT_GAP_MATRIX.md` als veränderliche P1-Support-/Gap-Matrix

Wenn diese Spezifikation einer fachlichen oder sicherheitsrelevanten P0-Regel widerspricht, gewinnt die fachliche/Security-Regel. Bei reinen Darstellungs- oder Interaktionsfragen ist dagegen **diese UX-Spezifikation** maßgeblich.

## 0.1 Normative Begriffe

- **MUSS / MUST:** verbindlich; Abweichung benötigt eine dokumentierte Entscheidung.
- **DARF NICHT / MUST NOT:** verbindliches Verbot.
- **SOLL / SHOULD:** Standard; Abweichung nur mit nachvollziehbarem Grund.
- **DARF / MAY:** zulässige Option.
- **DEFERRED:** gewünschte Zielrichtung, aber nicht automatisch Teil des aktuellen Implementierungspakets.
- **BACKEND REQUIRED:** UI darf nicht so tun, als sei die Funktion fertig, solange ein autoritativer Backendvertrag fehlt.

## 0.2 Entscheidungsregel für Implementierungsmodelle

Ein Agent darf **nicht** aus eigenem Geschmack Layout, Workflow oder Berechtigungslogik erfinden. Falls ein Detail nicht spezifiziert ist:

1. zuerst bestehende QM-Komponenten und generische Patterns wiederverwenden;
2. dann das konservativste, am wenigsten überraschende Desktop-Webmuster wählen;
3. keine neue Fachsemantik erfinden;
4. fehlenden Backendvertrag als Gap markieren;
5. keine clientseitige Ersatzlogik bauen, um einen fehlenden Backendvertrag zu kaschieren.

---

# 1. Produktziel des Webclients

QMToolV7 soll sich wie eine **ruhige, professionelle, datenorientierte Arbeitsanwendung** anfühlen — nicht wie eine Marketing-Website und nicht wie ein überladenes Enterprise-Portal.

Die Oberfläche soll drei Dinge gleichzeitig leisten:

1. **schnell erfassbar** für normale Anwender sein;
2. **informationsdicht** genug für Qualitätsmanagement, Dokumentenlenkung und Administration sein;
3. **vorhersagbar** sein: dieselben Muster funktionieren in allen Modulen gleich.

Die wichtigste UX-Regel lautet:

> Der Benutzer soll fachliche Objekte sehen und bearbeiten — nicht die technische Architektur des Systems.

Der Browser zeigt deshalb keine Datenbankpfade, Modul-Interna, Repositorybegriffe, technischen Actor-Context oder Transportdetails.

---

# 2. Nicht verhandelbare Architekturgrenzen der UI

## UX-D01 — Webclient ist die einzige neue Produkt-UI

- Neue Endbenutzeroberflächen leben ausschließlich unter `webclient/*`.
- PyQt/Tk sind Legacy/Reference.
- Neue fachliche Abläufe werden nicht parallel in Desktop und Web weiterentwickelt.

## UX-D02 — Backend ist fachlich autoritativ

Der Browser darf niemals autoritativ entscheiden:

- ob eine Aktion erlaubt ist;
- welchen fachlichen Status ein Objekt erhalten darf;
- ob eine Signatur gültig ist;
- ob ein Benutzer Reviewer/Approver/Admin sein darf;
- ob eine Revision aktuell ist;
- ob ein Objekt gelöscht, archiviert, freigegeben oder geändert werden darf.

Die UI rendert serverseitige Zustände und erlaubte Aktionen und lässt Mutationen vom Backend erneut prüfen. `allowed_actions` ist der kanonische UX-Begriff; bestehende APIs können diese Information derzeit als `available_actions` transportieren. WEB01 darf weder aus dem Namen noch aus Rollen eigene Aktionsregeln ableiten. Generische Action Metadata und die endgültige Namenskonvention gehören zu WCON00.

## UX-D03 — Keine serverseitigen Pfade im Browser

Downloads, Viewer, Signaturen und Attachments verwenden opake IDs/URLs der HTTP-Grenze. Niemals `C:\...`, UNC-Pfade oder Server-Dateisystempfade anzeigen oder als fachliche Referenz speichern.

## UX-D04 — Keine dauerhafte lokale Fachkopie

Dauerhaft lokal gespeichert werden dürfen nur **nicht-sensitive**, benutzerspezifische UI-Präferenzen wie:

- Theme/Density;
- Spaltenkonfiguration;
- persönliche Ansichten;
- letzte Ansicht;
- Favoriten.

Fachliche QM-Daten bleiben backendgetrieben. Lokale Präferenzen müssen pro Benutzer/Organisation namespaced und bei Logout bzw. Kontextwechsel sicher verworfen werden. Secrets, Rollen, Berechtigungen, organisatorische Policies, Shared Views und fachliche Kopien dürfen nicht lokal autoritativ gespeichert werden. Persönliche Präferenzen sollen, sobald ein Vertrag verfügbar ist, serverseitig pro Benutzer synchronisiert werden.

## UX-D05 — Same-Origin-Webmodell

Der Browser spricht ausschließlich die kanonische Same-Origin-API an. Sessiondaten werden nicht in LocalStorage/SessionStorage als Token persistiert.

---

# 3. Produktreferenzen — Inspiration, kein Clone

Die folgenden Produkte und die im historischen Handoff enthaltenen Visual References dienen als **UX-Referenzen für bestimmte Muster**. Sie sind keine Abhängigkeiten, keine zweite Source of Truth und keine Aufforderung zum visuellen Kopieren. Visual Reference 3 autorisiert nur die dokumentzentrierte Platzierungsinteraktion; Recipient-, Envelope-, Send-, Public-Link- und Multi-Party-Signing-Flows sind ausdrücklich keine WEB01-Produktpflicht.

## 3.1 Nextcloud — Shell, Administration, persönliche Einstellungen, Benachrichtigungen

Übernehmen soll QMTool insbesondere:

- stabile, unaufgeregte globale Navigation;
- klare Trennung zwischen persönlicher Nutzung und Administration;
- zentralen Benachrichtigungsbereich;
- konsistente Einstellungsstruktur;
- modulübergreifend ähnliche Shell.

Nicht übernehmen:

- Cloud-Dateimanager als Grundmetapher für alle QM-Objekte;
- Nextcloud-spezifische App-/Plugin-Semantik;
- visuelles Pixel-Cloning.

## 3.2 OpenProject — informationsdichte Listen und Liste→Detail-Arbeit

Übernehmen:

- datenorientierte Tabellen;
- starke Filter-/Sortiermuster;
- effizientes Wechseln zwischen Einträgen;
- Split-View bzw. Master/Detail dort, wo wiederholtes Öffnen vieler Datensätze üblich ist.

Nicht übernehmen:

- Projektmanagement-spezifische Begriffe oder Statuslogik;
- unnötige Funktionsdichte in einfachen Modulen.

## 3.3 Paperless-ngx — Dokumentenpool und Dokumentfokus

Übernehmen:

- Dokumentliste mit leistungsfähiger Suche/Filterung;
- Dokument als zentrales fachliches Objekt;
- schneller Wechsel von Metadaten zu Dokumentinhalt/Viewer;
- klare Unterscheidung zwischen Liste, Detail und Dokumentanzeige.

Nicht übernehmen:

- Paperless-spezifische Korrespondenten-/Tag-Fachlogik als QMTool-Domain;
- automatische Klassifikation als notwendige Produktfunktion.

## 3.4 Directus / Frappe — metadata-driven Formulare

Übernehmen:

- generische Formrenderer;
- konsistente Feldkomponenten;
- deklarative Feldtypen und Policies;
- wiederverwendbare Picker/Relationen;
- einheitliche Validierungsdarstellung.

Nicht übernehmen:

- Admin-Builder als primäres Endnutzererlebnis;
- clientseitige Businessregeln als Ersatz für Backendvalidierung.

## 3.5 DocuSeal — Signaturarbeitsplatz

Übernehmen:

- das Dokument dominiert den Arbeitsbereich;
- direkte visuelle Platzierung der Signatur auf dem PDF;
- Drag/Resize statt Koordinateneingabe als Hauptweg;
- unmittelbare Vorschau;
- wenige kontextbezogene Bedienelemente;
- kurzer, klarer Abschlussweg.

Nicht übernehmen:

- externes Envelope-/Multi-Party-Signing als V1-Standard;
- öffentliche Signaturlinks;
- QES-Versprechen;
- DocuSeal-spezifische Account-/Tenantlogik;
- UI-Clone.

---

# 4. Visuelle Grundsprache

## UX-D06 — Professionell, kompakt, ruhig

Standard ist eine **kompakte professionelle Dichte**. QMTool ist ein Arbeitswerkzeug; großzügige Marketing-Abstände sind zu vermeiden.

### Vorgaben

- klare Typografie;
- moderate Zeilenhöhen;
- begrenzte Anzahl gleichzeitig konkurrierender Akzentflächen;
- Statusfarben nur semantisch;
- primäre Aktion optisch eindeutig, aber nicht riesig;
- visuelle Hierarchie über Abstand, Typografie und Container — nicht über viele bunte Karten.

## UX-D07 — Design Tokens

Farben, Abstände, Typografie, Radius, Schatten, Z-Index und Dichte werden zentral über QM-eigene Tokens bzw. Komponenten gesteuert.

Einzelne Fachkomponenten dürfen keine frei erfundenen Designwerte als neuen Standard etablieren.

## UX-D08 — Theme

Erste Produktpriorität ist ein vollständiges, konsistentes Light Theme. Architektur und Tokens dürfen Dark Mode später ermöglichen, aber fehlender Dark Mode blockiert WEB01 nicht.

## UX-D09 — Dichte

Dichte ist eine Benutzerpräferenz. Mindestens:

- `compact` — bevorzugter Standard für produktive QM-Arbeit;
- `comfortable` — größere Abstände für Benutzer mit entsprechender Präferenz.

Dichte verändert keine fachlichen Informationen oder Berechtigungen.

---

# 5. Globale App-Shell

## 5.1 Desktop-Grundlayout

Die Desktop-Anwendung besteht logisch aus:

```text
┌──────────────────────────────────────────────────────────────┐
│ Global Header / Kontext / Suche / Notifications / User      │
├───────────────┬──────────────────────────────────────────────┤
│               │                                              │
│ Modul-        │              Content Area                    │
│ navigation   │                                              │
│               │                                              │
│               │                                              │
├───────────────┴──────────────────────────────────────────────┤
│ nur falls nötig: globale Status-/Connection-Meldung          │
└──────────────────────────────────────────────────────────────┘
```

Die linke Navigation ist stabil. Der Benutzer soll nicht bei jedem Modul eine vollständig neue App-Struktur lernen müssen.

## 5.2 Linke Modulnavigation

MUSS:

- zentrale Module auf oberster Ebene anzeigen;
- aktuell aktive Route sichtbar markieren;
- Icons nur unterstützend verwenden, niemals ohne verständliche Bezeichnung im normalen Expanded-Modus;
- bei vielen Modulen gruppierbar/scrollbar sein;
- Administration nicht zwischen normalen Fachmodulen verstecken.

### Sichtbarkeit von Modulen

Standard:

- lizenzierte + aktive + für Benutzer zugängliche Module anzeigen;
- nicht lizenzierte Module für normale Anwender ausblenden;
- deaktivierte Module für normale Anwender ausblenden;
- Admin darf in der System-/Modulübersicht alle bekannten Module samt Zustand sehen.

Die Shell darf keine Berechtigung aus Rollen selbst berechnen. Sie verwendet Backend-/Session-/Module-Capabilities.

## 5.3 Global Header

Enthält nach Bedarf:

- globalen Suchzugang;
- Connection-State nur wenn relevant;
- Notifications/Tasks;
- Benutzer-/Profilmenü;
- ggf. Kontexttitel der aktiven Ansicht.

Nicht dauerhaft hineinquetschen:

- fachmodulspezifische Toolbars;
- lange Filtergruppen;
- Debug-/Serverinformationen.

## 5.4 Browser-Tabs statt künstlicher interner Fensterverwaltung

QMTool soll keine eigene „MDI“- oder pseudo-browserartige Tabverwaltung für beliebige Objekte bauen.

- Routen müssen in echten Browser-Tabs geöffnet werden können.
- Links auf fachliche Objekte sollen mittlere Maustaste / Ctrl+Click sinnvoll unterstützen.
- Interne Tabs sind nur innerhalb eines einzelnen komplexen Detailobjekts zulässig, z. B. `Übersicht | Dokument | Kommentare | Verlauf`.

---

# 6. Routing, URLs und Zustand

## UX-D10 — Stabile, lesbare URLs

Fachliche Ansichten besitzen stabile URLs, z. B. sinngemäß:

```text
/documents
/documents/{documentId}
/documents/{documentId}/versions/{version}
/users/{userId}
/admin/modules
```

Technische IDs dürfen in URLs vorkommen, aber keine lokalen Dateipfade.

## UX-D11 — Listenstatus in URL, soweit sinnvoll

Filter, Suche, Sortierung, Auswahlseite oder gespeicherte View sollen so weit möglich in URL-/Query-State abbildbar sein, damit:

- Reload nicht überraschend alles verliert;
- Links teilbar sind;
- Browser Back/Forward funktioniert.

Nicht in URLs:

- Secrets;
- Sessiontokens;
- sensible temporäre Formdaten;
- Passwörter;
- Signatur-Reauth-Daten.

---

# 7. Startseite / Dashboard

## UX-D12 — Dashboard ist schlank

Das Dashboard ist kein BI-System und kein Kachel-Friedhof.

Es soll schnell beantworten:

- Was braucht meine Aufmerksamkeit?
- Was habe ich zuletzt bearbeitet?
- Welche Aufgaben sind offen?
- Gibt es relevante System-/Modulprobleme, die ich sehen darf?

Mögliche Widgets:

- Meine Aufgaben;
- zuletzt verwendete Objekte;
- Favoriten;
- relevante Benachrichtigungen;
- wenige modulbezogene Statuskarten.

## UX-D13 — Persönlicher Startpunkt

Benutzer dürfen später bevorzugte Startansicht wählen. Bis serverseitige Preferences vorhanden sind, darf die Foundation eine konservative lokale UI-Präferenz verwenden.

---

# 8. Generic View System

Generic-first ist verbindlich. Ein Modul erhält keine Custom View, nur weil ein Entwickler sie schöner findet.

## 8.1 Generische View-Typen

QMTool soll zentrale Renderer/Komponenten besitzen für:

- List;
- Detail;
- Form;
- History;
- Settings;
- Dashboard-Slice;
- Wizard;
- Relation/Object Picker;
- Attachment Section.

## 8.2 Wann Custom View erlaubt ist

Custom View nur wenn mindestens eines gilt:

- direkte Dokument-/Canvas-Interaktion nötig;
- räumliche Platzierung wichtig;
- hochgradig spezialisierter Workflow nicht sinnvoll in Generic Form abbildbar;
- Viewer/Editor mit eigener Interaktionsoberfläche nötig.

Typische genehmigte Beispiele:

- PDF Viewer;
- Signaturplatzierung.

Nicht ausreichend als Begründung:

- „dieses Modul sieht sonst langweilig aus“;
- „wir können es schneller hardcoden“;
- „dieses Formular hat viele Felder“.

---

# 9. Listen und Tabellen

## 9.1 Grundverhalten

Listen sind zentrale Arbeitsflächen, keine bloßen Reports.

MUSS:

- serverseitig oder backendverträglich paginieren/filterbar sein;
- leere Zustände sinnvoll darstellen;
- Loading separat von Empty darstellen;
- sortierbare Spalten eindeutig markieren;
- Status kompakt, konsistent und nicht nur über Farbe darstellen;
- Row-Actions sparsam halten;
- Hauptaktion pro Zeile nicht in einem Wald aus Icons verstecken.

## 9.2 Tabellenpersonalisierung

Ziel:

- Spalten ein-/ausblenden;
- Spaltenreihenfolge;
- Breite soweit sinnvoll;
- Sortierung;
- Filter;
- persönliche gespeicherte Views.

Persönliche Views gehören bevorzugt zum Benutzerprofil. Shared/Admin Views benötigen einen eigenen autoritativen Backendvertrag und dürfen nicht clientseitig als „gemeinsam“ simuliert werden.

## 9.3 Filter

Filterleiste soll:

- aktive Filter sichtbar machen;
- Filter schnell entfernbar machen;
- nicht jede Option permanent als riesiges Formular zeigen;
- komplexe Filter in ein Panel/Popover auslagern dürfen.

Aktive Filter dürfen als Chips/kompakte Tokens dargestellt werden.

## 9.4 Zeilenauswahl und Bulk Actions

Bulk Actions werden **nicht automatisch** angeboten.

Nur wenn Backend/Capability die konkrete Bulk-Aktion ausdrücklich unterstützt.

Client darf nicht N Einzelmutationen ausführen und dies als atomare Bulk-Aktion darstellen, wenn dafür kein Vertrag existiert.

---

# 10. Master/Detail und Split View

## UX-D14 — Split View für wiederholte Listenarbeit

Wo Benutzer viele Einträge nacheinander prüfen, ist bevorzugt:

```text
┌───────────────────────┬──────────────────────────────────────┐
│ Liste / Treffer       │ Detail / Preview                     │
│                       │                                      │
│ > aktueller Eintrag   │ ausgewähltes Objekt                  │
│   weiterer Eintrag    │                                      │
│   weiterer Eintrag    │                                      │
└───────────────────────┴──────────────────────────────────────┘
```

Das gilt besonders für Dokumentenpool, Aufgabenlisten und ähnliche review-intensive Bereiche.

Der Detailbereich darf eine echte Detailroute besitzen. Auf kleinen Viewports darf Split View in Navigation Liste → Detail übergehen.

---

# 11. Detailansichten

## UX-D15 — Read Mode zuerst

Fachobjekte öffnen standardmäßig in einem **Read Mode**.

Vorteile:

- keine versehentlichen Änderungen;
- klare Unterscheidung zwischen Lesen und Bearbeiten;
- bessere Darstellung komplexer Metadaten.

Bearbeiten erfolgt über explizite Aktion `Bearbeiten`, sofern `allowed_actions` dies zulässt.

## 11.1 Detailheader

Ein Detailheader zeigt typischerweise:

- fachlichen Titel;
- Typ/Kategorie;
- Status;
- Version/Revision wenn fachlich relevant;
- wichtigste Primäraktion;
- sekundäre Aktionen im Overflow.

Keine technischen IDs dominant darstellen, sofern nicht fachlich erforderlich.

## 11.2 Interne Detailtabs

Nur wenige, semantisch klare Tabs. Beispiel Dokument:

- Übersicht
- Dokument
- Kommentare
- Verlauf

Tabs sollen keine zufällige Zerlegung jedes kleinen Blocks erzeugen.

---

# 12. Formulare

## 12.1 Feldlayout

- Labels eindeutig und dauerhaft sichtbar;
- Placeholder ist kein Ersatz für Label;
- Pflichtfelder mit `*` kennzeichnen;
- Hilfe nur dort, wo sie nötig ist;
- verwandte Felder gruppieren;
- lange Formulare in sinnvolle Sektionen zerlegen;
- zwei Spalten nur bei inhaltlich passenden kurzen Feldern und ausreichender Breite.

## 12.2 Explizites Speichern

Für fachliche Änderungen gilt standardmäßig **Explicit Save**.

- `Speichern` sendet die fachliche Mutation;
- `Abbrechen` verwirft lokale Änderungen nach ggf. nötiger Warnung;
- keine stillen fachlichen Autosaves ohne expliziten Contract.

Autosave ist für reine UI-Präferenzen zulässig.

## UX-D16 — Dirty State

Bei Änderungen:

- sichtbar machen, dass ungespeicherte Änderungen existieren;
- optional Anzahl geänderter Felder zeigen;
- geänderte Felder subtil markieren;
- Navigation/Tab schließen mit geeigneter Warnung schützen.

Keine aggressive Modalwarnung bei jeder internen Interaktion.

## 12.3 Drafts

Draft-Speicherung nur, wenn der Backendvertrag `allow_draft` bzw. gleichwertige Semantik explizit erlaubt.

Kein clientseitiger „Entwurf“ als dauerhafte Fachkopie.

---

# 13. Validierung und Fehler

## UX-D17 — Backendfehler feldnah darstellen

Strukturierte Validierungsfehler werden:

1. am betroffenen Feld gezeigt;
2. zusätzlich in einer kompakten Formularzusammenfassung, wenn mehrere Fehler vorliegen;
3. nicht ausschließlich als Toast dargestellt.

## 13.1 Fehlerklassen

### 400/422 — Eingabe/Validation

- konkret erklären;
- betroffene Felder markieren.

### 401 — Session nicht gültig

- Sessionstatus sauber behandeln;
- Benutzer nicht mit endlosen Fehlertoasts fluten.

### 403 — nicht erlaubt

- Aktion nach Möglichkeit bereits über `allowed_actions` nicht anbieten;
- bei Race/Policyänderung trotzdem serverseitige Ablehnung verständlich zeigen.

### 404 — Objekt nicht vorhanden

- klare Not-Found-Ansicht;
- Rückweg anbieten.

### 409/412/428 — Revision/ETag/Precondition

- spezieller Konfliktpfad, siehe Abschnitt Concurrency.

### 5xx / Connection

- technische Fehler nicht als Rohstack anzeigen;
- Request-/Correlation-ID darf für Support angezeigt/kopiert werden.

---

# 14. Actions und Berechtigungen

## UX-D18 — `allowed_actions` bestimmt sichtbare Fachaktionen

Die UI darf Rollen nicht interpretieren.

Falsch:

```ts
if (user.role === 'QMB') showApproveButton()
```

Richtig:

```ts
if (resource.allowed_actions.includes('approve')) showApproveButton()
```

Der Backendendpoint validiert dennoch erneut.

## 14.1 Action-Metadaten

Zielvertrag für generische Actions sollte mindestens ausdrücken können:

- Action Code;
- Label/i18n-Key;
- enabled/disabled;
- optionaler Disable-Reason;
- requires_reason;
- requires_confirmation;
- destructive;
- optional benötigte Parameter/Formdefinition;
- ggf. Reauth requirement.

Wenn diese Metadaten serverseitig fehlen, ist generisches Action-Rendering für die betroffene
Aktion bis WCON00 blockiert. WEB01 darf weder Labels, Confirmation-/Reason-Pflichten noch
Destruktivität als hardcodierte Ersatzmetadaten mit eigener Fachbedeutung einführen.

## 14.2 Dialoge

Dialoge nur für:

- irreversible/destruktive Aktion;
- Pflichtbegründung;
- Reauthentifizierung;
- kurze Entscheidungen, die den Arbeitskontext nicht verlassen sollen.

Normale Bearbeitung gehört in die Seite, nicht in Modalkaskaden.

---

# 15. Concurrency, ETag und Konflikte

## UX-D19 — Konflikte sind normaler Multiuser-Fall

Ein stale write ist kein generischer „Serverfehler“.

Bei Konflikt soll die UI:

1. Mutation nicht als erfolgreich darstellen;
2. aktuelle Serverversion laden bzw. `current_state/current_etag` nutzen;
3. klar erklären, dass zwischenzeitlich geändert wurde;
4. lokale Änderungen nicht still verwerfen;
5. je nach Formtyp Vergleich/Reload/erneute Bearbeitung anbieten.

## 15.1 Minimaler Konfliktdialog

Beispiel:

- Titel: `Datensatz wurde zwischenzeitlich geändert`
- Text: `Eine andere Sitzung hat eine neuere Version gespeichert.`
- Aktionen:
  - `Aktuelle Version laden`
  - ggf. `Meine Änderungen ansehen`
  - `Abbrechen`

Keine automatische „last write wins“-Strategie im Client.

---

# 16. Edit Locks / Lease — DEFERRED

**BACKEND REQUIRED / Plattformfunktion; nicht WEB01-blockierend.** ETag/If-Match bleibt der verbindliche WEB01-Konfliktschutz. Ein Lock darf weder simuliert noch als vorhandene Sicherheit dargestellt werden.

Zielmodell:

- fachliche Bearbeitung kann optional serverseitigen Edit Lock/Lease verwenden;
- Lease besitzt Ablauf/Heartbeat;
- UI zeigt, wenn ein anderer Benutzer aktiv bearbeitet;
- stale Locks können nach definierter Policy administrativ bereinigt werden;
- Lock ist keine Autorisierung und ersetzt kein ETag.

## UX-Verhalten

Wenn Lock durch anderen Benutzer:

- Read Mode bleibt nutzbar;
- `Bearbeiten` deaktiviert oder erklärt den Konflikt;
- Benutzername nur anzeigen, wenn datenschutz-/policykonform;
- keine clientseitige Lock-Datei.

Session-Inaktivität und Edit-Lock-Lifetime sind getrennte Konzepte.

---

# 17. Connection State / Backend nicht erreichbar

## UX-D20 — Ansicht bleibt stehen

Bei Verbindungsverlust:

- bestehende Ansicht bleibt sichtbar;
- zentraler Banner zeigt `Verbindung zum Server unterbrochen`;
- fachliche Schreib-/Aktionsoperationen werden gesperrt;
- Read-Daten werden nicht als garantiert aktuell dargestellt;
- automatische Wiederverbindungsversuche laufen zentral;
- nach Wiederherstellung wird der Status aktualisiert und Weiterarbeiten ermöglicht.

Nicht tun:

- sofort komplette App durch Fehlerseite ersetzen;
- Mutation lokal queuen und später ohne erneute Fachprüfung senden;
- Benutzer mit Toast pro Pollingfehler fluten.

## 17.1 Anzeige

Banner kompakt, persistent solange offline, mit Status wie:

- `Verbindung unterbrochen`
- `Wiederverbinden …`
- `Verbindung wiederhergestellt`

Letzter Zustand darf kurz bestätigt und dann ausgeblendet werden.

---

# 18. Refresh und Live Updates

Der konkrete Transportmechanismus (gezielter Refetch, Polling, SSE oder Push) wird vom freigegebenen
Vertrag und INT00 bestimmt. Diese UX-Spezifikation legt keine technische Reihenfolge fest. Keine
Komponente startet eigenmächtig dauerhafte 1-Sekunden-Polls.

Prinzip:

- zentraler Connection-/Refresh-Mechanismus;
- View kann „stale“ erkennen;
- fachliche Mutationen führen zu gezielter Invalidierung/Refetch;
- kein globales Reload der gesamten SPA nach jeder Aktion.

---

# 19. Benachrichtigungen und Aufgaben

Documents-Tasks können bestehende Backendverträge nutzen. Ein persistentes modulübergreifendes Notification Center ist **DEFERRED** und gemäß P0 nicht Teil des ersten Piloten. Es darf in WEB01 weder simuliert noch als fertig dargestellt werden.

## UX-D21 — zentrale Stelle statt Modul-Inseln

Benachrichtigungen/Tasks sollen zentral erreichbar sein.

Unterscheidung:

- **Task:** verlangt typischerweise eine Benutzeraktion;
- **Notification:** informiert über Ereignis/Zustand.

Beispiele:

- Dokument wartet auf Review;
- Freigabe erforderlich;
- Kommentar wurde beantwortet;
- fachliche Frist nähert sich;
- Import/Job abgeschlossen.

Acknowledgement/Read-State soll serverseitig synchronisierbar sein.

Module dürfen nicht jeweils eigene völlig andere Notification-Center bauen.

---

# 20. Jobs / lange Operationen — DEFERRED

**BACKEND REQUIRED für autoritative Jobs.** Für WEB01 ist der generische Jobdienst deferred, solange kein freigegebener Pilot-Flow asynchron ausgeführt werden muss. OPS00/INT00 dürfen die Betriebsrelevanz prüfen, implementieren ihn aber nicht stillschweigend als UX-Ersatzvertrag.

Lange Vorgänge sollen nicht durch spinnernde HTTP-Buttons ohne Zustand modelliert werden.

Ziel:

- Job-ID;
- Status `queued/running/succeeded/failed/cancelled`;
- Progress falls verlässlich bestimmbar;
- verständliche Fehlermeldung;
- Cancel nur wenn backendseitig erlaubt;
- Notification bei Abschluss.

Beispiele:

- größerer Import;
- Export;
- Konvertierung;
- Backup-nahe Adminoperationen.

---

# 21. Suche

## UX-D22 — global + lokal

Es gibt zwei Ebenen:

### Global Search — DEFERRED

Modulübergreifender Einstieg. Später bevorzugt über `Ctrl+K`/Command Palette erreichbar.

### Module Search

Innerhalb einer Liste/Ansicht mit fachlich relevanten Filtern.

Global Search darf nicht einfach clientseitig alle Modulendpoints laden und durchsuchen.

---

# 22. Command Palette und Tastatur

## UX-D23 — schlanke Command Palette

`Ctrl+K` soll langfristig eine schlanke Palette öffnen für:

- Navigation zu Modulen;
- globale Suche;
- häufige erlaubte Aktionen;
- ggf. zuletzt verwendete Objekte.

Sie ersetzt keine sichtbare Navigation.

## 22.1 Standardshortcuts

- `Ctrl+S`: Speichern in aktivem editierbarem Fachformular, sofern sinnvoll;
- `Esc`: Dialog/Popover schließen oder Bearbeitung verlassen, niemals blind Daten verwerfen;
- `Ctrl+K`: Command Palette / globale Suche.

Browserstandards nicht unnötig überschreiben.

---

# 23. Breadcrumbs

Breadcrumbs nur bei echter Hierarchie.

Sinnvoll:

```text
Dokumente > QM-Handbuch > Version 4
```

Nicht sinnvoll:

```text
Home > Modul > Seite > Tab > Untertab > Panel
```

Bei flachen Bereichen reicht Seitentitel + Navigation.

---

# 24. Favoriten und zuletzt verwendet

Ziel:

- Benutzer kann fachliche Objekte favorisieren, wenn die Objektart dies unterstützt;
- „Zuletzt verwendet“ erleichtert Rückkehr;
- persönliche Präferenz bevorzugt serverseitig synchronisieren;
- keine fachliche Autorisierung aus Favoriten ableiten.

Wenn ein Objekt nicht mehr zugänglich ist, darf Favorit keine Daten leaken.

---

# 25. Persönliche Einstellungen vs. Administration

## UX-D24 — strikt getrennte Bereiche

### Persönlich

Beispiele:

- Theme;
- Density;
- bevorzugte Startansicht;
- Tabellen-/Viewpräferenzen;
- ggf. Signaturplatzierungs-Presets;
- Notification-Präferenzen soweit zulässig.

### Administration

Beispiele:

- Benutzer;
- Module/Lizenzen;
- systemweite Settings;
- Drucker/Output;
- Governance-relevante Einstellungen;
- technische Readiness-/Statusinformationen, soweit für Admin vorgesehen.

Eine persönliche Einstellung darf keine systemweite Fachpolicy ändern.

---

# 26. Admin-Modulübersicht

## UX-D25 — standardisierte Modulzustände

Admin erhält eine zentrale Übersicht. Mindestens folgende semantische Zustände müssen darstellbar sein:

- aktiv;
- nicht lizenziert;
- deaktiviert;
- fehlerhaft;
- nicht bereit / fehlende Abhängigkeit;
- ggf. Migration erforderlich.

Ein Modulfehler darf die restliche Shell nicht zerstören.

Jeder Status zeigt:

- verständliches Label;
- kurze Erklärung;
- ggf. erlaubte Adminaktion;
- technische Details nur aufklappbar/sekundär.

---

# 27. Attachments

## UX-D26 — zentrale Attachment-Komponente

Module sollen dieselben Komponenten verwenden für:

- Datei auswählen/hochladen;
- Upload-Fortschritt;
- Dateiname;
- Medientyp/Größe;
- Download/Preview, sofern erlaubt;
- Entfernen, sofern erlaubt;
- Fehler.

Keine Fachkomponente implementiert ihren eigenen Dateiupload mit Serverpfaden.

## 27.1 Kamera/Mobile-Vorbereitung

Für geeignete Workflows, insbesondere spätere Incident-Funktionen, soll Attachment-UI technisch so gestaltet sein, dass Browser-Kamera/Fotoaufnahme später möglich ist.

Dies ist kein Zwang, WEB01 mobil vollständig zu machen.

---

# 28. Relation / Object Picker

## UX-D27 — generischer Picker

Für Benutzer-, Objekt-, Dokument- oder andere Referenzen soll ein zentraler Picker existieren bzw. vorbereitet werden.

Eigenschaften:

- Suche;
- fachlicher Anzeigename;
- optional Typ/Kontext;
- keine technischen IDs als Primärlabel;
- Mehrfachauswahl nur wenn Contract erlaubt;
- nur auswählbare/erlaubte Zielobjekte darstellen.

---

# 29. History, Audit und technische Logs

## UX-D28 — drei Dinge nicht vermischen

### Fachlicher Verlauf

Für Benutzer verständliche Ereignisse:

- erstellt;
- Status geändert;
- Rolle zugewiesen;
- Kommentar hinzugefügt;
- freigegeben;
- archiviert;
- signiert.

### Audit/Nachweis

Detaillierter, nachvollziehbarer, append-only Fachnachweis für autorisierte Nutzer/Admins.

### Technische Logs

Betriebsdiagnose; nicht Teil der normalen fachlichen Objektchronik.

UI darf technische Logzeilen nicht einfach als fachliche History ausgeben.

---

# 30. Toasts, Banner, Inline-Feedback

## UX-D29 — Feedback nach Reichweite wählen

### Toast

Für kurze, abgeschlossene, nicht kritische Rückmeldung:

- `Gespeichert`
- `Kommentar hinzugefügt`

### Banner

Für andauernden/globalen Zustand:

- Verbindung verloren;
- System im Wartungsmodus;
- Modul nicht bereit.

### Inline

Für feld-/objektbezogene Fehler:

- Validation;
- fehlende Pflichtangabe;
- Conflict-Hinweis.

### Dialog

Für bewusste Entscheidung/Reauth/Destructive.

Keine Toast-Flut.

---

# 31. Destruktive Aktionen und Begründungen

## UX-D30 — Kritisch ist sichtbar kritisch

Destruktive oder governance-kritische Aktion:

- klarer Aktionsname statt `OK`;
- Begründungsfeld, wenn Backend `requires_reason` verlangt;
- Confirmation, wenn Contract dies verlangt;
- keine versteckte destructive Primary Action;
- nach Erfolg eindeutige Statusänderung.

Wenn eine Aktion nicht rückgängig gemacht werden kann, darf UI dies deutlich sagen — ohne künstliche Paniksprache.

---

# 32. Controlled Download

## UX-D31 — deny-by-default als Produktmuster

Bei gelenkten/geschützten Dokumenten ist Download nicht automatisch vorhanden.

Download-Button nur wenn konkrete Action/Capability dies erlaubt.

Browser darf nicht aus vorhandener Viewer-URL schließen, dass Download fachlich erlaubt sei.

---

# 33. Controlled Print — DEFERRED

**BACKEND REQUIRED für produktiven Druckpfad; OPS00/INT00 relevant, nicht WEB01-blockierend.**

Ein späterer Druckpfad muss backend-kontrolliert und über eine explizite serverseitige
Action/Capability freigegeben sein. UX00 entscheidet weder Adaptertechnologie noch Druckprotokoll.

## 33.1 Druckdialog

Wenn ein späterer Vertrag `print` erlaubt, rendert die UI ausschließlich die von diesem Vertrag
bereitgestellten Optionen, zum Beispiel:

- Drucker auswählen aus serverseitig erlaubter Liste;
- Anzahl Kopien;
- ggf. Zweck/Begründung;
- ggf. kontrollierte Kopienregel;
- klare Vorschau des zu druckenden Artefakts.

## UX-D32 — Kennzeichnung kontrollierter Kopien bleibt serverautoritativ

Ob und wie physische Kopien IDs, Zweck oder Empfänger benötigen, ist eine spätere Compliance-/OPS-
Entscheidung. Wenn ein freigegebener Vertrag solche Angaben liefert, zeigt die UI sie an; der
Browser generiert weder Copy-IDs noch Kopienregeln selbst.

---

# 34. Mobile / responsive Strategie

## UX-D33 — Desktop-first, mobile selektiv

QMToolV7 ist zunächst eine produktive Desktop-Browseranwendung.

Responsive Verhalten MUSS verhindern, dass die App auf kleineren Displays unbenutzbar zerbricht. Aber nicht jeder komplexe Workflow muss V1 smartphone-optimiert sein.

Priorität mobil später:

- Aufgaben ansehen;
- einfache Freigabe-/Reviewhandlungen, sofern sicher;
- Notifications;
- Incident-Foto/Attachment;
- einfache Such-/Detailansichten.

Nicht V1-Priorität:

- komplexe Signaturplatzierung auf Smartphone;
- große Admin-Tabellen;
- umfangreiche Builder.

---

# 35. Accessibility-Baseline

Dies ist ein Implementierungsstandard dieser Spezifikation.

MUSS:

- vollständige Tastaturbedienbarkeit zentraler Flows;
- sichtbarer Focus-State;
- semantische Labels;
- Status nicht ausschließlich über Farbe;
- ausreichender Kontrast;
- Dialog-Focus korrekt;
- Screenreader-fähige Formlabels und Fehlermeldungen.

Automatisierte a11y-Checks sollen Bestandteil der Webtests werden, sobald die Komponentenbasis stabil ist.

---

# 36. Internationalisierung

## UX-D34 — Deutsch zuerst, i18n von Anfang an

Erste UI-Sprache: Deutsch.

Trotzdem:

- sichtbare Strings über i18n-Keys;
- keine fachlichen Labels überall hardcoden;
- Datums-/Zeit-/Zahlenformatierung locale-aware;
- Backendcodes nicht direkt als Benutzertext ausgeben.

Technische Action Codes bleiben stabil und sprachneutral.

---

# 37. Dokumentenmodul — Zielaufbau WEB01

Documents + Signature sind der erste vollständige Produkt-Webslice.

## 37.1 Dokumentenpool

Empfohlenes Desktoplayout:

```text
┌────────────────────────────────────────────────────────────────────┐
│ Dokumente                         [Suche] [Filter] [Neu/Import]      │
├──────────────────────────────┬─────────────────────────────────────┤
│ Trefferliste / Tabelle       │ ausgewähltes Dokument               │
│                              │                                     │
│ Titel                        │ Titel / Status / Version             │
│ Status                       │ Metadaten                            │
│ Version                      │ nächste erlaubte Aktionen            │
│ Verantwortlich               │ Preview / Kurzinfo                  │
│ geändert                     │                                     │
└──────────────────────────────┴─────────────────────────────────────┘
```

Auf kleineren Viewports: Liste → separate Detailroute.

## 37.2 Dokumentliste — Kernspalten

Konkrete Spalten werden fachlich/vertraglich bestimmt. Typisch:

- Titel/Name;
- Dokumentkennung soweit vorhanden;
- Version;
- Status;
- verantwortliche/zugewiesene Rolle oder Nutzer, wenn relevant;
- zuletzt geändert;
- ggf. nächste Aufgabe.

Keine 20 Spalten als Standard. Weitere über Spaltenauswahl.

## 37.3 Dokumentdetail

Header:

- Titel;
- Version;
- Status;
- fachliche Kennung;
- Primäraktion aus `allowed_actions`;
- Overflow für seltene Aktionen.

Inhalt:

- Übersicht/Metadaten;
- Dokument/Viewer;
- Kommentare;
- Verlauf.

## 37.4 Dokumentaktion statt Workflow-Knopfwand

Benutzer soll nicht alle theoretischen Workflowtransitionen gleichzeitig sehen.

Zeige:

- die in aktuellem Zustand tatsächlich erlaubten nächsten Aktionen;
- Primäraktion prominent;
- alternative erlaubte Aktionen sekundär;
- nicht erlaubte Aktionen normalerweise gar nicht oder nur dann disabled, wenn der Disable-Grund für Verständnis wichtig ist.

---

# 38. Documents — Import

## UX-D35 — Import ist eigener klarer Flow

Unterstützte Pfade können sein:

- PDF importieren;
- DOCX/DOTX importieren, soweit der Backendvertrag dies unterstützt;
- aus Template erzeugen.

Flow:

1. Quelle wählen;
2. grundlegende Metadaten;
3. ggf. Template/Zuordnung;
4. serverseitige Validierung;
5. Ergebnis öffnen.

Keine automatische Datenmigration/„KI ordnet alles zu“, wenn kein ausdrücklicher Produktvertrag existiert.

---

# 39. PDF Viewer

## UX-D36 — Viewer ist eine Custom View

Der PDF-Inhalt ist zentral, nicht ein kleines Vorschaubild neben 20 Formularfeldern.

MUSS sinnvoll unterstützen:

- Seitenwechsel;
- Zoom;
- Fit width / fit page;
- aktuelle Seite;
- performantes Nachladen;
- Kontext für Kommentare/Signatur, soweit der jeweilige Modus dies braucht.

Optional/DEFERRED:

- Seitenminiaturen;
- Vollbildmodus;
- Suche im PDF, wenn technisch zuverlässig verfügbar.

## 39.1 Viewer-Modi

Ein Viewer kann unterschiedliche Modusflags besitzen:

- read-only viewing;
- comment mode;
- signature placement mode;
- controlled output context.

Die Fachberechtigung dafür kommt aus Backendactions.

---

# 40. Kommentare

## UX-D37 — Kommentare sind fachliche Objekte, keine Chatblase ohne Kontext

Dokumentkommentare zeigen mindestens:

- Autor;
- Zeitpunkt;
- Inhalt;
- Status soweit fachlich vorgesehen;
- Bezug auf Dokumentversion;
- ggf. Seiten-/Positionsbezug bei PDF-Kommentaren.

PDF-Kommentare und importierte/native Word-Kommentare müssen in der UI unterscheidbar bleiben, wenn ihre Semantik verschieden ist.

Keine Behauptung einer bidirektionalen Word-Synchronisation, solange der Backendvertrag sie nicht tatsächlich liefert.

---

# 41. Workflow-Aufgaben

## UX-D38 — Aufgabe zeigt „Was muss ich tun?“ statt Workflowmaschine

Eine persönliche Taskdarstellung soll bevorzugt zeigen:

- Dokument;
- Aufgabe/Rolle;
- Frist, falls vorhanden;
- aktueller Status;
- direkte Navigation zur relevanten Ansicht.

Technische Transitioncodes nur intern.

---

# 42. Signature Workspace — Zielbild

Die Signatur ist ein bewusster **DocuSeal-artiger Custom Flow**, angepasst an QMTool.

## 42.1 Grundlayout Desktop

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Signieren: <Dokumenttitel>                         [Abbrechen]       │
├───────────────┬───────────────────────────────────┬─────────────────┤
│ Seiten /      │                                   │ Signaturoptionen│
│ Navigation    │           PDF Canvas              │                 │
│ optional      │                                   │ Preset          │
│               │      ┌──────────────────┐         │ Name   [x]      │
│               │      │ Signaturblock    │         │ Datum  [x]      │
│               │      │ drag + resize    │         │ Uhrzeit[x]      │
│               │      └──────────────────┘         │                 │
│               │                                   │ [Signieren]     │
└───────────────┴───────────────────────────────────┴─────────────────┘
```

Der PDF-Bereich erhält den größten Flächenanteil.

## 42.2 Platzierung

MUSS:

- Signaturblock direkt auf PDF positionierbar;
- Drag;
- Resize;
- Seite eindeutig;
- Koordinaten aus Viewport korrekt in dokumentbezogene Koordinaten transformieren;
- Zoomänderung darf gespeicherte Platzierung nicht verändern;
- Vorschau entspricht möglichst genau dem finalen Ergebnis.

Koordinatenfelder dürfen für Diagnose/Feintuning existieren, sind aber **nicht Hauptbedienweg**.

## UX-D39 — Signaturinhalt

Signaturdarstellung kann enthalten:

- eigentliche Signatur/Signaturasset;
- Name;
- Datum;
- Uhrzeit.

Name/Datum/Uhrzeit sind einzeln ein-/ausblendbar, soweit der fachliche Signaturvertrag diese Optionen zulässt.

### Verbindliche Layoutregel

**Datum und Uhrzeit verwenden dieselbe Zeile bzw. dieselbe gemeinsame Layoutposition.**

`show_time` erweitert also die Datumszeile; es gibt keine vollständig unabhängige Zeitposition, solange keine spätere explizite Entscheidung dies ändert.

Beispiel:

```text
Max Mustermann
23.08.2026 16:42
[Signatur]
```

oder entsprechend dem freigegebenen Signature-Template.

## 42.3 Persönliche Presets

Ziel:

- Benutzer kann eine bewährte Platzierung als persönliches Preset speichern;
- Preset darf an Dokumenttyp und Rolle/Signaturkontext gebunden sein;
- bei nächstem passenden Signaturvorgang wird das zuletzt passende Preset automatisch **vorgeschlagen**;
- vorgeschlagen bedeutet nicht blind finalisiert — Nutzer sieht die Platzierung vor Abschluss.

Preset kann enthalten:

- Seite/relative Position;
- Größe;
- Name sichtbar;
- Datum sichtbar;
- Uhrzeit sichtbar;
- ggf. verwendete Darstellung/Template-ID.

**BACKEND/PREFERENCES REQUIRED** für geräteübergreifende Synchronisierung. Bis dahin darf kein lokales Preset als globale organisatorische Policy dargestellt werden.

## 42.4 Abschluss / Reauth

Vor fachlich verbindlicher Signatur:

1. Benutzer sieht finale Vorschau;
2. `Signieren` startet Reauthentifizierung gemäß bestehendem Signaturvertrag;
3. Passwort/Reauth-Daten werden nur für diesen Vorgang verwendet;
4. Backend validiert Actor, Workflowzustand, Berechtigung, Revision und Signatur;
5. Erfolg führt zur serverseitigen neuen fachlichen Resource/State;
6. UI zeigt Ergebnis und aktualisiert Viewer/Status.

Passwort niemals in LocalStorage, SessionStorage, Logs oder UI-State persistieren.

## 42.5 Nicht Teil des V1-Referenzflows

- externe Signaturlinks;
- anonyme Unterzeichner;
- Envelope-Workflow wie kommerzielle eSign-Plattform;
- QES-Behauptung;
- SMS-/E-Mail-Signatureinladungen ohne separates Produktpaket.

---

# 43. Approved / freigegebenes PDF

## UX-D40 — freigegebenes Artefakt ist klar erkennbar

Wenn Workflow ein unveränderliches freigegebenes PDF erzeugt:

- Viewer muss klar zwischen Source und freigegebenem Artefakt unterscheiden;
- freigegebenes Artefakt nicht als editierbar darstellen;
- Status/Version sichtbar;
- Download/Print nur gemäß erlaubten Actions.

---

# 44. Benutzerverwaltung — Minimal-Webslice

WEB01/Pilot benötigt mindestens eine klare Adminansicht für notwendige Benutzerverwaltung.

Muster:

- Liste links/zentral;
- Detail Read Mode;
- explizites Edit;
- Rollen/Berechtigungsdaten nicht clientseitig interpretieren;
- sensible Felder nicht in Tabellen zeigen;
- Passwortaktionen separat und bewusst.

Keine vollständige IAM-Suite erforderlich, wenn Pilotvertrag dies nicht verlangt.

---

# 45. Modulstatus und Fehlerisolation

## UX-D41 — kaputtes Modul ≠ kaputte App

Wenn Modul nicht verfügbar:

- Navigation kann Status anzeigen oder Eintrag für Admin deaktivieren;
- Modulroute zeigt verständliche Statusseite;
- andere Module/Shell bleiben nutzbar;
- keine endlose globale Exception-Seite.

Adminansicht darf Diagnose-/Correlation-Information anbieten.

---

# 46. Loading, Skeletons und Empty States

## 46.1 Loading

- bei initialen Daten ggf. Skeleton/Progress;
- kein Fullscreen-Spinner für jede kleine Mutation;
- Button während eigener Mutation lokal busy;
- parallele unbeteiligte Bereiche bleiben nutzbar.

## 46.2 Empty

Empty State erklärt:

- dass wirklich keine Einträge existieren bzw. Filter nichts finden;
- ggf. nächste erlaubte Aktion.

Unterscheiden:

- `Keine Dokumente vorhanden`
- `Keine Treffer für aktuelle Filter`
- `Daten konnten nicht geladen werden`

---

# 47. Context Menus / Rechtsklick

Rechtsklick darf Convenience bieten, ist aber niemals der einzige Zugang zu einer Aktion.

Alle wichtigen Aktionen müssen auch sichtbar/keyboardzugänglich erreichbar sein.

---

# 48. Sicherheitsnahe UX

## UX-D42 — Security nicht durch UI vortäuschen

- Versteckter Button ist keine Berechtigung;
- Disabled Button ist keine Berechtigung;
- lokale Route Guard ist keine Fachberechtigung;
- Clientrolle ist keine Fachberechtigung.

Backend bleibt autoritativ.

## 48.1 Reauth

Sensible Reauth-Flows:

- eigener Dialog/Step;
- Passwortfeld nie vorbefüllen;
- keine Persistenz;
- Fehler nicht verraten, was Sicherheitspolicy unnötig offenlegt;
- erfolgreiche Reauth nur für den vorgesehenen Vorgang/Zeitraum gemäß Backendvertrag.

---

# 49. Datenschutz / sensible Daten

- sensible Daten nicht unnötig in Tabellen-Vorschauen;
- keine Secrets in Fehlerdetails;
- keine Sessiontokens in URLs;
- keine Passwörter in Clientlogs;
- Clipboard-Aktionen bewusst einsetzen;
- Supportdetails dürfen Request-ID enthalten, nicht Credentialdaten.

---

# 50. Fehler- und Supportdetails

Für normale Benutzer:

```text
Speichern nicht möglich.
Der Datensatz wurde zwischenzeitlich geändert.
```

Sekundär aufklappbar:

```text
Fehlercode: document_conflict
Request-ID: ...
```

Rohtracebacks niemals in normaler Produktansicht.

---

# 51. UI-State vs. Fach-State

Zentral trennen:

## UI-State

- aktive Drawer;
- Filterpanel offen;
- ausgewählte Tabellenzeile;
- lokale Formdirtyness;
- Zoom;
- Dichte.

## Fach-State

- Dokumentstatus;
- Revision;
- Rollen;
- Workflow;
- Signaturen;
- Kommentare;
- Audit.

Fach-State kommt vom Backend. Kein Vue Store wird zur zweiten Fach-Datenbank.

---

# 52. Komponentenstrategie

Vuetify wird nur hinter QM-eigenen Komponenten/Patterns genutzt, damit Produktcode nicht überall direkt an Frameworkdetails hängt.

Beispielhafte Komponentenschicht:

```text
QMPage
QMPageHeader
QMModuleNav
QMDataTable
QMFilterBar
QMDetailPanel
QMForm
QMField*
QMActionBar
QMStatusChip
QMConfirmDialog
QMReasonDialog
QMErrorSummary
QMConnectionBanner
QMNotificationCenter
QMAttachmentList
QMObjectPicker
QMPdfViewer
QMSignatureWorkspace
QMHistoryTimeline
```

Nicht jede Komponente muss sofort existieren. Neue Fachansichten sollen aber vorhandene QM-Komponenten bevorzugen.

---

# 53. Generische Feldtypen

Der Generic Form Renderer soll mindestens auf folgende typische Typen vorbereitet sein:

- string;
- multiline text;
- integer;
- decimal;
- boolean;
- date;
- datetime;
- single select;
- multi select;
- user reference;
- object/reference;
- artifact/file reference.

Feldmetadaten können außerdem ausdrücken:

- required;
- editable;
- visible;
- help text;
- validation constraints;
- read-only reason;
- options source.

Clientseitige Vorvalidierung dient Komfort; Backend validiert autoritativ.

---

# 54. Saved Views

**BACKEND/PREFERENCES REQUIRED für Synchronisierung und Shared Views.** Lokale persönliche Views dürfen rein UX-seitig umgesetzt werden; serverseitige oder geteilte Views sind deferred.

Persönliche Saved View enthält typischerweise:

- Modul/View-ID;
- Filter;
- Sortierung;
- sichtbare Spalten;
- Spaltenreihenfolge;
- ggf. Dichte nur wenn view-spezifisch.

Shared Views:

- explizit administrativ/autorisiert;
- klar als geteilt markiert;
- nicht überschreibbar durch normalen Benutzer außer eigener Kopie.

---

# 55. Start-/Navigation bei Session

Nach Login:

1. Session und Benutzerkontext laden;
2. Modul-/Capabilityzustand laden;
3. persönliche Startpräferenz anwenden, falls gültig;
4. sonst Dashboard.

Bei fehlender Berechtigung für gespeicherte Startseite: auf Dashboard/Fallback navigieren, nicht Endlosschleife.

---

# 56. Wartungsmodus

Wenn Server Wartungsmodus meldet:

- gut sichtbarer globaler Banner;
- Reads ggf. entsprechend Serververtrag;
- Writes deaktiviert/abgelehnt;
- kein lokales Offline-Editing als Ersatz.

---

# 57. Lizenz-/Modulzustände in UX

Normale Benutzer sollen nicht mit Lizenztechnik belästigt werden.

Admin kann sehen:

- Modulname;
- Lizenzstatus;
- Aktivierungsstatus;
- Readiness;
- Fehlerzustand.

Bei nicht lizenziertem Fachmodul für normalen Nutzer bevorzugt vollständig aus Navigation entfernen.

---

# 58. Notification-/Action-Duplikation vermeiden

Eine Task darf den Benutzer direkt zur relevanten Resource/Action führen. Sie darf aber die Fachlogik nicht im Notification-Center duplizieren.

Beispiel:

`Dokument X wartet auf Review` → Öffnen → Dokumentdetail mit serverseitig erlaubter `Review annehmen`-Action.

---

# 59. Zustandslabels

Backendcodes und UI-Labels trennen.

Beispiel:

```text
backend: IN_REVIEW
ui.de: In Prüfung
```

Keine Fachlogik anhand übersetzter Labels.

---

# 60. Datum/Zeit

- serverseitig stabile Zeitrepräsentation;
- UI locale-aware;
- bei Audit/Signatur bei Bedarf Zeitzone klar;
- relative Zeit (`vor 5 Min.`) darf ergänzend sein, aber auditrelevante exakte Zeit muss zugänglich bleiben.

---

# 61. Confirmation-Muster

## Normale Aktion

Kein Confirm.

## Kritische Aktion

Kurzer Dialog mit Konsequenz.

## Destruktive Aktion

Konsequenz + ggf. Reason + eindeutiger Buttontext.

## Signatur

Eigener Reauth-/Finalisierungsschritt, nicht generischer Delete-Dialog.

---

# 62. Webclient und Backend-Gaps

Diese P0-Spezifikation enthält stabile Produkt-UX. Der veränderliche Implementierungsstand,
konkrete Repositorybelege, WEB01-Blocking und Owner-Checkpoints stehen ausschließlich in
`docs/WEBCLIENT_UX_CONTRACT_GAP_MATRIX.md` (P1).

Verbindliche Regel:

- `Already Supported` wird über den bestehenden Vertrag angebunden;
- `UX-only / WEB01` darf keinen neuen Backend- oder Fachvertrag vortäuschen;
- `Backend Contract Required Before WEB01` blockiert WEB01 bis WCON00 PASS ist;
- `OPS00/INT00 Relevant` bleibt im jeweiligen Operations-/Integrationsscope;
- `Deferred` wird nicht halbautoritativ im Browser nachgebaut.

WCON00 ist die schmale technische Voraussetzung zwischen OPS00 und INT00. WEB01 darf keine
Ersatzverträge, Hardcodes oder versteckte Fachlogik erfinden, um einen dort dokumentierten Gap
zu umgehen.

---

# 63. WEB01 — Mindestumfang der ersten vollständigen DMS-Webstrecke

WEB01 soll mindestens eine synthetische Browserstrecke ermöglichen:

1. Login, einschließlich des bestehenden Pflicht-Passwortwechsels, wenn der
   Server `password_change_required` liefert (bestehender Vertrag
   `/api/v1/auth/change-password`; keine neue Auth-Semantik im Browser);
2. Dokumentenpool öffnen;
3. Dokument anlegen/importieren;
4. Dokumentdetail sehen;
5. Rollen/Assignments gemäß Backendvertrag;
6. Workflow starten;
7. Bearbeitung abschließen;
8. Review/Approval mit getrennten Actor-Sessions;
9. ETag-Konflikt korrekt darstellen;
10. PDF-/DOCX-Kommentarpfade soweit im freigegebenen Scope;
11. Signaturpflicht erkennen;
12. Signature Workspace öffnen;
13. Signatur platzieren;
14. Reauthentifizieren;
15. signierte/freigegebene PDF-Version anzeigen;
16. History/Audit sichtbar machen;
17. Backendrestart überstehen;
18. Session-/Resourcezustand korrekt wiederherstellen.

Nicht in den Browser verlagern:

- Transitionregeln;
- Signaturvalidierung;
- ETag-Berechnung;
- Rechte;
- Datei-Persistenz;
- Workflowentscheidung.

---

# 64. Screen Acceptance Checklist — für Implementierungsagenten

Für **jede neue Seite** vor Fertigmeldung beantworten:

## Struktur

- [ ] Ist klar, welches fachliche Objekt/Problem die Seite bedient?
- [ ] Verwendet sie vorhandene Shell/Navigation?
- [ ] Ist sie Generic View, falls möglich?
- [ ] Ist Custom View begründet?
- [ ] Hat sie eine stabile Route?

## Backend

- [ ] Welche Endpoints/Contracts werden benutzt?
- [ ] Werden Rechte nur über Backend/allowed_actions bestimmt?
- [ ] Gibt es ETag/If-Match bei Mutationen, falls erforderlich?
- [ ] Keine Serverpfade?
- [ ] Keine lokale Fachpersistenz?

## UX

- [ ] Loading ≠ Empty ≠ Error?
- [ ] Read Mode vs Edit Mode klar?
- [ ] Dirty State vorhanden?
- [ ] Validierungsfehler feldnah?
- [ ] Primary Action eindeutig?
- [ ] Destructive Action geschützt?
- [ ] Keyboard/Focus sinnvoll?
- [ ] Connection Loss berücksichtigt?

## Security

- [ ] Keine Tokens/Passwörter persistiert?
- [ ] Keine clientseitige Rollenberechtigung?
- [ ] Keine Secrets in URL/Log?

## Tests

- [ ] Component Test für Kernzustände?
- [ ] Contract Test gegen erwartete API?
- [ ] 403/404/Conflict Negativpfade?
- [ ] Browser-E2E für kritischen Flow?

---

# 65. Anti-Patterns — ausdrücklich verboten

## AP-UX01 — Rollenprüfung im Frontend

Verboten.

## AP-UX02 — `localStorage` als fachliche Datenbank

Verboten.

## AP-UX03 — Serverpfad im Browser

Verboten.

## AP-UX04 — Modulspezifisches Vue-Bundle

Verboten.

## AP-UX05 — Jede Ansicht als Custom Component hardcoden

Verboten, wenn Generic Renderer ausreicht.

## AP-UX06 — PyQt 1:1 nachbauen

Verboten. PyQt ist Referenz für Fachverhalten, nicht Ziel-UX.

## AP-UX07 — Externes Referenzprodukt klonen

Verboten. Referenzen liefern Muster, keine Pixelvorlage.

## AP-UX08 — Disabled Button als Sicherheitsmaßnahme

Verboten als alleinige Maßnahme.

## AP-UX09 — Rohfehler/Traceback anzeigen

Verboten in normaler Produkt-UI.

## AP-UX10 — Modalkaskaden

Vermeiden. Normale Arbeit gehört in Seite/Panel.

## AP-UX11 — „Optimistische“ Fachmutation ohne Contract

Keine lokale Erfolgssimulation bei kritischen QM-Mutationen, wenn Server noch nicht bestätigt hat.

## AP-UX12 — Fake-Offline-Modus

Keine lokale fachliche Queue, die später blind synchronisiert.

---

# 66. Implementierungsreihenfolge innerhalb einer Fachansicht

Ein Agent soll diese Reihenfolge nutzen:

1. fachlichen Backendvertrag lesen;
2. benötigte Zustände und Actions auflisten;
3. Generic Pattern auswählen;
4. Route definieren;
5. Loading/Empty/Error/Forbidden/Conflict-Zustände planen;
6. Read Mode bauen;
7. allowed_actions anbinden;
8. Edit/Mutation anbinden;
9. Validation/Dirty/Conflict ergänzen;
10. Keyboard/A11y;
11. Tests;
12. erst danach visuelle Feinabstimmung.

Nicht zuerst hübsche Mockdaten-UI bauen und anschließend versuchen, Backendsemantik hineinzupressen.

---

# 67. Modell-spezifisches Übergabeformat

Wenn ein Implementierungsagent eine Ansicht baut, soll sein Plan mindestens enthalten:

```text
Screen: <Name>
Route: <route>
Pattern: Generic List | Generic Detail | Generic Form | Custom View
Backend contracts: <endpoints/contracts>
Required actions: <allowed_action codes>
Read states: <...>
Mutation states: <...>
Conflict behavior: <...>
Permission behavior: <...>
Loading/empty/error: <...>
Reusable QM components: <...>
New components justified: <...>
Tests: <...>
Out of scope: <...>
```

Ohne diese Zuordnung soll keine komplexe WEB01-Seite als „fertig geplant“ gelten.

---

# 68. Review-Regeln für GUI-PRs

Reviewer prüft mindestens:

1. **Contract correctness** — UI spiegelt echten Backendvertrag;
2. **Authorization correctness** — keine Rollen-/Policy-Duplikation;
3. **Generic-first** — keine unnötige Custom View;
4. **Consistency** — QM-Komponenten/Patterns wiederverwendet;
5. **State coverage** — Loading/Empty/Error/Conflict/Forbidden;
6. **Security** — Storage/Secrets/Pfade;
7. **Accessibility** — Focus/Keyboard/Labels;
8. **UX reference adherence** — bei Signature/Documents die hier festgelegten Referenzmuster;
9. **No fake completeness** — nicht vorhandene Backendfeatures werden nicht vorgetäuscht.

---

# 69. Screenshots / visuelle Abnahme

Für große neue Produktansichten soll die Evidence nach Möglichkeit enthalten:

- Desktop Standardzustand;
- Empty State;
- Validation State;
- Forbidden/disabled Action State, falls relevant;
- Conflict State bei ETag-relevanten Screens;
- Connection-Lost-Banner;
- responsive Narrow State;
- bei Signature: Platzierung + finale Vorschau.

Screenshots sind Ergänzung, kein Ersatz für Tests.

---

# 70. Konkrete Layoutentscheidung: Documents + Signature

Wenn ein Modell ohne weitere Designvorgabe WEB01 umsetzt, gelten folgende Defaults:

## Dokumentenpool

- linke globale Modulnavigation;
- Page Header mit Titel `Dokumente`;
- Suche + Filter kompakt oberhalb der Liste;
- Split View auf breitem Desktop;
- Tabelle links/zentral, Detailpanel rechts;
- Primäraktion `Neu/Importieren` nur wenn erlaubt;
- Auswahl bleibt beim Filterwechsel nur erhalten, wenn Resource weiter im Resultset/zugänglich ist.

## Dokumentdetail

- Read Mode zuerst;
- Header mit Titel/Status/Version;
- wenige Tabs: Übersicht, Dokument, Kommentare, Verlauf;
- nächste erlaubte Workflowaktion im Header/Action-Bereich;
- seltene Actions im Overflow.

## Signatur

- eigener Workspace;
- PDF nimmt größte Fläche;
- rechte Optionsleiste;
- Drag/Resize direkt auf PDF;
- Name/Datum/Uhrzeit toggelbar;
- Datum+Zeit gemeinsame Zeile;
- persönliches passendes Preset vorschlagen;
- finale Preview;
- Reauth;
- serverseitiger Abschluss.

Diese Defaults dürfen nur durch eine spätere explizite UX-Entscheidung ersetzt werden.

---

# 71. Feature Flags / noch nicht verfügbare Zielmuster

Wenn eine Funktion der Spezifikation noch nicht umgesetzt wird:

- keine tote Navigation zeigen;
- keine `Coming soon`-Kachel für jede geplante Funktion;
- Feature sauber ausblenden oder in Adminstatus als geplant markieren;
- keine Fake-Daten;
- Tests müssen klar sagen, welcher Scope implementiert ist.

---

# 72. Qualität der Texte

UI-Texte sollen:

- kurz;
- konkret;
- handlungsorientiert;
- ohne interne Architekturbegriffe sein.

Schlecht:

`DocumentsService rejected transition due to actor policy.`

Besser:

`Diese Aktion ist für Ihren aktuellen Workflow-Schritt nicht zulässig.`

Technischer Fehlercode darf sekundär verfügbar bleiben.

---

# 73. Statusdarstellung

Status-Chips:

- Text + semantische Farbe;
- nicht ausschließlich Farbe;
- überall gleiche Statusbezeichnung;
- keine zufälligen Modulfarben für identische Konzepte.

Beispiel:

- Entwurf
- In Prüfung
- Zur Freigabe
- Freigegeben
- Archiviert

Die tatsächlichen fachlichen Labels folgen dem jeweiligen Domainvertrag.

---

# 74. Progressive Disclosure

Komplexität nur zeigen, wenn sie gebraucht wird.

Beispiel:

- normale Nutzer sehen `Signieren`;
- erweiterte Platzierungsoptionen im Signature Workspace;
- technische Koordinaten höchstens Expert/Debug;
- Admin-Diagnose separat.

Keine Seite soll alle Möglichkeiten gleichzeitig zeigen, nur weil das Backend sie theoretisch kennt.

---

# 75. Präferenzen und Synchronisierung

Priorität:

1. serverseitig pro Benutzer, wenn Preference-Service vorhanden;
2. lokal nur UI-Komfortwerte;
3. keine fachliche Datenkopie.

Bei Konflikt zwischen lokalem alten UI-Wert und serverseitigem Preference-Wert gewinnt der autoritative serverseitige Wert bzw. eine definierte Migrationsregel.

---

# 76. Performance-UX

- Listen nicht komplett laden, wenn Pagination existiert;
- große PDFs inkrementell/renderoptimiert;
- keine unnötigen globalen Refetches;
- Suchfelder mit sinnvoller Debounce nur für Komfort, nicht als Fachlogik;
- Buttons sofort busy/disabled gegen Doppelclick, während Servermutation läuft;
- lange Jobs asynchron modellieren.

---

# 77. Browser Refresh / Deep Links

Jede stabile Fachroute muss direkten Reload vertragen:

- Session wird serverseitig wiederhergestellt;
- Resource wird neu geladen;
- UI darf nicht davon abhängen, dass Benutzer vorher über eine bestimmte Seite navigiert hat.

---

# 78. Back/Forward

Filter-/Detailnavigation soll Browserhistorie sinnvoll respektieren. Der Benutzer darf nicht durch selbstgebaute Routertricks in einer Seite „gefangen“ sein.

---

# 79. Upload-Sicherheit und UX

Bei Upload:

- akzeptierte Typen/Größen aus Contract/Config;
- Fehler verständlich;
- Fortschritt;
- kein Pfad aus Browserinput als Serverreferenz behandeln;
- Upload erst nach Backendbestätigung als fachlich vorhanden darstellen.

---

# 80. Umgang mit nicht lizenzierten Features

Normalnutzer:

- Feature/Modul nicht sichtbar, wenn nicht lizenziert.

Admin:

- darf Zustand `nicht lizenziert` sehen;
- UI kann erklären, warum Modul nicht verfügbar ist;
- kein Kauf-/Werbeoverlay als Kerninteraktion.

---

# 81. User Switching / Logout

Bei Logout:

- sensitive Clientstate leeren;
- fachliche Query-Caches leeren;
- keine Daten des vorherigen Users kurz im nächsten Login anzeigen;
- lokale rein persönliche Preferences sauber namespacen oder serverbasiert laden.

---

# 82. Session Timeout

Bei abgelaufener Session:

- offene ungespeicherte Formänderungen nicht unnötig zerstören;
- Login/Reauth-Flow abhängig vom Sicherheitsvertrag;
- Mutation nach Sessionverlust nicht blind wiederholen;
- Benutzer klar informieren.

---

# 83. Admin Settings

Nextcloud-artiges Grundmuster:

- linker Settings-Bereich bzw. klarer Category-Navigator;
- rechte Detailfläche;
- persönliche und administrative Kategorien getrennt;
- governance-kritische Settings mit zusätzlicher Bestätigung/Acknowledge gemäß Backendvertrag;
- normale Settings nicht mit technischen JSON-Editoren darstellen.

JSON-Editor nur für Entwickler-/Diagnosezwecke, nicht als normale Produktbedienung.

---

# 84. Systemdiagnose

Admin darf eine kompakte Readiness-/Statusansicht erhalten:

- Backend erreichbar;
- DB ready;
- Blobstore ready;
- Module status;
- Version;
- ggf. letzte Migration.

Keine Secrets/DSNs/Passwörter anzeigen.

---

# 85. Ausdruck und Download im Dokumentdetail

Wenn erlaubt, Output-Actions gehören in einen konsistenten `Weitere Aktionen`-/Output-Bereich.

Reihenfolge sollte fachlich klar sein:

- Anzeigen;
- Download, falls erlaubt;
- Drucken, falls erlaubt;
- Export/Nachweis nur in passenden Kontexten.

Nicht drei fast identische Iconbuttons ohne Text.

---

# 86. Signatur-Preset Auswahl

Wenn mehrere Presets existieren:

- `Zuletzt passend verwendet` als Vorschlag;
- Dropdown/Picker für alternative Presets;
- `Aktuelle Platzierung als persönliches Preset speichern` nur nach erfolgreicher/valider Platzierung;
- organisatorische Templates klar von persönlichen Presets unterscheiden.

---

# 87. Signatur-Zoom und Koordinaten

Technische Mindestregel:

- Signaturposition intern relativ/kanonisch zur PDF-Seite speichern;
- UI-Zoom ist reine Darstellung;
- Resize/Drag wird in Dokumentkoordinaten übersetzt;
- Wechsel von 80% auf 150% darf Position/Größe im finalen PDF nicht verschieben.

---

# 88. Signature Error States

MUSS sauber behandeln:

- Signaturasset fehlt;
- Reauth falsch;
- Dokumentrevision geändert;
- Workflowaktion nicht mehr erlaubt;
- Signatur außerhalb gültiger Seite/Bounds;
- Backend/Converter/Rendererfehler;
- Connection Loss vor Abschluss.

Nie Erfolg anzeigen, bevor Backend signierten Zustand bestätigt.

---

# 89. Kommentare — Interaction Defaults

- neuer Kommentar inline/Panel, nicht Fullscreen-Dialog;
- Antworten/Statusänderung nur wenn Backendmodell sie unterstützt;
- Kommentarautor/Zeit klar;
- gelöste Kommentare visuell weniger dominant, aber auffindbar;
- Filter `offen/alle` sinnvoll, wenn Statusmodell vorhanden.

---

# 90. Audit/History Darstellung

Timeline eignet sich für fachlichen Verlauf.

Jeder Eintrag:

- Aktion in verständlicher Sprache;
- Actor;
- Zeitpunkt;
- ggf. relevante Zustandsänderung;
- technische Details sekundär.

Keine künstliche Diffanzeige, wenn Backend keinen belastbaren vorher/nachher Zustand liefert.

---

# 91. Screen Ownership

Die SPA besitzt Screens und Routing zentral. Module liefern Datenverträge/Capabilities, keine eigenen Build-Artefakte.

Custom Views werden zentral registriert, z. B. sinngemäß:

```text
viewType: "signature-placement" -> QMSignatureWorkspace
viewType: "pdf-viewer"          -> QMPdfViewer
```

Keine dynamisch heruntergeladenen Modul-SPAs.

---

# 92. Metadata-driven Rendering

Wo Backend/Modul Metadaten liefert, soll UI daraus rendern können:

- Felddefinition;
- Label-Key;
- Typ;
- Sichtbarkeit;
- Editierbarkeit;
- Pflicht;
- Optionen;
- Relationstyp;
- ggf. Display hints.

Display hints dürfen nicht fachliche Validierungsregeln ersetzen.

---

# 93. Action Rendering Priority

Für aktuelle Resource:

1. eine Primary Action, wenn sinnvoll;
2. wenige Secondary Actions;
3. Rest im Overflow.

Wenn mehrere gleichwertige workflowkritische Entscheidungen existieren, dürfen zwei klare Aktionen nebeneinander stehen, z. B. `Annehmen` / `Ablehnen`.

Destruktive Aktion nie als versehentliche Default-Primary Action.

---

# 94. No-Data vs No-Permission

Nicht verwechseln:

- `Keine Daten vorhanden`
- `Sie haben keinen Zugriff`

Backend soll möglichst statusgerecht antworten; UI darf aus leerer Liste nicht schließen, dass Berechtigung fehlt.

---

# 95. Navigation bei 403/404

403:

- verständlich erklären;
- sinnvollen Rückweg.

404:

- Resource nicht vorhanden oder nicht auflösbar;
- keine internen Details.

Keine automatische Navigation zum Dashboard ohne Erklärung.

---

# 96. Confirmation nach erfolgreicher Mutation

Nach Erfolg:

- Resourcezustand aktualisieren;
- relevante Listen invalidieren/refetchen;
- kurzer Toast optional;
- Dialog schließen;
- nicht die ganze SPA neu laden.

---

# 97. Form Cancel

Wenn keine Änderungen: sofort zurück/Read Mode.

Wenn Dirty:

- `Änderungen verwerfen?`
- Optionen `Weiter bearbeiten` / `Verwerfen`.

Kein zusätzlicher Dialog nach erfolgreichem Save.

---

# 98. Tabellenaktionen

Preferred:

- Row click öffnet/selectiert Detail;
- Primary quick action nur wenn wirklich häufig;
- Overflow `…` für seltene Aktionen;
- Icons mit Tooltip/Accessible Label.

Nicht jede Action als eigene Spalte.

---

# 99. Filterpersistenz

Persönlich darf letzte Filter-/Viewauswahl wiederhergestellt werden, sofern dies nicht zu überraschenden „verschwundenen“ Daten führt.

Aktive Filter müssen immer deutlich sichtbar sein.

---

# 100. Release-/Review-Kriterium für diese Spezifikation

Eine Webclient-Implementierung entspricht dieser Spec erst, wenn:

- Architekturgrenzen eingehalten sind;
- zentrale Patterns konsistent sind;
- Documents/Signature gemäß den konkreten Layout-/Interaktionsentscheidungen umgesetzt sind;
- Backend-Gaps nicht durch Browserlogik kaschiert wurden;
- relevante Negativ-/Conflict-/Connection-Zustände implementiert und getestet sind;
- visuelle Abnahme keine eigenmächtigen Produktmuster zeigt.

---

# Anhang A — Kurzfassung der wichtigsten festen UX-Entscheidungen

1. Webclient ist die einzige neue Produkt-UI.
2. Vue 3 + TypeScript + Vite; Vuetify hinter QM-Komponenten.
3. Stabile linke Modulnavigation.
4. Schlankes Dashboard als Standardstart.
5. Generic-first: List/Detail/Form/History/Settings/Wizard.
6. Split View für datenintensive Liste→Detail-Arbeit.
7. Read Mode zuerst, explizites Edit.
8. Explizites Speichern für Fachmutationen; Autosave nur UI-Präferenzen.
9. Dirty State + Warnung bei Verlassen.
10. Backend-Validation feldnah anzeigen.
11. `allowed_actions` statt Rollenlogik im Client.
12. ETag-Konflikte als eigener UX-Fall.
13. Connection Loss: Ansicht stehen lassen, Writes sperren, Banner, Retry.
14. Persönliche Settings getrennt von Administration.
15. Tabellen personalisierbar; Saved Views vorbereitet.
16. Favoriten/Recent als persönliche Navigation.
17. Documents-Tasks über vorhandene Verträge; persistente zentrale Notifications deferred.
18. zentrale Jobs als deferred Zielmuster, nicht als WEB01-Fake.
19. Controlled Download deny-by-default.
20. Controlled Print backend-kontrolliert nur nach späterer OPS-/Contract-Freigabe.
21. PDF Viewer ist Custom View.
22. Signature Workspace ist DocuSeal-artiger Custom Flow.
23. Signatur frei per Drag/Resize auf PDF.
24. Name/Datum/Uhrzeit einzeln toggelbar.
25. Datum und Uhrzeit teilen dieselbe Zeile/Layoutposition.
26. Persönliche Signatur-Presets; zuletzt passendes Preset vorschlagen.
27. Reauth vor finaler Signatur.
28. Keine QES-/Envelope-/Public-Link-Behauptung in V1.
29. Deutsch zuerst, i18n ab Tag 1.
30. Desktop-first; Smartphone später selektive Flows.

---

# Anhang B — Referenzprodukt-Mapping

| QMTool-Bereich | Referenz | Übernommenes Muster |
|---|---|---|
| Shell / Settings / Notifications | Nextcloud | ruhige zentrale Shell, persönliche vs Admin-Einstellungen, zentraler Notification-Bereich |
| Datenlisten / Master-Detail | OpenProject | informationsdichte Tabellen, Filter, Split View |
| Dokumentenpool / Dokumentfokus | Paperless-ngx | dokumentzentrierte Suche/Filter/Detail/Viewer-Transition |
| Generic Forms | Directus / Frappe | metadata-driven Form-/Field-Rendering |
| Signature | DocuSeal | dokumentzentrierter Platzierungsworkspace, Drag/Resize, Preview, kurzer Abschlussflow |

Alle Referenzen sind Pattern-Referenzen, keine visuellen oder technischen Abhängigkeiten.

---

# Anhang C — Kanonische Repository-Integration

UX00 integriert diese Datei als P0. Dauerhaft gilt:

1. `docs/DOCS_CANONICAL_INDEX.md` führt sie unter P0.
2. `docs/GUI_SOURCE_OF_TRUTH.md` und `docs/GUI_ARCHITECTURE_PROJECT.md` verweisen auf sie.
3. AP-029 bindet WEB01 an diese Spec und WCON00.
4. Docs-Consistency-Tests schützen Status, Links und Kerninvarianten.
5. WEB01-Layouts sind nur gegen diese Spec reviewbar und dürfen keine abweichende Produkt-UX etablieren.

---

# Anhang D — Was diese Spec bewusst NICHT entscheidet

Diese UX-Spezifikation entscheidet nicht eigenmächtig:

- neue Fachstatus;
- neue Rollen oder Berechtigungen;
- neue Workflowtransitionen;
- Datenbankschemata;
- neue Auditsemantik;
- QES-Rechtsbewertung;
- genaue Signaturkryptografie;
- konkreten DOCX/DOTX-Converter;
- Serverdeployment;
- Backup-/Restore-Technik;
- neue Multi-Tenant-Funktionen.

Solche Entscheidungen bleiben in den zuständigen Architektur-/Fachpaketen.

---

# Anhang E — Verbindliche Agenten-/Implementierungsleitregel

> **Baue niemals eine neue QMTool-Seite aus dem Bauch heraus: nimm die zentrale Shell, wähle zuerst ein Generic Pattern, hole Zustände und erlaubte Aktionen vom Backend, behandle Loading/Empty/Error/Conflict/Connection explizit, verwende Custom Views nur für echte Spezialinteraktion und halte dich bei Documents/Signature an die hier festgelegten Referenzmuster.**
