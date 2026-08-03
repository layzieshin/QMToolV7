# Ziel-Persistenzmodell fuer QMToolV7

**Status:** Konkreter, noch nicht implementierter Zielvorschlag
**Stand:** 2026-08-03

## 1. Grundstruktur

Jedes Fachmodul bleibt Owner seiner Datenbank und seiner Tabellen. `qm_platform` stellt Migration Runner, Settings-Infrastruktur und Outbox-Dispatch bereit, besitzt aber keine fachlichen Documents-, Training- oder Incident-Daten.

Fachliche Module greifen nicht direkt auf Tabellen eines anderen Moduls zu. Moduluebergreifende IDs werden ueber die oeffentliche API des Owners validiert. Das ist besonders fuer User-UUIDs wichtig, solange Usermanagement in PostgreSQL und Documents in einer getrennten Datenbank liegen.

Alle neuen Tabellen verwenden stabile IDs, UTC-Zeitpunkte und explizite Statuswerte. Physisches Loeschen ist nur fuer einen nie eingereichten `DRAFT` zulaessig; sonst gilt Deaktivierung, Archivierung oder ein append-only Widerruf.

## 2. Documents-Kernmodell

Die folgende Struktur konkretisiert das Artefaktpaket v2. Namen duerfen bei der Implementierung an den bestehenden Repository-Stil angepasst werden; Entitaets- und Integritaetsgrenzen sind verbindlich.

### 2.1 Dokumentidentitaet und Version

#### `documents`

| Feld | Regel |
|---|---|
| `document_id` | PK, stabile UUID oder bestehende stabile ID |
| `document_code` | NOT NULL, UNIQUE, fachliche Kennung |
| `short_description` | NULL erlaubt, dokumentgebunden und auditierbar |
| `document_type_id` | FK auf `document_type_definitions` |
| `department_id` | externe validierte Organisations-ID oder spaeter FK zum Owner |
| `site_id` | externe validierte Standort-ID oder spaeter FK zum Owner |
| `regulatory_scope` | typisierter Wert; kein freier JSON-Key |
| `owner_user_id` | kanonische externe User-ID; NULL nur bei fachlich zulaessigem externem Dokument |
| `default_profile_definition_id` | FK auf `workflow_profile_definitions`, NULL nur mit dokumentierter Ableitung ueber Dokumentart |
| `manufacturer_or_publisher` | fuer externe Dokumente |
| `created_at`, `created_by_user_id`, `updated_at` | NOT NULL |

Indizes: `document_code` unique, `(document_type_id)`, `(owner_user_id)`, `(department_id)`, `(site_id)`.

#### `document_versions`

| Feld | Regel |
|---|---|
| `version_record_id` | PK |
| `document_id` | FK `documents`, ON DELETE RESTRICT |
| `visible_version` | positive sichtbare Versionsnummer |
| `record_revision` | positive interne Satzrevision; unterscheidet eine Korrekturfassung mit wiederverwendeter sichtbarer Nummer |
| `title` | NOT NULL, versionsgebunden |
| `status` | CHECK auf `DRAFT`, `IN_REVIEW`, `IN_APPROVAL`, `APPROVED`, `PUBLISHED`, `EXPIRED`, `ARCHIVED`, `ANNULLED` |
| `change_reason` | NOT NULL ab Nachfolgeversion |
| `approved_at`, `valid_from`, `valid_until`, `next_review_at` | fachlich konsistente Zeitfelder; `valid_until` wird bei Approval festgelegt, `valid_from = published_at`, Pruefintervall ab `approved_at` |
| `published_at`, `archived_at`, `annulled_at` | passend zum Status |
| `supersedes_version_record_id` | self-FK, ON DELETE RESTRICT |
| `corrects_annulled_version_record_id` | self-FK, nur fuer die ausdrueckliche Korrektur einer `ANNULLED`-Fassung mit gleicher sichtbarer Versionsnummer |
| `created_at`, `created_by_user_id`, `updated_at` | NOT NULL |

Constraints:

- UNIQUE `(document_id, visible_version, record_revision)` fuer die technische Identitaet.
- Partieller UNIQUE-Index auf `(document_id, visible_version)` fuer alle nicht `ANNULLED`-Saetze. Eine sichtbare Nummer darf nur durch eine explizit verknuepfte Korrekturfassung wiederverwendet werden, nachdem die vorherige Fassung `ANNULLED` wurde.
- Partieller UNIQUE-Index: hoechstens eine offene Nachfolgeversion je Dokument fuer `DRAFT`, `IN_REVIEW`, `IN_APPROVAL`, `APPROVED`.
- Partieller UNIQUE-Index: hoechstens eine aktuell gueltige `PUBLISHED`-Version. Falls SQLite den zeitabhaengigen Gueltigkeitsbegriff nicht im Index ausdruecken kann, erzwingt der Publish-Use-Case dies innerhalb `BEGIN IMMEDIATE` und ein statischer Index sichert hoechstens eine `PUBLISHED`-Zeile.
- Statuszeitpunkte werden per CHECK soweit moeglich und ansonsten im zentralen Invariant-Validator abgesichert.
- Ein nie eingereichter `DRAFT` darf verworfen und seine sichtbare Versionsnummer freigegeben werden. Ab der ersten Einreichung bleibt die Nummer reserviert; einzige Ausnahme ist die dokumentierte `ANNULLED`-Korrektur mit eigener `version_record_id`.

### 2.2 Dokumentarten und Workflowprofile

#### `document_type_definitions`

- `document_type_id` PK
- `code` NOT NULL UNIQUE
- `label` NOT NULL
- `default_profile_definition_id` FK, ON DELETE RESTRICT
- `profile_override_allowed` NOT NULL BOOLEAN
- `is_active` NOT NULL BOOLEAN
- `created_at`, `created_by_user_id`, `deactivated_at`, `deactivated_by_user_id`

Verwendete Dokumentarten werden nie geloescht.

#### `workflow_profile_definitions`

- `profile_definition_id` PK
- `profile_code` NOT NULL UNIQUE, stabiler Business-Key
- `label` NOT NULL
- `control_class` NOT NULL
- `is_active` NOT NULL
- `created_at`, `created_by_user_id`, `deactivated_at`, `deactivated_by_user_id`

#### `workflow_profile_versions`

- `profile_version_id` PK
- `profile_definition_id` FK, ON DELETE RESTRICT
- `version_no` positive Ganzzahl
- `effective_from` NOT NULL
- `created_at`, `created_by_user_id`, `change_reason` NOT NULL
- `definition_sha256` NOT NULL
- `source_kind` CHECK `SEED`, `MIGRATED`, `ADMIN`
- UNIQUE `(profile_definition_id, version_no)`
- UNIQUE `(profile_definition_id, definition_sha256)`

Profilversionen sind immutable. Eine Korrektur erzeugt `version_no + 1`.

#### `workflow_profile_transitions`

- `profile_transition_id` PK
- `profile_version_id` FK, ON DELETE RESTRICT
- `transition_no` NOT NULL
- `from_status`, `to_status` NOT NULL, jeweils CHECK auf feste Status
- `required_role` CHECK `EDITOR`, `REVIEWER`, `APPROVER`, `QMB`, `NONE`
- `decision_policy` CHECK `ONE_OF_POOL`, `ALL_ASSIGNED`, `NONE`
- `signature_required`, `four_eyes_required`, `revoke_if_changed` BOOLEAN NOT NULL
- `deadline_seconds` NULL oder positive Ganzzahl
- `is_enabled` NOT NULL
- UNIQUE `(profile_version_id, transition_no)`
- UNIQUE `(profile_version_id, from_status, to_status)`

Die Reihenfolge und Erreichbarkeit aller aktivierten Transitionen wird beim Anlegen einer Profilversion validiert.

### 2.3 Workflowinstanz, Snapshot und Runden

#### `workflow_instances`

- `workflow_instance_id` PK
- `version_record_id` FK `document_versions`, ON DELETE RESTRICT
- `profile_version_id` FK `workflow_profile_versions`, ON DELETE RESTRICT
- `profile_snapshot_schema_version` NOT NULL
- `profile_snapshot_json` NOT NULL
- `profile_snapshot_sha256` NOT NULL
- `instance_status` CHECK `ACTIVE`, `COMPLETED`, `ABORTED`
- `started_at`, `started_by_user_id` NOT NULL
- `completed_at`, `aborted_at`, `aborted_by_user_id`, `abort_reason`

Partieller UNIQUE-Index auf `version_record_id WHERE instance_status='ACTIVE'`.

Der Snapshot wird kanonisch aus der referenzierten Profilversion erzeugt und nach Insert nie geaendert. Der Hash muss bei jedem Lesen reproduzierbar sein.

#### `workflow_transition_instances`

- `transition_instance_id` PK
- `workflow_instance_id` FK, ON DELETE RESTRICT
- `profile_transition_id` FK, ON DELETE RESTRICT
- `submission_round_id` FK, NULL nur vor erster Einreichung
- `state` CHECK `PENDING`, `ACTIVE`, `COMPLETED`, `CANCELLED`, `REVOKED`
- `activated_at`, `due_at`, `completed_at`, `cancelled_at`
- UNIQUE fuer hoechstens eine aktive Transition je Workflowinstanz

#### `submission_rounds`

- `submission_round_id` PK
- `workflow_instance_id` FK, ON DELETE RESTRICT
- `round_no` positive Ganzzahl
- `submitted_at`, `submitted_by_user_id` NOT NULL
- `source_artifact_id` FK `document_artifacts`, ON DELETE RESTRICT
- `change_scope_sha256` NOT NULL
- `closed_at`, `result`
- UNIQUE `(workflow_instance_id, round_no)`

### 2.4 Zuweisungen und Entscheidungen

#### `workflow_role_assignments`

- `assignment_id` PK
- `workflow_instance_id` FK, ON DELETE RESTRICT
- `role_kind` CHECK `EDITOR`, `REVIEWER`, `APPROVER`
- `user_id` kanonische externe User-ID, NOT NULL
- `assigned_at`, `assigned_by_user_id` NOT NULL
- `revoked_at`, `revoked_by_user_id`, `revoke_reason`
- `replaces_assignment_id` self-FK, ON DELETE RESTRICT

Partieller UNIQUE-Index auf `(workflow_instance_id, role_kind, user_id)` fuer nicht widerrufene Zuweisungen. Indizes auf `(user_id, revoked_at)` und `(workflow_instance_id, role_kind)`.

#### `workflow_decisions`

- `decision_id` PK
- `transition_instance_id` FK, ON DELETE RESTRICT
- `submission_round_id` FK, ON DELETE RESTRICT
- `assignment_id` FK, ON DELETE RESTRICT
- `decision_kind` CHECK `ACCEPT`, `REJECT`
- `reason_code`, `reason_text`
- `decided_at`, `actor_user_id` NOT NULL
- `signature_evidence_id` externe stabile Signature-ID, wenn erforderlich
- `artifact_id` FK `document_artifacts`, ON DELETE RESTRICT
- `request_id`, `correlation_id`, `causation_id`
- UNIQUE `(transition_instance_id, submission_round_id, assignment_id)`

Die Zeile ist nach Insert immutable.

#### `workflow_decision_revocations`

- `revocation_id` PK
- `decision_id` FK, ON DELETE RESTRICT
- `revoked_at`, `revoked_by_user_id`, `reason` NOT NULL
- `caused_by_transition_instance_id` FK
- UNIQUE `(decision_id)`

Damit bleibt die tatsaechliche Entscheidung erhalten, obwohl ihre Wirkung fuer den laufenden Workflow widerrufen wurde.

### 2.5 Aenderungen, Artefakte und Kommentare

#### `document_change_entries`

- `change_entry_id` PK
- `version_record_id` FK, ON DELETE RESTRICT
- `chapter_ref`, `summary`, `reason` typisierte Felder
- `created_at`, `created_by_user_id`, `updated_at`, `updated_by_user_id`
- `superseded_by_change_entry_id` self-FK fuer Korrekturen

Diese Zeilen beschreiben den strukturierten Aenderungsumfang einer Version und spaeter einer Submission-Runde. Bestehende `custom_fields_json.change_requests` sind ein anderes, fachlich zurueckgestelltes Konzept und duerfen nicht in diese Tabelle umgedeutet werden.

#### `submission_round_change_entries`

- `submission_round_id` FK
- `change_entry_id` FK
- `included` BOOLEAN NOT NULL
- `exclusion_reason` nur bei `included=false`
- PK `(submission_round_id, change_entry_id)`

#### `document_artifacts`

Bestehende Kernfelder (`artifact_id`, Dokument-/Versionsbezug, Typ, Storage-Key, Dateiname, MIME, SHA-256, Groesse, Current-Flag) bleiben relational. Hinzu kommen nullable FKs auf `workflow_instance_id`, `submission_round_id` und `decision_id`. `metadata_json` bleibt fuer technische Leaf-Metadaten, erhaelt aber `metadata_schema_version` und wird nach Import nicht in-place geaendert.

#### `document_workflow_comments`

Bestehende Word-/PDF-Funktionalitaet bleibt. Hinzu kommen:

- FK `version_record_id`
- nullable FK `workflow_instance_id`
- nullable FK `submission_round_id`
- nullable FK `artifact_id`
- `anchor_schema_version` fuer `anchor_json`

UNIQUE fuer Word-Sync bleibt auf Dokumentversion, Kontext und `source_comment_key`. Kommentartext/Herkunft werden nie durch Statuswechsel ueberschrieben.

#### `document_comment_status_history`

- `history_id` PK
- `comment_id` FK, ON DELETE RESTRICT
- `from_status`, `to_status`
- `changed_at`, `changed_by_user_id`, `note`

Status `ACTIVE`, `RESOLVED`, `INACTIVE` bleibt im Kommentar als aktueller Read-Wert; die Historie ist append-only.

### 2.6 Read Tracking

`document_pdf_read_sessions`, `document_pdf_read_page_progress` und `document_read_receipts` bleiben relational. Sie erhalten echte FKs auf `version_record_id` und `artifact_id`, soweit sie innerhalb derselben DB liegen. Eine bestaetigte Read-Receipt ist append-only; eine Wiederholung wird ueber den bestehenden fachlichen Unique-Key idempotent.

## 3. Persistente Domain-Event-Outbox

Jede Fach-DB erhaelt dieselbe logische Struktur `outbox_events`; die Tabelle liegt physisch beim Aggregate-Owner.

| Feld | Regel |
|---|---|
| `event_id` | PK, vom Use Case erzeugt |
| `event_name` | NOT NULL |
| `schema_version` | positive Ganzzahl |
| `occurred_at_utc` | NOT NULL |
| `actor_user_id` | NULL nur bei explizitem System-/Anonymous-Event |
| `actor_kind` | CHECK `USER`, `SYSTEM`, `ANONYMOUS` |
| `module_id` | NOT NULL, muss dem DB-Owner entsprechen |
| `aggregate_type`, `aggregate_id` | NOT NULL |
| `document_id`, `version_record_id`, `workflow_instance_id`, `submission_round_id` | fuer Documents typisierte Bezugsspalten/FKs soweit lokal |
| `correlation_id` | NOT NULL |
| `causation_id` | NULL nur am Kettenanfang |
| `idempotency_key` | NOT NULL UNIQUE pro Modul/Eventvertrag |
| `payload_schema_version` | NOT NULL |
| `payload_json` | NOT NULL, kanonisch validiert |
| `payload_sha256` | NOT NULL |
| `created_at` | NOT NULL, identisch mit Transaktionspersistenz |
| `published_at` | NULL bis erste erfolgreiche Uebergabe an EventBus/Broker |
| `delivery_status` | CHECK `PENDING`, `PUBLISHED`, `RETRY`, `DEAD` |
| `attempt_count`, `next_attempt_at`, `last_error_code` | technische Zustellung; keine Secrets/Stacktraces |

Indizes: `(delivery_status, next_attempt_at, created_at)`, `(aggregate_type, aggregate_id, occurred_at_utc)`, `correlation_id`, sowie UNIQUE `event_id` und `idempotency_key`.

Transaktionsregel: Der Fachzustand, der autoritative Auditnachweis und der zugehoerige Outbox-Datensatz werden gemeinsam committed. Das Markieren als `PUBLISHED` geschieht in einer spaeteren kurzen Transaktion. Consumer muessen `event_id` idempotent behandeln.

## 4. Autoritatives Audit

Documents erhaelt `document_audit_events` nach dem in Usermanagement bewaehrten append-only Muster:

- `audit_id` PK
- `action`, `result`, `reason_code`
- `occurred_at`, `request_id`, `correlation_id`, `causation_id`
- `actor_kind`, `actor_user_id`, optional `system_actor`
- `effective_roles_snapshot_json` als unveraenderlicher, kanonisch gehashter Rollen-Snapshot des Actors
- `document_id`, `version_record_id`, `workflow_instance_id`, `submission_round_id`, `decision_id`
- `changed_fields`, `old_values_json`, `new_values_json` fuer den nachweisbaren Alt-/Neubezug
- `artifact_sha256` beziehungsweise `file_sha256`, wenn eine Datei oder ein Artefakt Gegenstand der Handlung ist
- `details_schema_version`, `details_json`, `details_sha256`

Runtime erhaelt INSERT, aber kein UPDATE/DELETE. Fachlich wichtige IDs liegen in Spalten, nicht nur in `details_json`. JSONL ist spaeter ein Export dieser Daten, nicht deren Quelle.

## 5. Settings-Zielmodell

### `platform_settings`

- PK `(scope_kind, scope_id, module_id, setting_key)`
- `scope_kind` CHECK `SYSTEM`, `MODULE`, `USER`
- `scope_id`: `global`, Modul-ID oder kanonische User-ID
- `value_type`, `value_json`, `schema_version`
- `revision` positive Ganzzahl
- `updated_at`, `updated_by_user_id`

Nur schema-validierte technische/flexible Werte duerfen hier liegen. UNIQUE-Key verhindert doppelte Wahrheiten.

### `platform_setting_revisions`

- `revision_id` PK
- Bezug auf den logischen Settings-Key
- `revision_no`, `old_value_json`, `new_value_json`
- `changed_at`, `changed_by_user_id`, `reason`
- UNIQUE pro Key und `revision_no`

Historienzeilen sind immutable. Governance-kritische Keys verlangen Actor und Begruendung.

Fachliche Policies werden nicht in diese Tabellen gepresst:

- Documents-Dokumentart/Profilbindung liegt in `document_type_definitions`.
- Documents-Berechtigungen liegen in Modulrollen/Permissions.
- Incident-Kategorien, Fristen und CAPA-Regeln erhalten im Incident-Folgepaket typisierte, versionierte Tabellen.
- Usermanagement-Passwortpolicy bleibt bis zu einem eigenen Security-Policy-Paket im bestehenden validierten Vertrag; eine Verschiebung erfolgt nicht nebenbei.

## 6. Weitere bestehende JSON-Spalten

| Modul/Inhalt | Ziel |
|---|---|
| Incident Labels | `labels` plus `incident_labels` Zuordnung |
| Incident Timeline Details | versioniertes, unveraenderliches `details_json` |
| Incident Artefaktmetadaten | `metadata_json` fuer technische Leaf-Daten |
| Training Quiz-Import | verschluesseltes, gehashtes Austauschblob plus relationales Binding |
| Training Question Selection/Presentation | vorlaeufig versionierter JSON-Snapshot |
| Training Answers | Entscheidung im Fachkonsolidierungspaket |
| Training Audit Details | JSON-Payload mit relationalen Kernbezuegen |
| Documents/Training Kommentaranker | gemeinsamer schema-versionierter JSON-Anchor-Vertrag |

## 7. Loesch-, Deaktivierungs- und Versionsregeln

- Verwendete Profildefinitionen, Profilversionen, Assignments, Entscheidungen, Audit- und Eventzeilen: `ON DELETE RESTRICT`, keine physische Loeschung.
- Stammdaten wie Profile und Dokumentarten: Deaktivierung mit Actor/Zeitpunkt.
- Workflowentscheidungen und deren Widerrufe: append-only.
- Technische Event-Zustellung darf Status/Attempt-Felder aktualisieren, niemals Envelope oder Payload.
- Artefaktbytes werden ueber Storage-Key und SHA-256 gebunden; fachliche Metadaten bleiben nachweissicher erhalten.
- Snapshot-JSON wird kanonisch serialisiert, gehasht und nach Insert nicht mutiert.
- Jede Tabellen-/Constraint-Aenderung erfolgt als nummerierte Vorwaertsmigration mit frischer Installation, Upgrade-Fixture und Datenerhalttest.

## 8. Zwingende Transaktionsgrenzen

In genau einer DB-Transaktion des Owners laufen mindestens:

1. Planumwandlung: Plan validieren, Dokument und Version 1/DRAFT anlegen, Audit und Outbox schreiben, Plan entfernen.
2. Workflowstart: Instanz, Profilsnapshot, Transitionen und Assignments anlegen, Audit und Outbox schreiben.
3. Entscheidung: Actor/Assignment pruefen, Decision/Signaturnachweis binden, Status/naechste Aufgabe aktualisieren, Audit und Outbox schreiben.
4. Ablehnung: Decision speichern, Runde schliessen, Status auf DRAFT setzen, Folgeaufgaben aktualisieren, Audit und Outbox schreiben.
5. Publikation: neue Version PUBLISHED setzen, bisherige PUBLISHED-Version archivieren, Recall markieren, Audit und Outbox schreiben.
6. Rollen-/Regelaenderung: betroffene Entscheidungen per Revocation unwirksam machen, Assignments ersetzen, Stage zuruecksetzen, Audit und Outbox schreiben.
7. Annullierung/Archivierung/Verlaengerung: Zustand, Begruendung, Actor, Nachweis und Event atomar speichern.

Cross-Modul-Folgen wie Training- oder Registry-Aktualisierung erfolgen ueber idempotente Events, nicht ueber eine vorgetaeuschte Transaktion ueber mehrere Datenbanken.
