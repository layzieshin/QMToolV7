# Offene Fragen zur JSON-Persistenz

**Stand:** 2026-08-03
**Regel:** Diese Liste enthaelt nur Entscheidungen, die weder durch kanonische Projektdokumente noch durch das Documents-Artefaktpaket v2 bereits beantwortet sind.

**J00-Bestaetigung:** OQ-01 bis OQ-09 sind vollstaendig und korrekt abgegrenzt. J00 entscheidet keine dieser Fragen und schliesst keine.

## OQ-01: Kanonische User-ID fuer Quermodule

**Sachverhalt:** Usermanagement PostgreSQL verwendet UUIDs. Documents, Training, Incident und Signature enthalten weiterhin historische String-IDs, teilweise in JSON-Listen. AP-028 M8 hat nur Prep/Inventar geliefert und bewusst kein Remapping vorgenommen.

**Zu entscheiden:**

- Wie wird jede bestehende String-ID eindeutig einer User-UUID zugeordnet?
- Wie werden geloeschte, umbenannte, unbekannte und System-Actors behandelt?
- Welches signierte/gehashte Mapping-Artefakt autorisiert die Migration?

**Empfehlung:** Separates Remapping-/Cutover-Paket mit Dry-run, eindeutiger Mappingtabelle, Blockerliste und bytegenau unveraenderten Quellen bei Fehler. Keine UUID aus Username oder Anzeigename heuristisch ableiten.

**Blockiert:** Produktive Migration von Documents-Assignments/Decisions und alle harten Userreferenz-Gates.
**Blockiert nicht:** Profilversionierung, lokale Schemaerweiterungen und reine JSON-Inventargates.

## OQ-02: Zulaessige Restkeys in `custom_fields_json`

**Sachverhalt:** `distribution_snapshot` kann zielgerichtet als historische Evidenz extrahiert werden. Bestehende `change_requests` sind laut Artefaktpaket fachlich nicht mit den neuen strukturierten Aenderungseintraegen identisch und bleiben bis zu einem separaten Fachpaket unveraendert. Weitere reale Keys und deren Nutzungs-/Abfragebedarf sind nicht vollstaendig aus dem Sourcecode ableitbar.

**Zu entscheiden:** Fuer jeden in realen Entwicklungs-/Pilotdaten gefundenen Key:

- fachliches Kernfeld, referenzierte Beziehung oder nur flexible Leaf-Metadaten;
- benoetigter Typ und Schema-Version;
- Such-/Filter-/Exportbedarf;
- Aufbewahrung und Audit.

**Empfehlung:** Vor J05 einen read-only Key-/Typ-/Haeufigkeitsreport ueber DB-Kopien erzeugen. Reservierte Namespaces anschliessend zentral sperren. Nur nicht referenzierte Leaf-Werte duerfen im Restblob bleiben.

**Blockiert:** Endgueltiges Cleanup von `custom_fields_json`.
**Blockiert nicht:** Migration bereits entschiedener Keys und historischer `distribution_snapshot`-Daten.

**Blockiert zusaetzlich:** Entfernung oder relationale Umdeutung von `change_requests`; dafuer ist das zurueckgestellte Change-Request-Fachpaket erforderlich.

## OQ-03: Owner fuer Standort- und Organisationsstammdaten

**Sachverhalt:** Das Documents-Sollmodell kennt aktuellen Fachbereich und Standort, definiert aber keinen repository-weiten Stammdatenowner. Freitext oder lokale Documents-Tabellen koennten spaeter erneut konkurrierende Wahrheiten erzeugen.

**Zu entscheiden:**

- Bleiben Standort/Fachbereich vorerst validierte Codes ohne zentralen FK?
- Oder entsteht ein separates, freizugebendes Organisationsstammdatenmodul?
- Welche Historie gilt bei Umbenennung/Deaktivierung?

**Empfehlung:** Fuer den fruehen Documents-MVP stabile Codes plus Anzeigenamensnapshot verwenden und keinen neuen Modulowner im Documents-Paket erfinden. Zentralisierung erst bei einem bestaetigten zweiten Consumer.

**Blockiert:** Endgueltige harte FKs fuer `site_id`/`department_id`.
**Blockiert nicht:** Documents-Kernworkflow und Entfernung der alten Verteilerlisten.

## OQ-04: Physischer Owner und Engine der Settings-Datenbank

**Status:** entschieden (2026-08-03), freigegeben fuer J02.

**Sachverhalt:** Der Zielvertrag trennt Bootstrap, technische Settings und Fachpolicies. Offen war, ob die allgemeinen Settings im fruehen Betrieb in einer backend-eigenen SQLite-Plattform-DB oder direkt in PostgreSQL liegen sollen. Clients duerfen die Datei keinesfalls gemeinsam oeffnen.

**Entscheidung:**

1. Engine und Owner: J02 verwendet eine **backend-owned SQLite**-Datenbank. Mehrere Clients greifen niemals direkt auf diese SQLite-Datei zu. `SettingsService` und seine Vertraege bleiben speicherunabhaengig, damit spaeter ein PostgreSQL-Adapter denselben fachlichen Pfad implementiert. Kein zweiter Settings-Service und kein paralleler fachlicher Pfad.
2. Scope: J02 unterstuetzt ausschliesslich den bestehenden Scope **`module_global`**. User- oder `user_module`-spezifische Settings sind nicht Teil von J02. Vorbereitende Tabellen oder APIs fuer noch nicht benoetigte User-Scopes werden nicht eingefuehrt.
3. Backup und Restore: Die Settings-Datenbank wird als **siebte Datenbank** in den gemeinsamen AP-027-Backup-, Restore-, Preflight- und Integritaetsvertrag aufgenommen. Kein separater Backup-Satz und kein unabhaengiger Migrationsmechanismus.

**Residual-Variante A (mitentschieden fuer J02):**

- Nur technische Schluessel (Bucket B) werden nach `platform_settings` migriert.
- Bootstrap-Schluessel (Bucket A) werden ausschliesslich ueber Env, feste Defaults oder bestehende Bootstrap-Vertraege aufgeloest.
- Fachliche Policy-Schluessel (Bucket C) werden nicht in `platform_settings` importiert; bis zum jeweiligen Owner-Paket ausschliesslich aus Residual-JSON (Allowlist, read-only).
- Kein Dual-Write, kein allgemeiner JSON-Fallback, keine heuristische Schluesselzuordnung.
- Derselbe Schluessel darf nie gleichzeitig in DB und Residual liegen (Overlap fail-closed).
- Residualarchiv ist Bestandteil jedes Plattform-Backup-Satzes (Manifest + SHA-256); Start und Restore pruefen die Pruefsumme.
- Residual-Reader und Allowlist sind zeitlich begrenzt und kein dauerhafter Kompatibilitaetspfad.

**Blockiert nicht mehr:** J02-Implementierungsplan und konkrete Migration Contribution.
**Blockiert nicht:** Modul-eigene fachliche Tabellen.

## OQ-05: Aufbewahrungs- und Exportvertrag fuer autoritatives Audit

**Sachverhalt:** Usermanagement besitzt bereits append-only PostgreSQL-Audit. Documents und andere lokale Module verwenden weiterhin generisches JSONL. Das Zielmodell verlangt autoritative modulnahe Auditzeilen, aber Aufbewahrung, Exportformat und Zugriff sind nicht abschliessend definiert.

**Zu entscheiden:**

- Aufbewahrungsdauer je Auditklasse;
- Zugriff fuer QMB, Admin und Support;
- revisionssicherer Export und dessen Signatur/Hashmanifest;
- Umgang mit personenbezogenen Daten nach Benutzerdeaktivierung;
- Zeitpunkt, ab dem JSONL nur noch Diagnose/Export ist.

**Empfehlung:** Autoritative DB-Zeilen frueh einfuehren, aber JSONL erst nach eigenem Audit-Retention-/Exportpaket abloesen. User-ID erhalten, Anzeigenamen nur snapshotten.

**Blockiert:** Abschaltung des generischen Audit-JSONL als Nachweisquelle.
**Blockiert nicht:** Transaktionales Documents-Audit im neuen Use Case.

## OQ-06: Outbox-Betriebspolitik

**Sachverhalt:** Tabellenstruktur und Transaktionsgrenze sind bestimmbar. Noch nicht entschieden sind die betrieblichen Grenzwerte des Dispatchers.

**Zu entscheiden:**

- maximale Retry-Anzahl und Backoff;
- Definition und Behandlung von `DEAD`;
- Retention publizierter Events;
- manueller Replay mit Berechtigung/Audit;
- spaeterer Broker oder weiterhin lokaler EventBus;
- Consumer-Idempotenzspeicher pro Consumer.

**Empfehlung:** Outbox-Insert und lokalen Dispatcher zuerst umsetzen; keine automatische Loeschung. Grenzwerte als versionierte technische Settings, Replay als explizit autorisierter Betriebs-Use-Case.

**Blockiert:** Produktionsreifer asynchroner Dispatch/Replay.
**Blockiert nicht:** Persistieren des Events in derselben Fachtransaktion und synchrones Publish nach Commit.

## OQ-07: Training-Antworten und Quiz-Snapshots

**Sachverhalt:** `selected_question_ids_json` und `presented_questions_json` sind plausible unveraenderliche Snapshots. Fuer `answers_json` ist nicht entschieden, ob Einzelantworten fachlich gesucht, langfristig auditiert oder nur als Attempt-Snapshot benoetigt werden.

**Zu entscheiden:** Im bereits vorgemerkten Paket "Training fachliche Konsolidierung" sind Auswertungsbedarf, Nachweisumfang, Korrekturregeln und Aufbewahrung festzulegen.

**Empfehlung:** Vor der Konsolidierung keine Normalisierung und keine neue JSON-Variante. Importhash und Dokumentversion weiter binden.

**Blockiert:** J08 und Cleanup der Training-JSON-Spalten.
**Blockiert nicht:** Documents-Multiuser-MVP.

## OQ-08: Incident-Policies und Timeline-Payloadschemas

**Sachverhalt:** Incident-Kategorien, Deadlines und CAPA-Regeln sind fachliche, governance-kritische Settings. Die konkreten Versionierungs-/Wirksamkeitsregeln und die erlaubten `timeline.details_json`-Schemas sind noch nicht fachlich freigegeben.

**Zu entscheiden:**

- Wirksamkeitsdatum und Historie von Policyversionen;
- welche laufenden Incidents alte Regeln behalten;
- Pflichtschema je Timeline-Entry-Type;
- welche Detail-IDs relational suchbar sein muessen.

**Empfehlung:** Eigenes Incident-Policy-Paket. Laufende Faelle referenzieren die angewandte Policyversion beziehungsweise einen Hashsnapshot.

**Blockiert:** Policyteil von J07.
**Blockiert nicht:** relationale Incident-Labels.

## OQ-09: Klassifikation unvollstaendiger Legacy-Workflows

**Sachverhalt:** Aktuelle `reviewed_by_json`/`approved_by_json` enthalten Benutzerlisten, aber nicht zwingend Entscheidungstyp, Zeitpunkt, Runde, Signaturbezug oder Widerruf. Das Artefaktpaket verbietet stille Klassifikation unklarer Bestandsdaten.

**Zu entscheiden:** Vor produktiver Migration muss fuer jeden unvollstaendigen Datensatz festgelegt werden, ob er als belegte Legacyentscheidung, nur als Legacyhinweis oder als Migrationsblocker gilt.

**Empfehlung:** Migrationsreport mit stabiler Datensatz-ID, vorhandener Evidenz und manueller Freigabespalte. Keine erfundenen Zeitpunkte, Runden oder Signaturen.

**Blockiert:** J04-Abnahme fuer betroffene Bestandsdaten.
**Blockiert nicht:** Leere/frische Datenbank und eindeutig belegte Fixtures.

## Bereits entschieden und daher nicht offen

- Feste Documents-Status und Ablehnung immer nach `DRAFT`.
- Workflow endet bei `APPROVED`; Publikation ist ein eigener Use Case.
- Profile sind zentral, benannt und versioniert; laufende Instanzen behalten ihren Snapshot.
- Editor/Reviewer/Approver und Entscheidungen werden relational modelliert.
- `ADMIN` besitzt keine automatische fachliche QMB-Befugnis.
- Word- und PDF-Kommentare einschliesslich `source_comment_key` und Anchor bleiben erhalten.
- Das Dashboard bleibt vorerst zustandsbasiert.
- Fehlende Consumer blockieren keine erfolgreiche Fachaktion.
- Documents besitzt im Ziel keine eigenen Sichtbarkeits-/Trainingsverteiler; Training entscheidet nach Publikation.
- Keine neue fachliche JSON-Datei, kein Greenfield-Modul und kein Big-Bang-Umbau.
- **OQ-04:** backend-owned SQLite Settings-DB als 7. AP-027-DB; nur `module_global`; Residual-Variante A fuer Bucket-C-Policies (siehe OQ-04).
