# ADR: Grenze zwischen relationaler Datenbank und JSON

**Status:** Entscheidungsvorlage mit normativem Zielzustand
**Stand:** 2026-08-03
**Geltung:** Repository-weit; Umsetzung nur ueber separat freigegebene Arbeitspakete
**Bezug:** `JSON_STORAGE_INVENTORY.md`, `DATABASE_EVOLUTION_POLICY.md`, Documents-Artefaktpaket v2

## Kontext

QMToolV7 verwendet JSON heute in vier sehr unterschiedlichen Rollen: source-kontrollierte Konfiguration, mutable Laufzeitdateien, Textfelder innerhalb von SQLite und Austausch-/Nachweisformate. Diese Formen wurden bisher teilweise gleich behandelt, obwohl sie andere Anforderungen an Integritaet, Historie, Multiuser-Zugriff und Audit haben.

Besonders im Documents-Modul liegen Rollenpools, Entscheidungen, Profilsnapshot und fachliche Aenderungsdaten in JSON-Feldern. Gleichzeitig soll die Anwendung bald multiuserfaehig betrieben werden. Dateibasierte oder unstrukturierte fachliche Beziehungen wuerden dabei verlorene Updates, nicht validierbare Benutzerreferenzen und unvollstaendige Historien beguenstigen.

## Entscheidung

### 1. Relationale Daten sind der Standard fuer veraenderliche Fachlichkeit

In relationale Tabellen gehoeren:

- fachliche Stammdaten und versionierte Definitionen;
- aktueller fachlicher Zustand;
- Beziehungen zwischen Fachobjekten;
- Rollen, Berechtigungen und Benutzerzuweisungen;
- Entscheidungen, Widerrufe und auditpflichtige Zustandswechsel;
- Daten, die gefiltert, gejoint, eindeutig gemacht oder per FK validiert werden;
- fachliche Policies mit eigener Identitaet, Version oder Wirksamkeit.

JSON darf nicht verwendet werden, um fehlende Entitaeten, Zuordnungstabellen oder Transaktionsgrenzen zu umgehen.

### 2. Zulassige JSON-Spalten sind eng begrenzt

Eine JSON-Spalte innerhalb einer Datenbank ist zulaessig, wenn alle folgenden Bedingungen gelten:

- der Inhalt ist ein unveraenderlicher Snapshot, eine Event-Payload oder flexible Leaf-Metadaten;
- einzelne enthaltene Werte sind keine eigenstaendig referenzierten Fachobjekte;
- es gibt keinen benoetigten relationalen Join, FK, Unique Constraint oder fachlichen Filter auf Unterfelder;
- der Owner validiert ein benanntes Schema beziehungsweise eine Schema-Version;
- kanonische Serialisierung und, bei Nachweisen/Snapshots, ein SHA-256-Hash sind definiert;
- Kernidentitaeten und haeufige Suchfelder liegen daneben als typisierte Spalten vor;
- Mutation erfolgt nur ueber den fachlichen Owner und innerhalb seiner Transaktion.

Ein JSON-Feld wird nicht allein deshalb akzeptabel, weil SQLite JSON als `TEXT` speichern kann.

### 3. Neue fachliche JSON-Dateien sind verboten

Neue JSON-Dateien duerfen keine mutable fachliche Wahrheit, Benutzerbeziehung, Berechtigung, Entscheidung oder Workflowkonfiguration enthalten.

Zulaessige Dateien sind:

- signierte oder externe Import-/Exportformate;
- source-kontrollierte technische Manifeste und unveraenderliche Seeds;
- minimale Bootstrap-Informationen, die vor dem Oeffnen der Datenbank erforderlich sind;
- technische Logs, Gate-Ergebnisse und Betriebsnachweise;
- externe Crash-Journale, deren Zweck gerade das Erkennen einer unvollstaendigen DB-Operation ist.

Jede Ausnahme braucht einen benannten Owner, ein Schema, eine Version, eine Schreibstrategie und eine Begruendung, warum eine DB nicht geeignet ist.

### 4. Bootstrap bleibt minimal

QMToolV7 fuehrt keine zweite allgemeine Konfigurationswahrheit neben der Settings-Datenbank ein.

- Der App-Home-Pfad und Standard-SQLite-Pfade werden deterministisch abgeleitet.
- Deployment-seitige PostgreSQL-Verbindungen, Runtime-Profil und Secrets kommen aus der Umgebung beziehungsweise dem Secret Store.
- Nur Werte, die nachweislich vor dem Oeffnen der Settings-DB gebraucht werden und nicht ableitbar sind, duerfen ausserhalb der DB liegen.
- Secrets, Passwoerter und Sessiontoken duerfen nie in einer Bootstrap-JSON-Datei gespeichert werden.

### 5. Settings werden nach Owner getrennt

- Technische, flexible und selten abgefragte Settings duerfen als typisierte Keys mit `value_json` in einer Settings-DB liegen.
- Governance-kritische Aenderungen erhalten Revision, Actor, Zeitpunkt und Begruendung.
- Benutzerspezifische Einstellungen werden getrennt von modulglobalen Einstellungen gespeichert.
- Fachliche Policies mit Beziehungen oder eigener Versionierung liegen in Tabellen des Fachmoduls, nicht in einem generischen Settings-Blob.
- Datenbankpfade und vergleichbare Startparameter bleiben Bootstrap-Informationen.

### 6. Workflowprofile sind versionierte Fachobjekte

`workflow_profiles.json` wird nicht als Runtime-Wahrheit fortgefuehrt.

- Profildefinition und Profilversion sind relationale Entitaeten.
- Feste Status werden nicht als beliebige Profildaten gespeichert.
- Transitionen, Rollenbedarf, Entscheidungsregel, Signaturpflicht, Frist, Vier-Augen-Regel und `revoke_if_changed` sind strukturierte Zeilen.
- Historisch verwendete Profilversionen werden nicht geloescht.
- Deaktivierung ersetzt Loeschung.
- Eine laufende `WorkflowInstance` referenziert die Profilversion und speichert zusaetzlich einen unveraenderlichen, gehashten JSON-Snapshot.
- Die bestehende Datei darf nach der Migration nur noch kontrollierter Seed oder Export sein.

### 7. Assignments und Entscheidungen sind nie JSON-Listen

Editor-, Reviewer- und Approverpools werden als relationale Zuweisungen gespeichert. Tatsaechliche Review-/Approval-Entscheidungen sind eigene unveraenderliche Datensaetze. Widerruf erzeugt einen weiteren Nachweis statt die urspruengliche Entscheidung zu ueberschreiben.

Benutzer-IDs werden als kanonische Usermanagement-IDs gespeichert. Solange Usermanagement und Fachmodul in verschiedenen Datenbanken liegen, ist die Referenz eine validierte externe Identitaet und kein vorgetaeuschter lokaler FK.

### 8. Events werden transaktional persistiert

Jedes Fachmodul mit zustandsaendernden Domain-Events erhaelt eine Outbox im selben Datenbankowner wie der Fachzustand.

- Fachmutation und Outbox-Insert sind eine Transaktion.
- `event_id` und fachlicher Idempotency-Key sind eindeutig.
- Das Envelope fuehrt Actor, Aggregate, Correlation und Causation als Spalten.
- Die flexible, versionierte Nutzlast liegt in `payload_json`.
- Der synchrone `EventBus` darf vorlaeufig nach erfolgreichem Commit aus dem persistierten Datensatz bedient werden.
- Fehlende oder fehlerhafte Consumer machen die Fachmutation nicht rueckgaengig; der Eventdatensatz bleibt zur erneuten Zustellung bestehen.
- Das zustandsbasierte Dashboard bleibt bestehen, bis eine separat freigegebene Projektion nachweislich vollstaendig ist.

Die Outbox ist Zielarchitektur, aber weiterhin ein eigenes Arbeitspaket. Sie wird nicht still in den Documents-Kernumbau hineingezogen.

### 9. Audit und Events bleiben unterschiedliche Vertraege

Ein Domain-Event ist keine automatische Auditfreigabe. Auditpflichtige Entscheidungen und administrative Aenderungen benoetigen einen autoritativen, append-only Nachweis beim Fachowner. JSONL darf Export und technisches Log bleiben, aber nicht die einzige Wahrheit fuer transaktional gekoppelte Fachentscheidungen.

### 10. Migrationen sind vorwaertsgerichtet und nachweisbar

- Jede Schemaaenderung erhaelt eine neue nummerierte Migration und aktualisierten Manifestvertrag.
- Bestehende JSON-Daten werden vor Umschaltung gelesen, validiert, gezaehlt und gehasht.
- Unklare oder nicht referenzierbare Datensaetze werden nicht heuristisch repariert.
- Alte Strukturen bleiben bis zum bestandenen Vergleich erhalten, werden danach aber nicht parallel weiterbeschrieben.
- Es gibt keine dauerhafte Dual-Write-Architektur.
- Rollback erfolgt ueber den vor dem Upgrade erzeugten Backup-Satz, nicht durch Downgrade-SQL.

## Konkrete Anwendung auf Documents

| Inhalt | Entscheidung |
|---|---|
| Workflowprofildefinition/-version | relationale Tabellen |
| Profilsnapshot der laufenden Instanz | unveraenderliche JSON-Spalte plus Hash und Profilversions-FK |
| Editor/Reviewer/Approver | relationale `workflow_role_assignments` |
| Review/Approval | relationale `workflow_decisions` und separate Widerrufe |
| Bestehende Change Requests | im Kernumbau unveraendert erhalten; separates Fachpaket entscheidet eine spaetere relationale Ablage |
| Strukturierte Aenderungseintraege einer Version/Runde | relationale `document_change_entries` und `submission_round_change_entries`; keine Migration aus Change Requests |
| Word-/PDF-Kommentartext und Status | relationale Kommentarstruktur beibehalten/erweitern |
| PDF-Positionsanker | schema-versionierte JSON-Spalte beibehalten |
| Artefaktmetadaten | JSON-Spalte nur fuer flexible technische Leaf-Daten |
| Event-Payload | `payload_json` in transaktionaler Outbox |
| Read-Tracking | bestehende relationale Tabellen |
| Documents-Verteilerlisten | aus aktivem Documents-Zielmodell entfernen; historische Snapshots erhalten |

## Folgen

### Positiv

- Multiuser-Schreibvorgaenge erhalten DB-Transaktionen und Eindeutigkeitsregeln.
- Benutzer-, Rollen- und Workflowbeziehungen werden validierbar und abfragbar.
- Historische Profile und Entscheidungen bleiben nachvollziehbar.
- Events gehen nach einem erfolgreichen Fachcommit nicht mehr verloren.
- JSON bleibt dort erhalten, wo Flexibilitaet oder Austauschformat einen echten Nutzen haben.

### Aufwand und Risiken

- Bestehende JSON-Inhalte muessen semantisch klassifiziert werden; ein Parser allein reicht nicht.
- Cross-DB-Userreferenzen koennen erst nach dem freigegebenen UUID-Remapping vollstaendig hart validiert werden.
- Settings- und Auditmigration sind repo-weit und duerfen nicht mit dem ersten Documents-Use-Case vermischt werden.
- Alte Anwendungen duerfen eine nach diesem Umbau migrierte Datenbank gemaess Vorwaertsmigrationspolitik nicht mehr oeffnen.

## Nicht entschieden durch dieses ADR

Die wenigen verbleibenden Produktentscheidungen stehen ausschliesslich in `JSON_STORAGE_OPEN_QUESTIONS.md`. Bereits im Documents-Artefaktpaket entschiedene Status-, Rollen-, Publikations- und Kommentarsemantiken werden nicht erneut geoeffnet.
