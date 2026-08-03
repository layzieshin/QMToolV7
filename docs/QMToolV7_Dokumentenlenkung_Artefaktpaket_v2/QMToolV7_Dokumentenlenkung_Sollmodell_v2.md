# QMToolV7 – Fachliches Sollmodell der Dokumentenlenkung

**Stand:** 2026-08-03
**Ziel:** Verbindliche fachliche Grundlage für den schrittweisen Umbau des bestehenden `modules/documents`-Moduls.
**Wichtig:** Dieses Dokument beschreibt **keinen Greenfield-Neubau**. Vorhandene, funktionierende Logik wird erhalten und gezielt migriert.

## 1. Geltungsbereich und Leitprinzipien

Das Modul lenkt interne und externe Dokumente von der Planung über Entwurf, Prüfung, Freigabe und Veröffentlichung bis zu Ablauf, Archivierung oder Annullierung.

Leitprinzipien:

1. Dokumentidentität, Dokumentversion, Workflow und Dateien sind getrennte fachliche Objekte.
2. Es gibt höchstens eine aktuell gültige veröffentlichte Version je Dokumentenkennung.
3. Abgeschlossene Entscheidungen, Signaturen und Auditdaten werden niemals überschrieben.
4. Fachregeln werden im Service durchgesetzt; die GUI ist nicht die Autoritätsgrenze.
5. Der Umbau erfolgt kompatibel und schrittweise. Bestehende Funktionen für Artefakte, Signaturen, Verlängerung, Archivierung und Audit werden weiterverwendet.

## 2. Begriffe und fachliche Objekte

### 2.1 `DocumentPlan`

Ein Planungseintrag vor Beginn des gelenkten Dokumentenlebenszyklus.

- eigenes Objekt, **kein** `DocumentStatus`
- kein eigener Status
- frei veränderbar
- Pflicht: Titel und kurze Planungsbeschreibung
- optionale Vorbelegung: Dokumentenkennung, Dokumentenart, Fachbereich, Standort, regulatorischer Geltungsbereich, Dokumenteneigner, gewünschtes Workflowprofil
- Ersteller des Planungseintrags wird bei internen Dokumenten als Dokumenteneigner vorgeschlagen
- Umwandlung in Dokument + Version 1 + `DRAFT` erfolgt atomar
- nach erfolgreicher Umwandlung wird der Planungseintrag gelöscht
- erhalten bleibt ein Auditnachweis der Umwandlung

### 2.2 `Document`

Dauerhafte Identität über alle Versionen hinweg.

Felder:

- interne technische `document_uid`
- fachliche `document_id` / Dokumentenkennung
- aktuelle Kurzbeschreibung, optional und ohne neue Version änderbar
- aktuelle Dokumentenart
- aktueller Fachbereich, Standort und regulatorischer Geltungsbereich
- aktueller Dokumenteneigner bei internen Dokumenten
- dokumentbezogen gewähltes Standard-Workflowprofil bzw. Profilüberschreibung
- optional `manufacturer_or_publisher` für externe Dokumente
- Auditinformationen

Regeln:

- Dokumentenkennung ist eindeutig.
- Nach der ersten Einreichung bleibt die Kennung dauerhaft reserviert.
- Ein nie eingereichter `DRAFT` darf vollständig verworfen werden; dann wird die Kennung wieder frei.
- Kurzbeschreibung darf ohne neue Version geändert werden, aber immer mit Audit.
- Dokumentenart und andere nicht inhaltliche Metadaten darf der QMB mit Begründung ändern. Abgeschlossene Versionen behalten historische Snapshots.

### 2.3 `DocumentVersion`

Ein konkreter inhaltlicher Stand eines Dokuments.

Felder:

- technische eindeutige `version_record_id`
- `document_uid`
- sichtbare Versionsnummer
- Titel
- Änderungsanlass, Pflichtfeld
- strukturierte Änderungseinträge
- Snapshot der relevanten Dokumentmetadaten
- Status
- Gültigkeits- und Prüfdaten
- Artefaktbeziehungen
- Aufbewahrungsregel

Regeln:

- Version 1 beginnt bereits im `DRAFT` mit sichtbarer Versionsnummer 1.
- Eine Nachfolgeversion erhält die nächste Versionsnummer beim Anlegen.
- Je Dokument darf höchstens eine offene Nachfolgeversion existieren.
- Eine neue interne Version basiert auf einer Kopie der zuletzt aktuellen bearbeitbaren Quelldatei der Vorgängerversion.
- Eine neue externe Version entsteht durch Import einer neuen PDF.
- Nie eingereichte Entwürfe dürfen vollständig verworfen werden; ihre Nummer kann wiederverwendet werden.
- Ab erster Einreichung bleibt eine Versionsnummer grundsätzlich historisch reserviert.
- Ausnahme: Eine annullierte Fassung zählt nicht als reguläre offizielle Version; eine Korrekturfassung darf dieselbe sichtbare Versionsnummer verwenden. Technisch bleiben beide Datensätze über ihre `version_record_id` unterscheidbar.

### 2.4 `WorkflowInstance`

Konkreter Freigabeworkflow einer Dokumentversion.

- einer Dokumentversion können nacheinander mehrere Workflowinstanzen zugeordnet sein
- nie mehr als eine aktive Workflowinstanz gleichzeitig
- enthält eine unveränderliche Kopie/Snapshot der gewählten Workflowprofilversion
- enthält konkrete Rollenpools und Laufzeit-Overrides
- beginnt in `DRAFT`
- endet bei `APPROVED`, Abbruch oder Annullierung des Vorgangs

### 2.5 `SubmissionRound`

Ein Einreichungsdurchlauf innerhalb einer Workflowinstanz.

- beginnt mit Einreichung aus `DRAFT`
- endet durch fachliche Ablehnung oder erfolgreichen Abschluss
- Ablehnung führt immer zu `DRAFT` und erzeugt bei erneuter Einreichung eine neue Runde
- enthält Entscheidungen, Signaturen, Artefakte, Rollen, Zeitpunkte und Ablehnungsgründe

### 2.6 `WorkflowProfile` und `WorkflowProfileVersion`

Zentral verwaltete, benannte und versionierte Workflowdefinition.

- Profile werden nicht im Dokumentdialog bearbeitet.
- Profilname ist nur eine verständliche Bezeichnung, keine fachliche Einschränkung auf eine Dokumentenart.
- Dokumentenarten sind mit einem Standardprofil verknüpft.
- Beim Dokument darf vom Standard abgewichen werden.
- Beim Workflowstart wird die konkrete Profilversion fest in die Workflowinstanz übernommen.
- Spätere Profiländerungen verändern laufende oder abgeschlossene Workflows nicht.
- Alte Profilversionen dürfen kopiert und als Grundlage einer neuen Version verwendet werden.

## 3. Statusmodell

### 3.1 Feste Status

| Status | Bedeutung |
|---|---|
| `DRAFT` | Gelenkter Entwurf in Bearbeitung; Inhalt darf geändert werden. |
| `IN_REVIEW` | Eingereichter, fixierter Stand befindet sich in Prüfung. |
| `IN_APPROVAL` | Geprüfter Stand wartet auf Freigabeentscheidung. |
| `APPROVED` | Workflow erfolgreich abgeschlossen; Fassung ist unveränderlich, aber noch nicht veröffentlicht. |
| `PUBLISHED` | Ausdrücklich veröffentlicht und aktuell gültig; einzige Fassung, die andere Module abrufen dürfen. |
| `EXPIRED` | Automatisch abgelaufen; Freigabehistorie bleibt bestehen, normale Nutzer und andere Module haben keinen Zugriff. |
| `ARCHIVED` | Historische, nicht aktive Fassung. |
| `ANNULLED` | Formal oder fachlich ungültige Fassung; endgültig und nur für Audit/History erhalten. |

`PLANNED` entfällt als Dokumentstatus. `IN_PROGRESS` wird durch `DRAFT` ersetzt.

### 3.2 Lebenszyklus

Grundpfad:

`DRAFT → IN_REVIEW → IN_APPROVAL → APPROVED → PUBLISHED → ARCHIVED`

Profilabhängig können Prüfung oder andere Zwischenübergänge übersprungen werden. Es werden aber keine neuen, frei definierbaren Stufen eingeführt. Das Profil konfiguriert ausschließlich die **Übergänge zwischen den festen Status**.

Weitere Übergänge:

- fachliche Ablehnung aus jeder Workflowstufe → `DRAFT`
- Rücknahme einer noch nicht veröffentlichten Freigabe: `APPROVED → DRAFT`, gleiche Versionsnummer, neuer Workflow
- Ablauf: `PUBLISHED → EXPIRED` automatisch bei Überschreitung von `valid_until`
- erfolgreiche Verlängerung: `EXPIRED → PUBLISHED`, gleiche Version
- begründete Archivierung aus grundsätzlich jedem persistierten Zustand; laufender Workflow wird vorher beendet
- ungültige Fassung → `ANNULLED`, endgültig

### 3.3 Zentrale Statusinvarianten

- Maximal eine gültige `PUBLISHED`-Version je Dokument.
- `APPROVED` ist nicht über die öffentliche Dokumenten-API sichtbar.
- `PUBLISHED` ist unveränderlich.
- `EXPIRED`, `ARCHIVED` und `ANNULLED` sind für normale Nutzer und andere Module nicht abrufbar.
- Ein `EXPIRED`-Dokument darf durch normale Nutzer weder gelesen noch gedruckt werden; der QMB behält Zugriff zur Bearbeitung der Folgemaßnahmen.
- Die bisherige `PUBLISHED`-Version bleibt während der Bearbeitung einer Nachfolgeversion aktiv, sofern sie noch gültig ist.
- Ist sie abgelaufen, existiert sie weiter als `EXPIRED`, wird aber nicht mehr bereitgestellt.

## 4. Dokumentenarten und Kennungen

### 4.1 Konfigurierbare Dokumentenarten

Die bisher fest codierten Arten `VA`, `AA`, `FB`, `LS`, `EXT`, `OTHER` werden in konfigurierbare Stammdaten überführt.

Je Dokumentenart:

- Code und Bezeichnung
- aktiv/inaktiv
- Kennungsschema
- Standard-Workflowprofil
- optionale fachliche Standardwerte

Bereits verwendete Dokumentenarten dürfen nicht gelöscht, nur deaktiviert werden.

### 4.2 Dokumentenkennung

Interne Dokumente verwenden das organisationsspezifische strukturierte Kennungsschema. Die Kennung bildet die Prozesslandschaft bereits ab; ein zusätzliches Prozesslandschaftsfeld ist nicht erforderlich.

Beim Anlegen:

- nächste freie Kennung automatisch ermitteln **oder**
- Kennung manuell eingeben, etwa für Bestands- und Altdokumente

Lücken dürfen nur verwendet werden, wenn eine Kennung niemals dauerhaft genutzt wurde. Kennungen archivierter, abgelaufener oder obsoleter Dokumente bleiben reserviert.

Externe Dokumente erhalten ein eigenes Schema, derzeit `EXT` plus fortlaufende Zahl. Die Stellenzahl muss konfigurierbar sein, damit ein späterer Wechsel von zwei auf drei Ziffern möglich ist.

## 5. Metadaten und Änderbarkeit

### 5.1 Dokumentgebunden

- Dokumentenkennung
- Kurzbeschreibung, optional
- aktuelle Dokumentenart
- aktueller Fachbereich
- aktueller Standort
- aktueller regulatorischer Geltungsbereich
- aktueller Dokumenteneigner bei internen Dokumenten
- dokumentbezogene Workflowprofil-Voreinstellung/Überschreibung
- optional Hersteller/Herausgeber bei externen Dokumenten

Nicht inhaltliche Metadaten darf der QMB mit Begründung und Audit ändern, ohne eine neue Dokumentversion zu erzeugen. Historische Versionen behalten Snapshots.

### 5.2 Versionsgebunden

- Titel
- sichtbare Versionsnummer
- Änderungsanlass
- Änderungseinträge
- Freigabe-/Publikations-/Gültigkeitsdaten
- Artefakte
- Workflow- und Signaturnachweise

Der Titel darf nach Veröffentlichung nur über eine neue Version geändert werden.

### 5.3 Pflichtdaten beim Übergang zu `DRAFT`

- Dokumentenkennung
- Dokumentenart
- Titel
- bei internen Dokumenten ein Dokumenteneigner

Die Kurzbeschreibung ist optional. Ist sie leer, wird beim Übergang zu `DRAFT` und nochmals vor Veröffentlichung ein nicht blockierender Hinweis erzeugt.

## 6. Änderungsanlass und Änderungseinträge

Jede Version benötigt genau einen Änderungsanlass.

- Version 1: Grund der Neuerstellung
- spätere Versionen: Grund der Überarbeitung
- im `DRAFT` darf der QMB Tippfehler oder sachliche Fehler mit Begründung korrigieren
- mit der ersten Einreichung wird der Änderungsanlass festgeschrieben

Zusätzlich kann eine Version mehrere strukturierte Änderungseinträge besitzen:

- Beschreibung, Pflicht
- betroffener Abschnitt/Kapitel, optional
- Ersteller und Zeitpunkt automatisch
- Änderungen an Einträgen bleiben auditierbar
- bei Einreichung wird ausgewählt, welche Einträge tatsächlich in der eingereichten Fassung enthalten sind
- nicht enthaltene Einträge werden nicht gelöscht, sondern als nicht übernommen markiert
- enthaltene Einträge werden mit der Einreichung eingefroren

Ein automatischer DOCX-Diff ist außerhalb des aktuellen Umfangs, das Modell soll spätere Verknüpfungen/Anker aber ermöglichen.

## 7. Workflowprofile und Übergangsregeln

Das Profil definiert für jeden vorhandenen Übergang:

- ob der Übergang im Profil genutzt wird
- erforderliche konkrete Workflowrolle
- erforderlicher Rollenpool
- Zustimmungsregel `ONE_OF_POOL` oder `ALL_ASSIGNED`
- Signaturpflicht
- Bearbeitungsfrist, Standard unbegrenzt
- `revoke_if_changed`

Zusätzlich besitzt das Profil eine Vier-Augen-Regel.

### 7.1 Rollenpools und Zustimmungen

- Beim Workflowstart müssen alle laut Profil erforderlichen Rollenpools vollständig besetzt sein.
- Fehlende Pflichtrollen verhindern den Workflowstart; Status und Daten bleiben unverändert.
- `ONE_OF_POOL`: Eine berechtigte und konkret zugewiesene Person schließt die Stufe positiv ab.
- `ALL_ASSIGNED`: Alle beim Workflowstart beziehungsweise durch QMB-Änderung zugewiesenen Personen müssen positiv entscheiden.
- Bei `ALL_ASSIGNED` reicht eine Ablehnung, um die Stufe abzulehnen.
- Die Zuweisung zu einem Rollenpool braucht keine Zustimmung der zugewiesenen Person.

### 7.2 Vier-Augen-Regel

Zwei Sicherungsebenen:

1. Der Benutzer muss der erforderlichen Rolle im konkreten Workflow zugewiesen sein.
2. Ist `four_eyes_required` aktiv, darf dieselbe Person nicht zwei unmittelbar aufeinanderfolgende Prozessstufen ausführen.

Beispiel:

- Editor darf einreichen.
- Er darf anschließend nicht selbst prüfen.
- Nach Prüfung durch eine andere Person darf er, sofern als Freigeber zugewiesen, freigeben.

Ohne Vier-Augen-Regel darf dieselbe Person den gesamten Workflow nur dann durchführen, wenn sie allen erforderlichen Rollen konkret zugewiesen ist.

### 7.3 Änderungen im laufenden Workflow

Normale Nutzer dürfen Rollenpools und Workflowregeln im laufenden Workflow nicht ändern.

Der QMB darf mit Begründung:

- noch nicht tätig gewordene Personen austauschen
- Rollenpools ändern
- Laufzeitregeln der Workflowinstanz korrigieren

Für jeden Übergang kann `revoke_if_changed` gesetzt werden. Eine Sammeloption „Revoke on any“ setzt diese Option für alle Übergänge.

Wenn eine markierte Stufe betroffen ist:

- Rücksprung zur betroffenen Stufe
- Entscheidungen und Signaturen dieser und aller folgenden Stufen werden widerrufen, nicht gelöscht
- frühere erfolgreich abgeschlossene Stufen bleiben gültig

Beispiel: Prüfer A hat geprüft, der QMB ändert den Prüfer auf B. Rücksprung zu `IN_REVIEW`; Editor-Einreichung bleibt gültig, Prüfung A und spätere Entscheidungen werden widerrufen.

Eine fachliche Ablehnung ist davon getrennt: Sie führt immer vollständig zu `DRAFT` und beendet die aktuelle Einreichungsrunde.

### 7.4 Fristen

- Je Übergang/Stufe konfigurierbar
- Standard unbegrenzt
- Überschreitung verändert den Workflow zunächst nicht automatisch
- sie löst ein Event aus
- spätere Eskalationen können über Event-Consumer ergänzt werden

## 8. Workflowstart

Der Workflowstart ist atomar.

Erforderlich:

- vollständige Pflichtmetadaten
- vollständige Quelldatei
- ausgewählte Workflowprofilversion
- alle laut Profil notwendigen Rollenpools
- alle zugewiesenen Benutzer besitzen die erforderlichen Modulrollen/Berechtigungen
- keine weitere aktive Workflowinstanz derselben Version

Quelldateien:

- interne Dokumente: bearbeitbare Quelle, normalerweise DOCX
- externe Dokumente: importierte PDF

Bei Fehler oder Abbruch entsteht kein aktiver Workflow; die Version bleibt unverändert in `DRAFT`.

## 9. Ablehnung, Abbruch und Rücknahme

### 9.1 Fachliche Ablehnung

- Ablehnungsgrund ist Pflicht
- jede Ablehnung führt zu `DRAFT`
- alle Entscheidungen und Signaturen der aktuellen Einreichungsrunde bleiben historisch erhalten, gelten aber nicht weiter
- neue Einreichung erzeugt eine neue `SubmissionRound`

### 9.2 Workflowabbruch

- vorhandene normale Abbruchmechanik weiterverwenden
- Pflichtbegründung
- Version kehrt zu `DRAFT` zurück, sofern sie weiterbearbeitet werden soll
- bei einem nie eingereichten Entwurf ist vollständiges Verwerfen möglich

### 9.3 Rücknahme von `APPROVED`

Solange eine Fassung noch nicht veröffentlicht wurde:

- QMB kann Freigabe begründet zurücknehmen
- gleiche sichtbare Versionsnummer bleibt bestehen
- Version kehrt zu `DRAFT` zurück
- abgeschlossene Workflowinstanz bleibt im Audit erhalten
- eine neue Workflowinstanz wird gestartet

## 10. Artefakte und Signaturen

### 10.1 Grundregeln

- Artefakte gehören immer zu einer konkreten Dokumentversion.
- Workflow-/Entscheidungsartefakte werden zusätzlich der Workflowinstanz und Einreichungsrunde zugeordnet.
- Dateien verschiedener Versionen werden niemals überschrieben.
- aktuelle Quelle wird je Artefakttyp gekennzeichnet.

### 10.2 Interne Dokumente

- `DRAFT`: aktuelle DOCX ist bearbeitbare Quelle
- Einreichung: aktuelle DOCX wird in PDF konvertiert
- erforderliche Signaturen werden nach Profil auf der jeweiligen PDF-Stufe angebracht
- Prüfer erhält die Editor-signierte PDF, wenn der Übergang eine Editorsignatur verlangt
- Freigeber erhält die kumulativ signierte PDF
- finale Freigabe erzeugt die finale PDF

Scheitert Konvertierung oder wird eine Pflichtsignatur abgebrochen, erfolgt kein Statuswechsel.

### 10.3 Externe Dokumente

- direkte PDF-Übernahme
- keine interne Unterschrift erforderlich, sofern das Profil keine verlangt
- mindestens eine ausdrückliche Freigabeaktion ist Pflicht
- Original-PDF wird unverändert gelenkt

### 10.4 Artefakte bei Ablehnung

Pro abgelehnter Runde wird dauerhaft mindestens die PDF erhalten, die der ablehnende Akteur tatsächlich beurteilt hat.

- Review-Ablehnung: typischerweise editor-signierte PDF
- Freigabe-Ablehnung: typischerweise editor- und prüfersignierte PDF
- veraltete Zwischenkopien derselben Runde dürfen entfernt werden
- erhaltenes Ablehnungsartefakt wird mit Akteur, Zeitpunkt, Grund und Runde verknüpft

### 10.5 Veröffentlichung und Dateiname

Gelenkte Dokumente werden grundsätzlich als PDF veröffentlicht.

Einheitlicher Dateiname:

`<Dokumentenkennung>_<aktueller Titel>.pdf`

Keine Versions-, Status- oder Signaturzusätze im Dateinamen. Version und Signaturstatus werden über Dokumentinhalt und Historie nachvollzogen.

Wasserzeichen werden nur technisch vorbereitet und zunächst nicht aktiviert.

## 11. Freigabe, Veröffentlichung, Gültigkeit und Prüfung

### 11.1 Zeitpunkte

- `approved_at`: Zeitpunkt der Freigabeentscheidung/Signatur
- `published_at`: Zeitpunkt der ausdrücklichen Veröffentlichung
- `valid_from = published_at`
- `valid_until`: bei Freigabe festgelegt, muss zum Veröffentlichungszeitpunkt noch aktuell gültig sein
- Prüffrist läuft ab `approved_at`

### 11.2 Veröffentlichung

Voraussetzungen:

- Status `APPROVED`
- finales PDF vorhanden
- Pflichtmetadaten vollständig
- Freigabe ist zum Veröffentlichungszeitpunkt noch gültig
- ausführender Benutzer besitzt Berechtigung und ist fachlich autorisiert

Die Veröffentlichung ist eine eigene Aktion außerhalb des Freigabeworkflows.

Beim Veröffentlichen einer Nachfolgeversion werden in einem konsistenten Vorgang:

- neue Version `PUBLISHED`
- bisherige `PUBLISHED`-Version `ARCHIVED`
- Kopienrückruf für die Vorgängerversion ausgelöst

Es darf keinen Zwischenzustand mit zwei gültigen `PUBLISHED`-Versionen geben.

### 11.3 Gültigkeitsprüfung und Verlängerung

Standard:

- Prüf-/Gültigkeitsintervall: zwei Jahre
- Intervall ist konfigurierbar, aber nicht hardcoded
- maximal drei Verlängerungen
- jede Verlängerung verlängert `valid_until`
- `extension_count` wird erhöht
- nach der dritten Verlängerung gibt es kein weiteres `next_review_at`
- Verlängerung erzeugt keine neue Dokumentversion
- Ergebnis, Begründung, Akteur, Zeitpunkt und gegebenenfalls Signatur werden auditiert

Wenn eine neue Version erforderlich ist, wird keine Verlängerung ausgeführt.

### 11.4 Ablauf

Bei Überschreitung von `valid_until`:

- automatischer Statuswechsel `PUBLISHED → EXPIRED`
- API stellt die Version nicht mehr bereit
- normale Nutzer dürfen sie weder lesen noch drucken
- QMB erhält frühzeitige Warnungen vor Ablauf und eine Aufgabe bei Ablauf
- QMB kann verlängern, eine neue Version anlegen oder archivieren

Eine erfolgreiche Verlängerung setzt dieselbe Version wieder auf `PUBLISHED`.

## 12. Archivierung und Annullierung

### 12.1 Archivierung

- immer mit Begründung, Akteur und Zeitpunkt
- grundsätzlich für jede persistierte Fassung möglich
- laufender Workflow muss vorher beendet werden
- historischer Inhalt bleibt erhalten
- aus einer archivierten Dokumenthistorie kann später eine neue Version erzeugt werden
- existiert eine aktive Version, ist diese die Ausgangsbasis der Nachfolgeversion

### 12.2 Aufbewahrung

- Standard: unbegrenzt
- optional manuell konfigurierbare Aufbewahrungsfrist
- Fristende löst ein Event und eine QMB-Aufgabe aus
- keine automatische physische Löschung
- spätere Option: Datei entfernen, Metadaten und Auditnachweise erhalten
- vollständige physische Löschung bleibt zunächst ausgeschlossen

### 12.3 `ANNULLED`

- für formal oder fachlich ungültige Fassungen
- endgültiger Status der konkreten Fassung
- nicht bearbeitbar, nicht veröffentlichbar, nicht für normale Nutzer sichtbar
- Dateien, Workflow und Audit bleiben unverändert erhalten
- Korrektur erzeugt einen neuen internen Versionsdatensatz in `DRAFT`
- gleiche sichtbare Versionsnummer ist zulässig

## 13. Rollen und Berechtigungen

### 13.1 Systemrollen

- `ADMIN`: technische Gesamtverantwortung, Systemrollen, Logs und Systembetrieb; keine automatische fachliche Befugnis in der Dokumentenlenkung
- `QMB`: fachlicher Leiter des Dokumentenmoduls
- `USER`: normale Systemnutzung

Ein Admin darf nur fachlich im Dokumentenmodul handeln, wenn der QMB ihm zusätzlich eine passende Modulrolle erteilt.

### 13.2 Modulrollen

Modulrollen sind konfigurierbar. Berechtigungen werden Rollen zugeordnet; Benutzer dürfen mehrere Modulrollen besitzen.

Beispiele für Berechtigungen:

- Planungseintrag anlegen
- Dokument anlegen/konvertieren
- als Editor eingesetzt werden
- als Prüfer eingesetzt werden
- als Freigeber eingesetzt werden
- Workflow starten
- Rollenpools besetzen
- einreichen
- prüfen/ablehnen
- freigeben/ablehnen
- veröffentlichen
- verlängern
- archivieren
- annullieren
- Metadaten korrigieren
- Workflowregeln im laufenden Vorgang ändern
- kontrollierte Kopien verwalten
- Workflowprofile verwalten
- Dokumentenarten verwalten

Modulrollen bestimmen die grundsätzliche Eignung für Rollenpools und Aktionen. Workflowaktionen werden erst durch die konkrete Zuweisung im Workflow aktiviert.

### 13.3 QMB-Verwaltung

- QMB vergibt und entzieht Modulrollen
- QMB darf sich selbst Rollen erteilen
- optional kann der Admin eine Selbstzuweisungssperre aktivieren
- bei aktivierter Sperre benötigt der QMB einmalig eine Admin-Bestätigung; danach darf er sich selbst den bestätigten Rollenbereich zuweisen

### 13.4 Entzug und Benutzerdeaktivierung

- Benutzer werden nicht physisch gelöscht, nur deaktiviert
- Berechtigungen eines in einem laufenden Workflow benötigten Benutzers dürfen erst nach vollständiger Ersatzzuweisung entzogen werden
- Ersetzung und Entzug/Deaktivierung erfolgen konsistent
- historische Entscheidungen und Signaturen bleiben erhalten
- ausgeschiedene Beteiligte ändern abgeschlossene oder veröffentlichte Dokumente nicht automatisch

## 14. Dokumenteneigner und Workflowrollen

Interne Dokumente:

- besitzen zwingend einen Dokumenteneigner/Ersteller
- Owner wird beim Planungs-/Anlegevorgang vorgeschlagen
- Owner erhält automatisch die Editor-Eignung und wird beim Workflowstart typischerweise dem Editorpool zugeordnet
- Änderung durch QMB mit Begründung und Audit

Externe Dokumente:

- besitzen keinen internen Ersteller/Owner für den Inhalt
- benötigen mindestens einen internen Freigeber
- Hersteller/Herausgeber ist optionales Metadatum

Prüfer und Freigeber sind keine dauerhaften Dokumentfelder. Sie werden für jede Workflowinstanz neu aus den berechtigten Pools ausgewählt. Die zuletzt verwendeten Personen dürfen nur als Vorschlag dienen.

## 15. Gelenkte Ausdrucke und Kopien

Das Dokumentenmodul erhält eine globale Einstellung `managed_prints_enabled`.

Ist sie deaktiviert:

- Druckprotokoll kann weiterhin Nutzer, Zeitpunkt, Version, aufrufendes Modul und Anzahl erfassen.

Ist sie aktiviert:

- gilt sie für alle veröffentlichten Dokumente
- jeder Ausdruck muss über das Dokumentenmodul bzw. dessen API erfolgen
- mehrere Exemplare pro Druckauftrag sind erlaubt
- jedes Exemplar erhält eine eigene fortlaufende Kopiennummer
- Kopiennummer beginnt je veröffentlichter Version bei 1
- sichtbarer Vermerk, z. B. `Gelenkte Kopie Nr. 17`
- eindeutiger Schlüssel: Dokumentenkennung + Version + Kopiennummer
- erfasst werden mindestens Anwender sowie Datum/Uhrzeit

Bei Veröffentlichung einer Nachfolgeversion:

- alle Kopien der Vorgängerversion werden als rückzurufen markiert
- Event/Aufgabe an QMB mit Anzahl, Dokumentenkennung und Version
- Sammelbestätigung pro Version genügt
- erfasst werden vernichtete und nicht aufgefundene Exemplare
- fehlende Exemplare benötigen eine Begründung
- Rückruf darf begründet abgeschlossen werden
- spätere Abweichungsbearbeitung erfolgt im Fehler-/Abweichungsmodul

Nicht gültige Versionen dürfen nicht gedruckt werden.

## 16. Externe Dokumente, Vorlagen und Referenzen

### 16.1 Externe Dokumente

- eigene Kennung und vollständige Versionshistorie
- direkte PDF-Quelle
- kurzer, profilgesteuerter Freigabeweg
- mindestens Freigabeaktion
- kein separates Hersteller-Versionsfeld
- optional Hersteller/Herausgeber

### 16.2 Dokumentvorlagen

Vorlagen sollen später selbst gelenkte Dokumente mit eigener Kennung und Versionsfolge werden können.

- Architektur vorbereiten
- Funktion zunächst nicht aktiv verwenden
- aktuell bleiben `.dotx`/andere Vorlagen technische Dateien auf der Festplatte, die geöffnet und importiert werden

### 16.3 Dokumentreferenzen

Fachliche Referenzen beziehen sich auf die Dokumentenkennung und damit automatisch auf die aktuell gültige `PUBLISHED`-Version.

- strukturiertes Referenzmodell vorbereiten
- automatische Erkennung/Einfügung in DOCX/PDF nicht Bestandteil des aktuellen Umbaus
- zunächst bleiben Referenzen im Dokumentinhalt

## 17. Kommentarsystem

Die bestehende Kommentarfunktion ist verbindlicher Soll-Bestand und darf beim Umbau nicht reduziert oder entfernt werden.

### 17.1 Word-Kommentare

- Kommentare aus der jeweils aktuellen DOCX werden über den vorhandenen `DocxCommentReader` und `CommentSyncService` synchronisiert.
- Der Word-Autor bleibt Quellmetadatum. Audit-Actor ist der Benutzer, der die Synchronisierung ausführt.
- `source_comment_key` dient der Wiedererkennung und muss idempotente Synchronisierung ermöglichen.
- Ein in einer späteren DOCX fehlender Kommentar wird nicht automatisch aus der Historie gelöscht.
- Kommentare gehören mindestens zu Dokumentversion und Kontext; für das neue Modell werden zusätzlich Workflowinstanz, Einreichungsrunde und relevantes Artefakt zugeordnet.

### 17.2 PDF-Kommentare

- PDF-Kommentare bleiben mit Seite, optionalem Positionsanker, Artefakt-ID, Autor, Zeit und Text erhalten.
- Ein Kommentar darf nur einem zur betreffenden Version und aktiven Workflowrunde gehörenden PDF-Artefakt zugeordnet werden.
- PDF-Kommentare verändern die PDF-Datei selbst nicht.

### 17.3 Kommentarstatus und Historie

- Bestehende Status `ACTIVE`, `RESOLVED` und `INACTIVE` bleiben erhalten.
- Statusänderungen überschreiben weder Kommentartext noch Herkunft.
- Jede Statusänderung speichert Actor, Zeitpunkt und optionale Notiz und publiziert ein Event.
- Kommentare bleiben bei Ablehnung, erneuter Einreichung, Archivierung und Annullierung als historischer Nachweis erhalten.
- Neue Blockerregeln für offene Kommentare werden im Kernumbau nicht erfunden; sie bleiben ein gesondertes späteres Fachpaket.

## 18. Trainingsmodul und Sichtbarkeit

- Zielgruppen, Leseberechtigungen, Kenntnisnahmen und Schulungszuordnungen gehören vollständig zum Trainingsmodul.
- Das Dokumentenmodul besitzt keine eigenen Verteilungsrollen, Zielgruppen oder Vertraulichkeitsstufen.
- Eine Trainingszuordnung ist keine Voraussetzung für `PUBLISHED`.
- Veröffentlichung löst ein Event aus; das Trainingsmodul entscheidet anschließend über Sichtbarkeit und Aufgaben.

## 19. Öffentliche API

Die öffentliche Lese-API für andere Module liefert ausschließlich:

- Status `PUBLISHED`
- `valid_from <= now < valid_until`
- nicht archiviert, nicht annulliert, nicht abgelaufen
- finale veröffentlichte PDF

`APPROVED`, `EXPIRED`, `ARCHIVED` und `ANNULLED` werden nicht als aktive Dokumente bereitgestellt.

Weitere öffentliche Fähigkeiten:

- finale PDF einer gültigen veröffentlichten Version abrufen
- kontrollierten Druckauftrag auslösen
- Ereignisse abonnieren
- Dokumentkennung und Version als stabile Referenz verwenden

## 20. Events und Aufgabenrouting

Der ausführliche verbindliche Katalog steht in `QMToolV7_Dokumentenlenkung_Eventkatalog.md`.

Grundregeln:

- Jeder erfolgreiche Workflow- und Statusübergang publiziert ein eigenes versioniertes Domain-Event.
- Das Event enthält den tatsächlichen Ausgangs- und Zielstatus sowie Dokument-, Versions-, Workflow-, Runden-, Actor-, Correlation- und Causation-Bezug.
- Aktiviert der Übergang eine Aufgabe, enthält das Event außerdem die konkrete Aktion, Zielbenutzer beziehungsweise den Zielpool, Zustimmungsregel und Frist.
- Fehlende Consumer dürfen die Fachaktion nicht verhindern.
- Der aktuelle `EventBus` ist synchron und nicht dauerhaft. Ein nicht konsumiertes Event wird nicht gespeichert. Deshalb bleibt das Dashboard bis zu einer möglichen späteren Outbox/Projection zusätzlich aus dem aktuellen Fachzustand und den konkreten Zuweisungen ableitbar.
- Bestehende v1-Events werden kontrolliert auf v2 gemappt. Während der Migration ist Dual-Publish zulässig, sofern keine doppelte Consumerwirkung entsteht.
- Erfolgsereignisse dürfen nicht vor dem erfolgreichen Fachcommit publiziert werden.

Zwingend eventiert werden insbesondere alle Pfade:

`DRAFT → IN_REVIEW`, `DRAFT → IN_APPROVAL`, `DRAFT → APPROVED`,
`IN_REVIEW → IN_APPROVAL`, `IN_REVIEW → APPROVED`, `IN_REVIEW → DRAFT`,
`IN_APPROVAL → APPROVED`, `IN_APPROVAL → DRAFT`,
`APPROVED → DRAFT`, `APPROVED → PUBLISHED`,
`PUBLISHED → EXPIRED`, `EXPIRED → PUBLISHED`,
`PUBLISHED → ARCHIVED` sowie Übergänge zu `ARCHIVED` und `ANNULLED`.

## 21. Audit

Alle fachlich relevanten Änderungen und Entscheidungen werden auditiert.

Dazu gehören insbesondere:

- Plan, Dokument und Version anlegen, konvertieren oder verwerfen
- Metadatenänderungen
- Dateiimport, Konvertierung, Artefakterzeugung und Signatur
- Workflowstart, Abbruch, Rollen-/Pool-/Regeländerung
- Einreichung, Zustimmung, Ablehnung und Widerruf
- Veröffentlichung, Ablauf, Verlängerung, Archivierung und Annullierung
- Word-Kommentar-Synchronisierung, PDF-Kommentare und Kommentarstatusänderungen
- Modulrollen und Berechtigungen
- Ausdrucke, Kopiennummern, Rückruf und Vernichtung
- Aufbewahrungsfristen und Löschentscheidungen
- QMB-Sonderaktionen
- gesperrte oder unzulässige Zugriffsversuche

Mindestinhalt:

- Actor/User-ID
- wirksame System- und Modulrolle
- Zeitpunkt
- Aktion
- Dokument und Version beziehungsweise sonstiges Objekt
- vorheriger und neuer Zustand
- Ergebnis
- Begründung, wenn erforderlich
- Korrelations-/Workflow-/Runden-ID
- Artefakt-ID und Hash, wenn dateibezogen
- Kommentar-ID und Quell-/Positionsbezug, wenn kommentarbezogen

Reines normales Öffnen/Lesen wird im Dokumentenmodul nicht auditiert.

## 22. Use-Case-Auswahl und Edge Cases

- `01_Use_Cases` der Excel enthält den verbindlichen Kernkatalog mit 50 Use Cases.
- `12_Use_Case_Kandidaten` beziehungsweise `QMToolV7_Dokumentenlenkung_Use_Case_Kandidaten.md` enthält einen bewusst überbreiten Auswahlkatalog.
- Kandidaten werden erst nach ausdrücklicher fachlicher Auswahl verbindlich.
- Für jeden übernommenen mutierenden Use Case werden passende Edge Cases aus `13_Edge_Cases` beziehungsweise `QMToolV7_Dokumentenlenkung_Edge_Cases.md` in konkrete Tests überführt.

## 23. Bewusst zurückgestellte Punkte

- GUI-Aufbau und konkrete Dialogführung
- automatischer DOCX-Diff
- automatische Erkennung und Pflege von Dokumentreferenzen
- aktive Wasserzeichenfunktion
- vollständige physische Löschung historischer Daten
- neue Kommentar-Blockerregeln oder ein Neuentwurf des Kommentarsystems
- Change-Request-Prozess, soweit er über die bestehende Grundfunktion hinausgeht
- Training-/Sichtbarkeitslogik
- Abweichungsbearbeitung bei fehlenden Papierkopien
- dauerhafte Event-Outbox/Replay-Infrastruktur

Diese Punkte dürfen den Kernumbau nicht blockieren. Die bestehende Word-/PDF-Kommentarfunktion gehört ausdrücklich **nicht** zu den zurückgestellten Bestandsfunktionen; sie ist zu erhalten.
