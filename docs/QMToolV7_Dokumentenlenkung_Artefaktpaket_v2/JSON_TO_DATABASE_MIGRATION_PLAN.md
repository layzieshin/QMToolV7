# Inkrementeller JSON-zu-Datenbank-Migrationsplan

**Status:** Planungsartefakt, keine automatische Freigabe zur Umsetzung
**Stand:** 2026-08-03

## Leitregeln fuer jedes Paket

- Ein Paket besitzt einen fachlichen Owner und einen klaren Hotspot.
- Keine neue oeffentliche API, wenn die bestehende `modules/<name>/api.py`-Fassade erweitert werden kann.
- Keine dauerhafte Dual-Write- oder Parallelrepository-Architektur.
- Alte Daten werden vor Mutation gesichert, gezaehlt, validiert und gehasht.
- Unklare Datensaetze blockieren fail-closed; keine heuristische Reparatur.
- Nach einer Vorwaertsmigration ist der Rollback der komplette vorherige Backup-Satz.
- GUI-Anpassungen folgen erst, wenn Fachlogik, Persistenz und CLI-Vertrag gruen sind.
- Jedes Paket ergaenzt nummerierte Migration, Manifest/Checksumme, Upgrade-Fixture, Frischaufbau, Datenerhalt, Idempotenz, zu-neue-DB-Test und Go-live-Gate.

## Reihenfolge

Die Pakete sind aufeinander aufbauend, aber nicht pauschal freigegeben. Die Documents-Pakete J03 bis J06 werden mit dem geplanten Documents-Umbauplan synchronisiert, damit kein zweiter Migrationsstrang entsteht.

## J00: Inventar- und Architekturbaseline

**Ziel:** Dieses Artefaktpaket als gepruefte Entscheidungsgrundlage etablieren.

**Betroffene Dateien:** Gesamtes Artefaktpaket v2 (16 Dateien inkl. Ursprungsdokumente und XLSX), die fuenf JSON-Analyseartefakte, Manifest, README/Arbeitsauftrag-Referenzen sowie ein expliziter Roadmap-Verweis.

**Tabellen/Migrationen:** Keine.

**Kompatibilitaet:** Keine Runtime-Aenderung.

**Validierung und Tests:** Repository-Suche gegen alle `*.json`/JSONL-Schreiber und `*_json`-Schemas; Docs-Pakettest `tests/docs/test_document_control_artifact_package.py`; Supervisor-Freigabe der ADR und offenen Fragen.

**Rollback:** Dokumentcommit zuruecknehmen.

**Abnahme:** Jede aktive Persistenzfundstelle steht in `JSON_STORAGE_INVENTORY.md`; echte Unklarheiten stehen ausschliesslich in `JSON_STORAGE_OPEN_QUESTIONS.md` (OQ-01 bis OQ-09).

**Alte JSON-Struktur entfernen:** Nie in J00.

### J00-Status (2026-08-03)

- Inventur-Verifikation und Abgrenzungen dokumentiert.
- OQ-01 bis OQ-09 bestaetigt als vollstaendige offene Punkte; keine OQ in J00 geloest.
- Roadmap-Verweis gesetzt: J00 nur Baseline; J01+ brauchen separate Freigaben; J03–J06 in den Documents-Umbau integrieren; kein paralleler Persistenzumbau.
- **Supervisor-Freigabe: erteilt am 2026-08-03 nach Staging-, Manifest- und Gate-Pruefung**

## J01: Schutzgates gegen neue fachliche JSON-Dateien

**Ziel:** Neue mutable fachliche JSON-Dateien und neue unregistrierte `*_json`-Spalten verhindern.

**Betroffene Dateien:** `scripts/json_persistence_gate.py` (einzige ausfuehrbare Allowlist), `scripts/database_migration_gate.py` (Check `no_unregistered_json_persistence`), `tests/interfaces/test_json_persistence_gate.py`, `.github/workflows/ci-gates.yml`. Keine P0-Aenderung an `MODULE_INTEGRATION_POLICY.md`.

**Tabellen/Migrationen:** Keine.

**Kompatibilitaet:** Allowlist der in der Inventur akzeptierten Dateien/Spalten (J00-IDs). Das Gate bewertet neue Funde (inkl. gestagt/untracked), nicht bestehende pauschal rot.

**Import/Dual-Read/Dual-Write:** Nicht anwendbar.

**Tests:** Negativfixture fuer neue Domain-JSON-/JSONL-Datei, neue JSON-Beziehungsspalte und unversionierte Snapshotspalte; Positivtests fuer Migration Manifest, Anchor und Legacy-Snapshot; gestagte und untracked Negativfaelle; Migration-Gate-Rotfall.

**Rollback:** Gate-Commit zuruecknehmen.

**Abnahme:** Ein neuer Fund braucht Kategorie, Owner und ADR-konforme Begruendung sowie Allowlist-Eintrag im Script.

**Alte JSON-Struktur entfernen:** Nie in J01.

### J01-Status (2026-08-03)

- Ausfuehrbare Allowlist-Owner: `scripts/json_persistence_gate.py` (Dokumente spiegeln nur).
- Repo-Modus: HEAD + Index (`git ls-files --cached`) + untracked; Scratch-Modus mit `source_files`; kein Git-Fallback.
- Runtime-/Fachlogik unveraendert; J02+ nicht gestartet.
- **Supervisor-Freigabe: ausstehend**

## J02: Settings-Persistenz trennen

**Ziel:** `settings.json` von gemischter Runtime-Wahrheit zu einem kontrollierten Importbestand machen.
**Status:** freigegeben zur Umsetzung (OQ-04 entschieden); Supervisor-Abnahme nach Implementierung ausstehend.
**Basis:** `origin/main` @ `71a7b43`.

**Betroffene Dateien:** `qm_platform/settings/*`, Runtime-/CLI- und Backend-Bootstrap, Settings-CLI/PyQt, Modul-Settings-Contributions, neue Plattformmigration, Backup/Restore, J01-Gate und Tests.

**Neue Tabellen/Migrationen:** Plattform-DB `platform_settings` (7. AP-027-DB) mit Tabellen `platform_settings` und `platform_setting_revisions`; nur `module_global`; technische Migration nach AP-027-Regeln. Residualarchiv zusaetzlich im Backup-Satz.

**Schluesselpartition (maschinell vollstaendig als `(module_id, setting_key)`):**

- Bucket A (Bootstrap): Pfade und Startparameter — Env/Defaults/Pfadresolver, nie `platform_settings`.
- Bucket B (technisch): Import in `platform_settings`, mutierbar, schema-validiert.
- Bucket C (Fachpolicy): Residual-JSON Allowlist, read-only, Owner + Folgepaket; nicht in `platform_settings`.

**Bootstrap-Reihenfolge (verbindlich):**

1. `app_home` und Env/Defaults bestimmen
2. Modul- und Plattform-Contributions registrieren
3. alle sieben `DatabaseSpec`s ohne `SettingsService` erzeugen
4. sieben Datenbanken migrieren
5. DB-basierten `SettingsService` oeffnen; Residualarchiv laden und SHA-256 pruefen; Overlap DB ∩ Residual fail-closed
6. erst danach Module und settingsabhaengige Plattformdienste verdrahten

Pfadleser in Modul-Wiring duerfen nicht weiter indirekt auf `settings.json` zugreifen.

**Uebergangskompatibilitaet:**

1. Dry-run klassifiziert alle Keys gegen Schema ∪ Defaults ∪ Callers ∪ Fixtures; unknown blockiert.
2. Bucket A → Bootstrap-Pfadresolver.
3. Bucket B einmalig schema-validiert importieren; Cutover ist journalisiert (`settings_cutover_journal.json`) und nach Abbruch resumierbar (kein stilles Skip bei vorhandenem Residual ohne Abschluss).
4. Lese-Vertrag: Bucket B aus `platform_settings`; Bucket C **ausschliesslich** aus Residual-JSON (nie Contribution-Defaults zur Laufzeit). Frischinstallation ohne Legacy-`settings.json` seedet Residual einmalig aus Contribution-Defaults und verankert den SHA-256 in `platform_settings_integrity`. Fehlendes Residual bei deklarierten C-Keys → fail-closed (`residual_archive_missing`). Oeffentlicher Dict-Vertrag: `B-defaults ⊕ B-DB ⊕ C-residual`.
5. Quell-`settings.json` wird byteidentisch archiviert und nicht mehr beschrieben.
6. Residualarchiv ist Bestandteil jedes Plattform-Backups (Manifest + SHA-256); Restore stellt es byte-exact wieder her. Laufzeit-Verankerung des Residual-Hash liegt in der DB (`platform_settings_integrity.residual_archive_sha256`), nicht in der Sidecar-Datei allein.

**Import:** Key/Typ/Modul gegen `SettingsContribution.schema` validieren; unbekannte Keys blockieren mit Report. Governance-kritische B-Werte erhalten Revision 1 mit Actor `migration:j02-settings-import`.

**Actors (kein stiller Fallback):**

- Benutzeraenderung: bestaetigter `UserContext` nur via `issue_user_context` (`_server_confirmed`); CLI/PyQt-Schreibpfade muessen ihn ueber `resolve_session` liefern. Objekte mit blossem `is_confirmed=True` sind ungueltig.
- Import: `migration:j02-settings-import`.
- Backend-Haertung/Bootstrap: `system:backend_bootstrap`.
- Der Legacy-Zustand `get_current_user()` / `current_user.json` darf **nicht** stillschweigend als Actor verwendet werden. Fehlt ein bestaetigter `UserContext` am Schreibpfad → fail-closed.
- J02 fuehrt keine lokale SQLite-Session ein. Klassische Desktop-/CLI-Runtimes bleiben fuer Settings-Schreibvorgaenge voruebergehend read-only. Der spaetere Desktoptransport bleibt J09 zugeordnet und nutzt denselben autoritativen PostgreSQL-Sessionpfad wie das Backend.

**`set_module_settings`-Semantik:** `values` ist die vollstaendige Bucket-B-Payload (Replace). Bucket-A → `bootstrap_setting_immutable`; Bucket-C → `residual_policy_readonly`; unknown → `unknown_setting_key`; fehlende Pflichtwerte → `missing_required_setting`. Kein stilles Strippen.

**Oeffentlicher Vertragswechsel Incident:** `IncidentManagementApi.set_module_settings` / Service erfordern ab J02 den Keyword-Parameter `actor` (bestaetigter `UserContext` oder System-/Migrationsactor). Aufrufe ohne `actor` sind ungueltig (`TypeError`). Bucket-C-Payloads bleiben auch mit Actor fail-closed (`residual_policy_readonly`).

**Dual-Read/Dual-Write:** Kein Dual-Write. Vergleichslauf gegen Residualarchiv erlaubt. Kein allgemeiner JSON-Fallback.

**Tests:** Klassifikations-Vollstaendigkeit; Verlustfreie B-Uebernahme; unknown/A/C-Writes; Overlap; Residual-Hashdrift gegen DB-Anker; Cutover-Resume nach Injiziertem Fehler zwischen Modulimporten; 7-DB-Backup inkl. Residualarchiv; Actor ohne Legacy-/Forged-Fallback; J01 Residual-Reader Positiv- und Writer-Negativtests; Incident-`actor`-Vertragswechsel.

**Rollback:** Voller Backup-Satz (7 DBs + Residualarchiv) plus vorherige Anwendung.

**Abnahme:** Effektive Settings konsistent; Vergleichsreport gruen; Bucket-C als Restblocker; kein produktiver Writer auf `settings.json`; keine zweite Sessionpersistenz oder lokale Tokenwahrheit.

**Alte JSON-Struktur entfernen:** Residual-Reader/Allowlist erst nach letztem Owner-Paket (nicht in J02). Fachpolicykeys erst in ihren Owner-Paketen.

## J03: Documents-Workflowprofile versionieren

**Ziel:** `workflow_profiles.json` und `WorkflowProfileStoreJSON` aus dem Runtime-Schreibpfad entfernen.

**Betroffene Dateien:** `modules/documents/profile_store.py`, Documents Contracts/Service/API/Wiring, `modules/documents/workflow_profiles.json`, neue Documents-Migration, CLI-first Profilverwaltung, Profiltests und Packaging.

**Neue Tabellen/Migrationen:** `workflow_profile_definitions`, `workflow_profile_versions`, `workflow_profile_transitions`, `document_type_definitions` beziehungsweise deren bestehender Owner.

**Uebergangskompatibilitaet:** Bestehende oeffentliche Profil-DTOs bleiben zunaechst als Read-Model. Der neue Store rekonstruiert sie aus Tabellen. Keine zweite oeffentliche Profil-API.

**Import:**

- Datei vor Import hashen und gegen erwarteten Paket-/Operatorhash dokumentieren.
- `IN_PROGRESS` kontrolliert nach `DRAFT` uebersetzen.
- `phases` deterministisch in Transitionen ueberfuehren.
- Jede Profil-ID als stabile Definition und Inhalt als Version 1 anlegen.
- Doppelte IDs, unbekannte Status/Regeln oder semantisch unvollstaendige Profile blockieren.
- Angepasste lokale Profile werden nicht durch den gebundelten Seed ueberschrieben.

**Dual-Read/Dual-Write:** Kein Dual-Write. Vor Umschaltung erzeugt ein Vergleichsgate fuer jedes Profil dasselbe kanonische DTO aus Datei und Tabellen. Danach wird nur relational gelesen/geschrieben.

**Tests:** Alle bestehenden Profilvarianten, alte Profilversion erhalten, Deaktivierung statt Loeschung, Hashdrift, ungueltiger Import, frische DB, Upgrade, Packaging ohne Runtime-Dateischreiber.

**Rollback:** Documents-Backup-Satz und vorherige Anwendung.

**Abnahme:** Alle Profile semantisch gleich oder explizit blockiert; neue Version veraendert alte Instanzen nicht; GUI/CLI schreiben keine Profildatei mehr.

**Alte JSON-Struktur entfernen:** Runtime-Reader/-Writer nach bestandenem Vergleich entfernen. Die Datei darf als versionierter Seed/Export im Paket bleiben, nicht als mutable Wahrheit.

## J04: Documents-Workflowinstanzen, Assignments und Decisions normalisieren

**Ziel:** `workflow_profile_json`, Actorpools und Entscheidungslisten aus `document_versions` herausloesen.

**Betroffene Dateien:** Documents-Migrationen, Repository, Contracts/Read-Model, Workflow-Use-Cases, API, Event-/Auditpfad und Tests. Keine GUI-Fachlogik.

**Neue Tabellen/Migrationen:** `workflow_instances`, `workflow_transition_instances`, `submission_rounds`, `workflow_role_assignments`, `workflow_decisions`, `workflow_decision_revocations`.

**Uebergangskompatibilitaet:** Das bestehende `DocumentVersionState` wird aus den normalisierten Tabellen rekonstruiert, solange CLI/PyQt es benoetigen. Alle neuen Writes laufen durch den kanonischen Workflow-Use-Case.

**Import:**

- Je Legacyversion Status, `workflow_active`, Profilsnapshot, Pools, `reviewed_by`, `approved_by` und Signaturflags gemeinsam klassifizieren.
- Eindeutige Benutzer gegen den freigegebenen User-ID-Mappingvertrag pruefen.
- Nur beweisbare Entscheidungen anlegen. Fehlender Zeitpunkt/Actor/Stage wird im Migrationsreport markiert und nicht erfunden.
- Maximal eine aktive Instanz pro Version erzwingen.

**Dual-Read/Dual-Write:** Kein Dual-Write. Migration backfillt Tabellen, Vergleichsgate prueft Read-Model, dann schaltet derselbe Release den Repository-Reader/-Writer um. Alte Spalten bleiben eine Version lang read-only.

**Tests:** Poolregeln, Vier-Augen, ONE_OF_POOL/ALL_ASSIGNED, parallele Entscheidung, Rejection nach DRAFT, Revocation, Deaktivierung/Replacement, Snapshotimmutabilitaet, Datenerhalt und Transaktionsrollback.

**Rollback:** Documents-Backup-Satz; keine Down-Migration.

**Abnahme:** JSON- und neues Read-Model sind fuer alle freigegebenen Fixtures gleich; unklare Produktionskopien blockieren; neue Writes aendern keine Legacy-JSON-Spalte.

**Alte JSON-Struktur entfernen:** In separater Cleanup-Migration nach einem Release ohne Legacy-Writes und bestandenem Byte-/Zeilenvergleich.

## J05: Documents-Custom-Fields und Verteiler kontrolliert abgrenzen

**Ziel:** Entschiedene Kernfachlogik aus `custom_fields_json` entfernen, die im Sollmodell entfallenen Documents-Verteiler sicher stilllegen und den zurueckgestellten Change-Request-Key ohne Umdeutung erhalten.

**Betroffene Dateien:** Documents-Migration, Repository, Metadatenvalidierung, API-kompatibles Read-Model, Export und Tests. Change-Request-Use-Cases werden in diesem Paket nicht fachlich erweitert.

**Neue Tabellen/Migrationen:** `document_change_entries` und `submission_round_change_entries` nur fuer die neuen strukturierten Aenderungseintraege des Sollmodells; optional klar benannte Legacy-Snapshottabelle/-spalte fuer historische Verteilerdaten. Keine Change-Request-Zieltabelle ohne separates Fachpaket.

**Uebergangskompatibilitaet:** `custom_fields` bleibt im DTO fuer echte Erweiterungsmetadaten. Reservierte Kernkeys werden daraus entfernt und durch typisierte API-Felder/Use-Cases bedient.

**Import:**

- Reale Key-/Typstatistik erzeugen.
- `change_requests` nur inventarisieren, validieren und bytegenau erhalten; keine Umdeutung zu Aenderungseintraegen und kein neuer Lifecycle.
- `distribution_snapshot` kanonisch als historische, immutable Evidenz binden.
- Aktive `distribution_*_json`-Listen nur nach Consumer-Suche und fachlichem Report stilllegen; keine Zielgruppen in Documents neu erfinden.

**Dual-Read/Dual-Write:** Vergleichslesung ist erlaubt; Writes gehen nach Umschaltung nur in die neue Struktur. Der Restblob darf keine reservierten Keys mehr annehmen.

**Tests:** Bestehender Change-Request-Export und bytegenauer Erhalt, unbekannte Keys, reservierte Keys, parallele Aenderung, historische Snapshotgleichheit, Training-/Registry-Consumer-Suche sowie Negativtest gegen eine Change-Request-zu-Change-Entry-Umdeutung.

**Rollback:** Documents-Backup-Satz.

**Abnahme:** Kein Workflow-, Assignment- oder Registrykernzustand liegt im Restblob; neue strukturierte Aenderungseintraege sind relational. Der zurueckgestellte Change-Request-Bestand bleibt bis zu seinem Fachpaket klar gekennzeichnet und unveraendert; Word/PDF-Kommentare und bestehende Exporte bleiben funktionsfaehig.

**Alte JSON-Struktur entfernen:** Einzelne JSON-Spalten/Keys erst nach Consumer-Gate. `change_requests` darf erst nach dem separaten Fachpaket entfernt werden; der uebrige Rest-`custom_fields_json` bleibt nur fuer ADR-konforme Leaf-Metadaten.

## J06: Documents-Outbox und autoritatives Audit

**Ziel:** Erfolgreiche Documents-Zustandswechsel transaktional mit dauerhaftem Event und Auditnachweis koppeln.

**Betroffene Dateien:** Documents-Migration, bestehender Eventing-Owner, Workflow-/Publikations-Use-Cases, `qm_platform`-Outbox-Port/Dispatcher, EventBus-Adapter, Auditexport und Tests.

**Neue Tabellen/Migrationen:** `outbox_events`, `document_audit_events` im Documents-DB-Owner.

**Uebergangskompatibilitaet:** Bestehender synchroner EventBus bleibt. Nach Fachcommit wird exakt das persistierte Envelope publiziert. Dashboard bleibt zunaechst zustandsbasiert.

**Import:** Alte fluechtige Events werden nicht erfunden. Bestehende nachweisbare Legacyfelder koennen als gekennzeichnete Migrationsevidenz importiert werden, nicht als vollstaendige Eventhistorie.

**Dual-Read/Dual-Write:** Waehrend der Eventvertragsmigration ist kontrolliertes v1/v2-Dual-Publish nur gemaess Artefaktpaket und mit idempotenten Consumern erlaubt. Es gibt nur einen Outbox-Datensatz pro fachlichem Ereignis.

**Tests:** Fachrollback bei Outbox-/Audit-Insertfehler, genau ein Event je Erfolg, kein Event bei Ablehnung/Fehler ausser explizitem Denied-Event, Retry, Doppelzustellung, Correlation/Causation, Payloadhash, Consumer-Ausfall ohne Fachrollback.

**Rollback:** DB-Backup. Dispatcher kann deaktiviert werden, ohne Outboxzeilen zu verlieren.

**Abnahme:** Jeder im v2-Katalog verpflichtende Workflow-/Statusuebergang besitzt getestetes persisted Envelope; JSONL ist nicht mehr einzige Auditwahrheit.

**Alte JSON-Struktur entfernen:** Direkte Erfolgs-Publishes erst nach vollstaendiger Eventmatrix und Consumerpruefung; JSONL-Audit erst nach freigegebenem Export-/Retentionvertrag.

## J07: Incident-JSON normalisieren

**Ziel:** Abfragbare Labels und fachliche Incident-Policies relationalisieren, flexible Historien-/Artefaktmetadaten bewusst behalten.

**Betroffene Dateien:** Incident-Migration, Repository, Settings/Policy-Owner, API/Read-Model, CLI-first Tests.

**Neue Tabellen/Migrationen:** `labels`, `incident_labels`; fuer freigegebene Policies typisierte/versionierte Tabellen fuer Kategorien, Deadlines und CAPA-Regeln.

**Uebergangskompatibilitaet:** Bestehende Listen-/Dict-Vertraege werden aus Tabellen rekonstruiert. `timeline.details_json` und `artifact.metadata_json` bleiben schema-versioniert.

**Import:** Labels trimmen/deduplizieren; unbekannte Policyformen blockieren statt Defaults zu setzen.

**Dual-Read/Dual-Write:** Kein dauerhafter Parallelpfad; wie J04 Backfill, Vergleich, Umschaltung, spaeter Cleanup.

**Tests:** Filter/Reports, doppelte Labels, Policyversion, Audit, Backup/Restore, unveraenderliche Timeline.

**Rollback:** Incident-DB-Backup.

**Abnahme:** Labelabfragen benoetigen kein JSON-Parsen; fachliche Policies haben Actor/Version.

**Alte JSON-Struktur entfernen:** `labels_json` nach Vergleichsrelease; fachliche Keys aus `settings.json` nach jeweiliger Policyabnahme.

## J08: Training-JSON nach Fachkonsolidierung

**Ziel:** Nur die in der separaten Training-Konsolidierung bestaetigten JSON-Grenzen umsetzen.

**Voraussetzung:** Roadmap-Paket "Training fachliche Konsolidierung" ist abgeschlossen. Dieses Paket darf nicht vorher fachliche Antworten erfinden.

**Betroffene Dateien:** Training-Migrationen, Quiz-/Kommentar-/Audit-Repositories, Training-API und CLI-first Tests.

**Neue Tabellen/Migrationen:** Abhaengig von der Fachentscheidung, insbesondere moegliche `training_quiz_answer_items`; keine Aenderung an Tag-/Assignmenttabellen ohne Bedarf.

**Uebergangskompatibilitaet:** Verschluesselte Quiz-Imports bleiben gehashte Austauschblobs. Snapshotfelder bleiben, sofern die Fachentscheidung keinen relationalen Einzelantwortnachweis verlangt.

**Import:** Attempt-, Import- und Dokumentversionsbezug validieren; Antworten niemals auswertend umdeuten.

**Dual-Read/Dual-Write:** Nur zeitlich begrenzter Vergleich, kein dauerhafter Parallelpfad.

**Tests:** Datenerhalt abgeschlossener Attempts, Importhash, Antwortreihenfolge, Audit, Kommentaranker und Rollenregeln.

**Rollback:** Training-DB-Backup.

**Abnahme:** Fachmatrix und Tests bestimmen explizit, welche Snapshots JSON bleiben.

**Alte JSON-Struktur entfernen:** Nur nach fachlicher Freigabe und Vergleich aller Attempts.

## J09: Desktop-Session und JSONL-Audit abloesen

**Ziel:** `current_user.json` als Security-Zustand beenden und autoritative Auditnachweise aus lokalen JSONL-Dateien herausfuehren.

**Voraussetzung:** Produktiver Usermanagement-Cutover inklusive UUID-Remapping sowie ein freigegebener Desktop-Sessiontransport.

**Betroffene Dateien:** Usermanagement `SessionStore`, CLI/PyQt-Login, Wiring, Architecture-Gates, Plattform-Auditexport.

**Neue Tabellen/Migrationen:** Keine neue Sessionvariante; bestehende PostgreSQL-Sessions nutzen. Fachmodul-Audittabellen werden in deren Paketen angelegt.

**Uebergangskompatibilitaet:** Desktop nutzt denselben opaken Sessionpfad wie Backend. Ein Use Case bleibt vollstaendig lokal oder vollstaendig backendgetragen; nie halb/halb.

**Import:** `current_user.json` wird nicht als Session importiert. Benutzer meldet sich neu an. JSONL kann als gekennzeichnetes Legacyarchiv erhalten bleiben.

**Dual-Read/Dual-Write:** Kein Dual-Auth. Umschaltung pro vollstaendig backendmigriertem Use Case.

**Tests:** Kein Backend-/migrierter Desktoppfad liest Datei; Logout/Expiry/Password-Change; Multi-Client-Isolation; Legacyarchivexport.

**Rollback:** Vorherige App plus DB-Backup; neue Sessions werden nicht in die Datei zurueckgeschrieben.

**Abnahme:** Architecture-Gates finden keinen produktiven Auth-Leser der Datei; autoritative Audits sind relational.

**Alte JSON-Struktur entfernen:** `current_user.json` nach vollstaendigem Desktop-Cutover. JSONL nur gemaess Retention, nie durch undokumentierte Loeschung.

## J10: Abschluss-Cleanup und dauerhafte Gates

**Ziel:** Abgeloeste Spalten, Writer, Reader und Settings-Keys entfernen, ohne Exporte oder Nachweise zu verlieren.

**Betroffene Dateien:** Nur durch J02 bis J09 nachweislich ungenutzte Strukturen; Migrationen, Packaging, Docs und Gates.

**Neue Tabellen/Migrationen:** Cleanup-Migrationen je Modul, niemals ein repo-weiter Big Bang.

**Kompatibilitaet:** Oeffentliche APIs bleiben oder werden in eigenem Deprecation-Paket geaendert. Keine stillen Adapterketten.

**Validierung:** Repository-weite Suche, DB-Fingerprint, Zeilen-/Hashvergleich, frische Installation, Upgrade vom unmittelbar vorherigen Stand, Backup/Restore, alle Modul-/Architektur-/Go-live-Gates.

**Rollback:** Vollstaendige Backups je betroffenem Modul.

**Abnahme:** Keine abgeloeste JSON-Struktur wird gelesen oder beschrieben; Allowlist im Architektur-Gate entspricht `JSON_STORAGE_INVENTORY.md`.

**Alte JSON-Struktur entfernen:** Genau in diesem paketweisen Cleanup, nie bereits waehrend des ersten Backfills.

## Empfohlene Freigabereihenfolge fuer den fruehen Nutzwert

1. J00/J01 als Guardrail.
2. Documents-Umbau mit J03, J04 und J05 in der Reihenfolge des Documents-Artefaktpakets.
3. J06, sobald der erste multiuserfaehige mutierende Documents-Use-Case produktionsnah wird.
4. J02 nur so weit vorziehen, wie Settings aktuell Multiuserbetrieb oder Governance blockieren; keine Fachpolicies nebenbei migrieren.
5. Incident, Training und Desktop-Cleanup als eigene Folgepakete.

Damit bleibt der Weg zum nutzbaren Documents-MVP kurz, ohne die spaetere Persistenzgrenze wieder aufzuweichen.
