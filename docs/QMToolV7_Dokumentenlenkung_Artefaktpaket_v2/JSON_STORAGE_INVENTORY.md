# JSON-Speicherinventar QMToolV7

**Stand:** 2026-08-03
**Scope:** Aktive Produktionspfade, persistierte Laufzeitdaten, Datenbankschemas, Bootstrap-/Betriebsartefakte und fachliche Austauschformate. Testfixtures und reine JSON-Ausgabe auf `stdout` sind nur im Abschnitt "Abgrenzung" erfasst.

## Bewertungsgrundlage

Die Inventur beruecksichtigt `*.json`, JSONL-Inhalte, `json.load(s)`, `json.dump(s)`, JSON-Schreibvorgaenge, JSON-Felder in SQLite, Settings, Events, Snapshots sowie Import und Export. Die Zielentscheidungen folgen dem Documents-Artefaktpaket v2 und den kanonischen Architektur- und Migrationsregeln.

Die Arbeitsmappe `QMToolV7_Fachlogik_Dokumentenlenkung_Ausgefüllt_v2.xlsx` wurde am 2026-08-03 auf der isolierten Open-Terminal-Instanz mit `openpyxl 3.1.5` strukturell und inhaltlich ausgewertet. Ihr SHA-256 `3049a115f9f3f917379ea58b74b34a2be3389560d230eb07f4914d6f096761bd` stimmt mit `QMToolV7_Dokumentenlenkung_MANIFEST_v2.txt` ueberein. Der Abgleich umfasst alle 16 Tabellenblaetter, insbesondere Use Cases, offene Punkte, Status-/Rollenmodell, Entscheidungsprotokoll, Uebergangsmatrix, Berechtigungen, Umbauplan, Events/API und Kommentare. Damit besteht keine verbleibende XLSX-Werkzeug-Einschraenkung.

Kategorien:

- **A** Bootstrap- oder Infrastrukturkonfiguration
- **B** fachliche Stammdaten
- **C** fachlicher Zustand oder Beziehung
- **D** unveraenderlicher historischer Snapshot
- **E** Domain-Event-Payload
- **F** technische Metadaten
- **G** Import-/Export- oder Austauschformat
- **H** Cache oder temporaere Daten
- **I** fachliche Entscheidung erforderlich

## Fundstellen- und Entscheidungs-Matrix

| ID | Fundstelle | Modul | Information | Leser | Schreiber | Kat. | Fachlich/technisch | Veraenderlichkeit | Audit | Relationale Abfrage | Beziehungen | Risiko heute | Zielablage | Erforderliche Migration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| J01 | `license/license.json` | Plattform/Lizenz | Signierter Lizenzvertrag, Machine-ID, Module, Ablauf | `LicenseService`, Bootstrap, Doctor | Lizenzimport/-issuer; Dev-Bootstrap | G | technisch/rechtlich | Austauschdatei wird ersetzt, Inhalt signiert | ja | nein | Module, Installation | Repo-Datei kann installationsspezifisch wirken; Schreibpfade in CLI und Backend | **JSON-Datei beibehalten** als signiertes Austauschformat; Pfad/Quelle per Bootstrap | Keine DB-Migration. Import atomar machen und produktive Lizenz nicht im Source-Tree erzeugen. |
| J02 | `qm_platform/persistence/migration_manifest.json` | Plattform/Persistenz | Nummer, Name, Pfad und SHA-256 aller SQLite-Migrationen | Migration Runner, CI-Gates | Entwicklung im selben PR wie Migration | A | technisch | append-only, versioniert | ja | nein | Modulmigrationen | Manuelle Abweichung blockiert Migration; genau das ist beabsichtigt | **JSON-Datei beibehalten** als source-kontrollierter Manifestvertrag | Keine Datenmigration; bestehende Checksum-/Kontiguitaets-Gates beibehalten. |
| J03 | `modules/documents/workflow_profiles.json` | Documents | Workflowprofile, Phasen, Rollenanforderungen, Signatur- und Vier-Augen-Regeln | `WorkflowProfileStoreJSON`, Wiring, GUI, Gates | PyQt-Profilverwaltung, manuelle Aenderung | B | fachlich | mutable | ja | ja | Profilversion, Dokumentart, Workflowinstanz | Keine Historie, Dateikonflikte, veraltete Statusnamen, kein FK, Multiuser-ungeeignet | **relationale DB-Tabellen** fuer Definition, Version und Transition; JSON nur noch Seed/Export | Versionierte Tabellen erstellen; Datei mit festem Hash importieren; semantisch vergleichen; Runtime-Schreiber entfernen; Datei spaeter nur als Seed/Export behalten. |
| J04 | `storage/platform/settings.json`: DB-/Artefaktpfade, Runtime-Startparameter | Plattform und Module | Pfade zu SQLite, Artefakten, Keys und Profilquelle | CLI-/Backend-Bootstrap, Module | `SettingsService`, CLI/PyQt | A | technisch | mutable | bei sicherheitskritischen Keys ja | nein | App-Home, Module | Gesamte Datei wird ueberschrieben; konkurrierende Prozesse koennen Updates verlieren; Bootstrap und Fachpolicy vermischt | **Umgebungsvariable oder minimale Bootstrap-Angabe**; Standardpfade aus App-Home ableiten | Explizite Bootstrap-Schluessel festlegen; Werte in Env/Deployment uebernehmen; nicht mehr als allgemeine Settings behandeln. |
| J05 | `storage/platform/settings.json`: allgemeine Modul-/Systemsettings | Plattform und Module | Signaturmodus, Quizparameter, Erinnerungsfrist und vergleichbare flexible Werte | `SettingsService`, Modul-Wiring, Settings-UI | CLI/PyQt ueber `SettingsService` | A | technisch/operativ | mutable | teilweise | selten | Modul, optional Benutzer | Keine Revision, keine atomare Einzelwertaenderung, keine Nutzertrennung | **JSON-Spalte innerhalb einer Settings-DB** je typisiertem Key, mit Revision/Audit fuer kritische Werte | `platform_settings` und Historie anlegen; validiert importieren; danach atomare DB-Writes; JSON-Datei erst nach Vergleich entfernen. |
| J06 | `storage/platform/settings.json`: fachliche Policies | Documents, Incidents, Usermanagement | Dokumentart-Profilregeln, Erstellberechtigungen, Incident-Fristen/CAPA-Regeln, Passwortpolicy | Fachservices/Wiring | Settings-UI/CLI | B | fachlich | mutable | ja | ja | Rollen, Dokumentarten, Kategorien, Prozesse | Policies umgehen relationale Integritaet und fachliche Versionierung | **relationale DB-Tabellen** im fachlichen Owner; kein generischer Settings-Blob | Pro Policy eigenes Paket: typisierte Tabellen, Versions-/Auditfelder, Import, Vergleich, anschliessend Settings-Key sperren/entfernen. |
| J07 | `storage/platform/session/current_user.json` | Usermanagement/Desktop | Aktuell angemeldeter Desktop-Benutzer | Desktop/CLI `SessionStore` | Desktop-Login/-Logout | H | technisch mit Security-Bezug | mutable, kurzlebig | nein | nein | Benutzer | Lokale Datei darf keine Backend-Wahrheit sein; Klartextidentitaet ist faelschbar | **vollstaendig entfernen**, sobald Desktop den opaken Sessionpfad nutzt; bis dahin lokale Legacy-Datei | Separates Desktop-Session-Folgepaket. Backend-Gate beibehalten; kein Cross-Client-Sharing; Datei beim Logout entfernen. |
| J08 | `storage/platform/database-migration-journal.json` | Plattform/Persistenz | Externes Journal eines laufenden/abgebrochenen DB-Upgrades | `DatabaseEvolutionManager` vor DB-Start | `DatabaseEvolutionManager` atomar ueber Tempdatei | H | technisch | kurzlebig | ja | nein | Backup-Satz und DB-Beitraege | Muss vor Oeffnen der Ziel-DB lesbar sein; Manipulation blockiert Betrieb | **JSON-Datei beibehalten** als minimale externe Crash-Barriere | Schema-Version und Journal-ID verpflichtend halten; keine Verlagerung in die zu migrierende DB. |
| J09 | `storage/platform/backups/databases/<backup-id>/manifest.json` | Plattform/Persistenz | Backup-Satz, Quelldateien, Hashes und Versionen | Backup-Liste/Restore | `DatabaseEvolutionManager` | D | technisch | nach Erstellung unveraenderlich | ja | nein | Backup-Dateien, Datenbanken | Integritaet haengt an Hashpruefung und unveraendertem Manifest | **JSON-Datei beibehalten** neben dem Backup-Satz | Manifestversion/Checksumme weiter pruefen; Restore erzeugt vorher Sicherheitsbackup. |
| J10 | `storage/platform/backups/logs/_state.json` | Plattform/Logging | Letzter erfolgreicher Log-Backup-Zeitpunkt | `LogBackupService` | `LogBackupService` | H | technisch | mutable | nein | nein | Logarchive | Parsefehler werden als "kein Backup" behandelt; nicht atomar geschrieben | **JSON-Datei beibehalten**, aber als nichtfachlichen Cursor behandeln | Spaeter atomarer Write und explizite Diagnose bei Defekt; keine Fach-DB erforderlich. |
| J11 | `storage/platform/logs/platform.log` (JSONL-Inhalt) und ZIP-Archive | Plattform/Logging | Diagnoseereignisse mit Kontext | LogQuery/Support | `LoggerService` append-only | F | technisch | append-only, rotierend | nein | begrenzt | Modul, Correlation-ID | Kein zentrales Schema; Dateisperren/Rotation nur lokal | **JSON-Datei beibehalten** als technisches Log/Exportformat | Keine fachliche DB-Migration. Struktur versionieren und Secrets weiterhin ausschliessen. |
| J12 | `storage/platform/logs/audit.log` (JSONL-Inhalt) und ZIP-Archive | Plattform/Audit | Generische Auditzeilen | Support, Backup | `AuditLogger` append-only | D | fachlicher Nachweis in technischer Datei | append-only, wird archiviert/trunkiert | ja | ja | Actor, Ziel, Fachobjekt | Keine FK, keine gemeinsame Transaktion, schwache Kopplung zu Events, lokale Datei | **relationale Audit-Datensaetze** beim jeweiligen fachlichen Owner; JSONL nur Export | Je Modul autoritative Audit-Tabelle/Use-Case-Transaktion einfuehren; JSONL erst nach Nachweisexport und Consumer-Suche als Wahrheit abloesen. |
| J13 | `scripts/registry_recovery_drill.py` Evidence-JSON | Registry/Betrieb | Recovery-Drill-Ergebnis und Hashnachweis | Operator/CI | Wartungsskript | G | technisch | unveraenderliches Ergebnis | ja | nein | Drill-Lauf/Backup | Manuell ersetzbar, daher nur Evidenz mit nachvollziehbarer Ausfuehrung | **JSON-Datei beibehalten** als Betriebsnachweis | Run-ID, Toolversion und Eingabehash erhalten; keine operative Zustandsquelle. |
| J14 | `scripts/database_migration_gate.py`, `postgres_migration_gate.py`, `golive_gate.py` Output-JSON | Plattform/CI | Gate-Checks und Ergebnis | CI/Operator | jeweiliges Gate | G | technisch | pro Lauf unveraenderlich | ja | nein | Commit/Basis-Ref | Handgeschriebene Datei darf keinen Zustand freischalten | **JSON-Datei beibehalten** als Ausgabe, nie als Eingabe-Wahrheit | Keine DB-Migration; Ausfuehrung/Exit-Code bleibt Autoritaet. |
| J15 | `build/.../ap028-m8-cutover-prep-*.json` | Usermanagement/Betrieb | Cutover-Inventar und Blocker | Operator | `prepare_postgres_cutover` | G | technisch | pro Lauf unveraenderlich | ja | nein | SQLite-Quelle, PG-Identitaet, Quermodulreferenzen | Nur Prep; darf keinen Cutover ausloesen | **JSON-Datei beibehalten** als nichtautorisierende Evidenz | Keine Migration; Status bleibt `invalid_source`, `blocked` oder `ready_for_remapping`. |
| J16 | `build/.../pg-backup-restore-drill-*.json` | Usermanagement/Betrieb | Dump-/Restore-Nachweis, Hashes, Fingerprints | M8 Prep/Operator | interner Drill | D | technisch | pro Lauf unveraenderlich | ja | nein | konkrete Quell-/Ziel-DB | Manipulation oder falsche DB-Bindung koennte false-green erzeugen; M8 haertet dies | **JSON-Datei beibehalten** als gebundener Nachweis | Keine DB-Migration; Identitaetsdigest, Tool-Exitcodes und Fingerprints weiterhin live verifizieren. |
| J17 | Documents-Aenderungsanforderungs-Export (`*.json`) | Documents | Exportierte Change-Request-Zeilen | Benutzer/externe Werkzeuge | CLI/PyQt ueber Documents-API | G | fachliches Austauschformat | Export unveraenderlich | Export selbst nein | nein | Dokument/Version | Export kann veralten und ist keine Wahrheit; Change Requests sind fachlich nicht mit den neuen Aenderungseintraegen identisch | **JSON-Datei beibehalten** als Export | Bestehenden Exportvertrag erhalten. Eine neue relationale Quelle darf erst ein separates Change-Request-Fachpaket festlegen; keine Umdeutung zu `document_change_entries`. |
| J18 | Training Quiz-JSON und verschluesselter `.quiz`-Blob | Training | Extern importierte Quizdefinition inklusive Fragen/Antworten | `QuizImportService`, Quiz-Ausfuehrung | Admin-Import ueber API | G | fachliches Austauschformat | Importblob unveraenderlich | ja | innerhalb des Blobs nein | Dokument/Version/Import | Fachvertrag noch nicht konsolidiert; Inhalt nur blobweise validierbar | **JSON-Datei beibehalten** als versioniertes, gehashtes Importartefakt | Keine Normalisierung vor "Training fachliche Konsolidierung"; Binding/Hash bleiben relational. |
| J19 | `EventEnvelope.payload` aller Module, derzeit nur In-Memory | Plattform/alle Module | Versionierte Domain-Event-Payload | synchrone Subscriber | Fach-Use-Cases | E | fachlich | nach Erzeugung unveraenderlich | ja, je Ereignis | teils | Aggregate, Actor, Correlation/Causation | Event geht ohne Subscriber/bei Prozessende verloren; Erfolg und Publish nicht atomar | **persistierter Event-Datensatz mit `payload_json`** im DB-Owner, danach EventBus-Dispatch | Gemeinsamen Outbox-Vertrag schaffen; pro Modul in derselben Fachtransaktion schreiben; EventBus aus persisted Event bedienen. |
| J20 | `document_headers.distribution_roles_json` | Documents | Rollenverteiler | Documents-Service/Repository | Metadaten-Use-Case | C | fachlich | mutable; Snapshot bei Approval | ja | ja | Rollen/Benutzergruppen | Freitextliste, keine FK, Sollmodell weist Sichtbarkeit Training zu | **vollstaendig entfernen** aus aktivem Documents-Modell; historische Snapshotdaten bewahren | Consumer-Suche; Altdatenreport; keine neue Documents-Rollentabelle erfinden; historische Werte in gekennzeichnetem Legacy-Snapshot erhalten. |
| J21 | `document_headers.distribution_sites_json` | Documents | Zielstandorte | Documents-Service/Repository | Metadaten-Use-Case | C | fachlich | mutable; Snapshot bei Approval | ja | ja | Standortstamm | Freitext, keine FK; Semantik kollidiert mit Sollmodell ohne Documents-Zielgruppen | **vollstaendig entfernen** als Verteiler; `document.site` bleibt separates Dokumentmetadatum | Consumer-Suche und Altdatenreport; historischen Snapshot erhalten, aktive Verteilernutzung beenden. |
| J22 | `document_headers.distribution_departments_json` | Documents | Zielabteilungen | Documents-Service/Repository | Metadaten-Use-Case | C | fachlich | mutable; Snapshot bei Approval | ja | ja | Fachbereich/Organisation | Freitext, keine FK; mit Dokument-Fachbereich vermischt | **vollstaendig entfernen** als Verteiler; Dokument-Fachbereich typisiert/relational fuehren | Consumer-Suche, Datenklassifikation, historischer Snapshot; kein stilles Mapping. |
| J23 | `document_versions.workflow_profile_json` | Documents | Beim Start kopierte Profilregeln | Repository/Workflow | Workflowstart/State-Save | D | fachlich | soll unveraenderlich sein | ja | nein | Profilversion, Workflowinstanz | Liegt am Versionszustand statt an der Instanz; kein Hash/FK; Save kann ueberschreiben | **JSON-Spalte innerhalb der DB** als unveraenderlicher `profile_snapshot_json` an `workflow_instances`, plus FK zur Profilversion | Beim Workflow-Import Snapshot kanonisieren/hashen; Instanz zuordnen; alte Spalte nach Vergleich entfernen. |
| J24 | `document_versions.editors_json` | Documents | Editorpool | Workflow/Readmodel | Zuweisungs-Use-Case | C | fachlich | mutable nach Regeln | ja | ja | User, Instanz, Stufe | Keine FK, Historie oder eindeutige aktive Zuweisung | **relationale Zuordnungstabelle** `workflow_role_assignments` | Pro Instanz/Rolle/User importieren; unbekannte User blockieren; kompatibles Read-Model ableiten. |
| J25 | `document_versions.reviewers_json` | Documents | Reviewerpool | Workflow/Readmodel | Zuweisungs-Use-Case | C | fachlich | mutable nach Regeln | ja | ja | User, Instanz, Stufe | Wie J24; Vier-Augen-Pruefung nur im Code | **relationale Zuordnungstabelle** `workflow_role_assignments` | Wie J24, Rolle `REVIEWER`; aktive Eindeutigkeit und Historie erzwingen. |
| J26 | `document_versions.approvers_json` | Documents | Approverpool | Workflow/Readmodel | Zuweisungs-Use-Case | C | fachlich | mutable nach Regeln | ja | ja | User, Instanz, Stufe | Wie J24 | **relationale Zuordnungstabelle** `workflow_role_assignments` | Wie J24, Rolle `APPROVER`. |
| J27 | `document_versions.reviewed_by_json` | Documents | Bereits abgegebene Reviewzustimmungen | Workflow/Readmodel | Review-Entscheidung | C | fachlich | historischer Nachweis, heute als Liste aktualisiert | ja | ja | User, Runde, Entscheidung, Signatur | Identitaet ohne Entscheidung, Zeit, Grund, Runde oder Widerruf | **relationale DB-Tabelle** `workflow_decisions` | Nur eindeutig ableitbare Legacyentscheidungen importieren; unklare Datensaetze blockieren/manuell klassifizieren. |
| J28 | `document_versions.approved_by_json` | Documents | Bereits abgegebene Approvalzustimmungen | Workflow/Readmodel | Approval-Entscheidung | C | fachlich | historischer Nachweis, heute als Liste aktualisiert | ja | ja | User, Runde, Entscheidung, Signatur | Wie J27 | **relationale DB-Tabelle** `workflow_decisions` | Wie J27, Stage `APPROVAL`. |
| J29 | `document_versions.custom_fields_json.change_requests` | Documents | Bestehende Aenderungsanforderungen | Documents-Service, CLI/GUI | Change-Request-Use-Cases | C | fachlich, im Kernumbau zurueckgestellt | mutable mit Historie | ja | ja | Dokumentversion, Actor | Unstrukturierte Liste in Sammelblob; konkurrierende Updates und schwache IDs; fachlich nicht identisch mit `document_change_entries` | **noch offen** (siehe OQ-02): bis zum separaten Change-Request-Fachpaket unveraendert erhalten | Key-/Typ-/Zaehlinventur und bytegenauen Erhalt pruefen. Nicht in `document_change_entries` importieren und keinen neuen Lifecycle erfinden. |
| J30 | `document_versions.custom_fields_json.distribution_snapshot` | Documents | Eingefrorener historischer Verteilerstand | Workflow/Readmodel | Approval-Use-Case | D | fachlich | nach Erzeugung unveraenderlich | ja | nein | Dokumentversion/Workflowrunde | In mutablem Sammelblob; aktive Verteilersemantik ist im Soll entfallen | **JSON-Spalte innerhalb der DB** als klar versionierter Legacy-/Rundensnapshot, nur fuer Historie | Snapshot aus `custom_fields_json` extrahieren, hashbinden und danach nicht mehr mutieren. |
| J31 | `document_versions.custom_fields_json` sonstige Keys | Documents | Erweiterbare Metadaten, z. B. `topic` | API/CLI/GUI/Presenter | Metadaten-Use-Case | I | fachlich unbekannt | mutable | je Key | je Key | potenziell Registry/Fachobjekte | Sammelblob mischt Erweiterung und Kernfachlogik | **noch offen** (siehe OQ-02): bekannte Fachkeys relational; nur nicht referenzierte Leaf-Metadaten als JSON-Spalte | Vor Migration reale Key-/Typ-/Nutzungsinventur; reservierte Keys verbieten; Schema-Version fuer verbleibenden Blob. |
| J32 | `document_artifacts.metadata_json` | Documents | Flexible technische Artefaktmetadaten | Artifact-Repository/API | Artifact-Import | F | technisch | nach Import grundsaetzlich unveraenderlich | ja | selten | Artefakt | Kein JSON-Schema; fachliche Werte koennten hineindriften | **JSON-Spalte innerhalb der DB** | Bekannte Kernwerte als Spalten/FKs; Rest kanonisch, schema-versioniert und nach Import immutable. |
| J33 | `document_workflow_comments.anchor_json` | Documents | PDF-Auswahl-/Positionsanker | Comment-Service, PDF-Viewer | PDF-Kommentarerstellung | F | technisch | nach Kommentarerstellung unveraenderlich | ja | nein | Seite/Artefakt/Kommentar | Kein expliziter Schema-Versionswert; Artefaktbezug optional | **JSON-Spalte innerhalb der DB** | Word/PDF-Funktion erhalten; `anchor_schema_version` und verpflichtenden Artefakt-/Rundenbezug fuer neue PDF-Anker ergaenzen. |
| J34 | `incidents.labels_json` | Incident Management | Labels eines Vorfalls | Incident-Repository, Filter/Reports | Incident-Use-Cases | C | fachlich | mutable | ja | ja | Incident, Labelstamm | Keine FK, erschwerte Filter/Unique-Regeln | **relationale Zuordnungstabelle** `incident_labels` | Labels deduplizieren; `labels` + `incident_labels` backfillen; Listenvertrag aus Join ableiten. |
| J35 | `incident_timeline.details_json` | Incident Management | Ereignisspezifische Timeline-Details | Timeline/Report | Fach-Use-Cases append-only | D | fachlich | unveraenderlich | ja | selten | Incident/Timeline-Eintrag | Flexible Form ohne Schema-Version | **JSON-Spalte innerhalb der DB** | Eventtyp-spezifische Schema-Version/Validatoren; haeufig referenzierte IDs als Spalten. |
| J36 | `incident_artifacts.metadata_json` | Incident Management | Flexible Artefaktmetadaten | Artifact-Repository/Reports | Artifact-Use-Case | F | technisch | nach Import unveraenderlich | ja | selten | Incident/Artefakt | Wie J32 | **JSON-Spalte innerhalb der DB** | Kernwerte relational belassen; Rest schema-versioniert und immutable. |
| J37 | `training_quiz_attempts.selected_question_ids_json` | Training | Eingefrorene Auswahl der Fragen | Quiz-Ausfuehrung/History | Quizstart | D | fachlich | unveraenderlich | ja | nein | Quizimport/Attempt | IDs referenzieren Inhalt im verschluesselten Importblob, nicht relationale Fragen | **JSON-Spalte innerhalb der DB** vorlaeufig beibehalten | Erst im Training-Konsolidierungspaket entscheiden; Hash/Import-ID an Attempt binden. |
| J38 | `training_quiz_attempts.presented_questions_json` | Training | Reihenfolge/Antwortdarstellung des gestarteten Quiz | Quiz-Ausfuehrung | Quizstart | D | fachlich | unveraenderlich | ja | nein | Attempt/Quizimport | Vertrag lebt als String im Contract; kein Schema-Versionsfeld | **JSON-Spalte innerhalb der DB** vorlaeufig beibehalten | Schema-Version und Importhash speichern; fachliche Normalisierung nicht vor Training-Konsolidierung. |
| J39 | `training_quiz_attempts.answers_json` | Training | Abgegebene Antworten | Quiz-Auswertung/History | Quizabschluss | I | fachlich | nach Abschluss unveraenderlich | ja | moeglicherweise | Attempt/Fragen | Fachlicher Abfrage-/Nachweisbedarf ist noch nicht konsolidiert | **noch offen** (siehe OQ-07) | Im Training-Konsolidierungspaket entscheiden: Antwortzeilen relational oder versionierter Snapshot; bis dahin nicht migrieren. |
| J40 | `training_comments.anchor_json` | Training | PDF-Positionsanker eines Trainingskommentars | Training-Kommentarservice/PDF-UI | Kommentarerstellung | F | technisch | nach Erstellung unveraenderlich | ja | nein | Dokumentversion/Kommentar | Gleiche Schemafrage wie Documents; kein DB-FK zum Documents-Artefakt | **JSON-Spalte innerhalb der DB** | Gemeinsamen Anchor-Vertrag nutzen, Schema-Version und stabile Dokument-/Artefaktidentitaet ergaenzen. |
| J41 | `training_audit_log.details_json` | Training | Aktionsspezifische Auditdetails | Reports/Admin | Training-Services append-only | D | fachlicher Nachweis | unveraenderlich | ja | selten | Actor/Fachobjekt | Eventtyp nicht schema-versioniert; relevante IDs nur im Blob moeglich | **JSON-Spalte innerhalb der DB** in autoritativem Auditdatensatz | Kernbezugsspalten ergaenzen; Payload pro Action versionieren; Training-Fachpaket abwarten. |
| J42 | Settings-/Workflowprofil-Editoren und CLI-Argumente mit JSON-Text | Interfaces | Transportdarstellung fuer Settings, Custom Fields und Antworten | CLI/PyQt | Benutzer, Adapter | G | Austauschformat | nicht selbst persistent | nein | nein | jeweilige API | Rohes JSON in UI beguenstigt untypisierte Eingaben; Persistenzrisiko liegt beim Owner | **JSON als Austauschformat beibehalten**, wo eine strukturierte UI noch fehlt | Adapter duerfen nur oeffentliche APIs aufrufen; nach relationaler Migration typisierte Commands/Controls bevorzugen. |
| J43 | `.vscode/extensions.json`, `.vscode/settings.json` | Entwicklungsumgebung | Editor-Empfehlung, lokaler Interpreter und IDE-Startverhalten | VS Code | Entwickler/IDE | A | technisch | mutable durch Entwickler | nein | nein | lokaler Workspace | Nicht produktiv; kann persoenliche IDE-Praeferenzen mit Projektregeln vermischen | **JSON-Datei beibehalten** als optionale Entwicklungsumgebung, nicht als Runtime-Konfiguration | Keine Migration; aus Produkt-/Packagingpfaden ausgeschlossen halten. |
| J44 | `workflow_profile_imports.report_json` | Documents | Technischer Import-/Evidenzreport je Seed- oder Legacy-Importlauf (Profilzeilen, Hashes, Klassifikation, Blockgruende) | Profilstore/Admin-Diagnose | Bootstrap-/Upgrade-Import (`WorkflowProfileRelationalStore.import_seed`) | F | technisch | nach Importlauf unveraenderlich (Importzeile append-only) | ja | selten | Importlauf, Quelldatei, Profilcodes | Flexibles Report-JSON ohne Schema-Versionsfeld; kein fachlicher Zustand | **JSON-Spalte innerhalb der DB** als technische Evidenz neben relationalen Importmetadaten | Keine Normalisierung noetig; Allowlist und Gate absichern; Inhalt bleibt Nachweis, nicht Runtime-Wahrheit fuer Profile. |

## Nicht als eigene JSON-Persistenz bewertet

- JSON-Ausgabe auf `stdout` der CLI und HTTP-JSON sind Transport, keine dauerhafte Ablage.
- `json.dumps()` zur deterministischen Fingerprint-Bildung in `postgres_schema.py` speichert kein JSON.
- `usermanagement.audit_events.changed_fields` ist ein PostgreSQL-Array, keine JSON-Spalte.
- Testfixtures mit `tmp_path/*.json`, Inline-Payloads und Assertions bilden die oben genannten Produktionsvertraege ab, sind aber keine weiteren Laufzeit-Speicherorte.
- `build/`, Backup- und Exportartefakte sind keine fachliche Quelle der Wahrheit, auch wenn sie als Nachweis aufbewahrt werden.
- `packaging/dist_output/.../workflow_profiles.json` ist eine erzeugte Kopie von J03 und keine zweite Quelle. Sie wird durch den Build neu materialisiert und nie direkt migriert oder editiert.
- `tools/license_issuer_gui` schreibt lokale `config.json` und `issues.jsonl` unter dem Benutzerprofil des Issuer-Werkzeugs. Das ist kein Produkt-Runtime-Speicher und keine fachliche QM-Persistenz; Ausgabe von Lizenzdateien faellt unter J01.
- `training_assignment_snapshots` und vergleichbare Trainings-Snapshot-Tabellen sind relationale Zeilen ohne JSON-Spalte und daher keine eigene JSON-Persistenzfundstelle.
- Domain-`EventEnvelope.payload` ist derzeit nur In-Memory (J19); es gibt keine produktive Outbox-/`payload_json`-Tabelle.

## J00-Verifikation (2026-08-03)

**Ausfuehrungsbasis:** Worktree `I:/Projekte/QMToolV7-j00`, Branch `feature/j00-json-storage-baseline`, Tip `8a132ba`. Arbeitsverzeichnis = Repo-Root. Werkzeug: `rg` (ripgrep).

### Kopierbare Suchbefehle und Ergebniszuordnung

```text
# 1) Schema-Spalten *_json
rg -n "_json\b" -g "*.sql" modules qm_platform src
# → Documents/Incident/Training 0001_initial.sql → J20–J41

# 2) JSON-Schreiber und Dateipfade
rg -n "json\.dump|\.write_text\(|Path\([^\)]*\.json|open\([^\)]*\.json" -g "*.py" modules qm_platform interfaces src scripts packaging tools
# → Runtime-Schreiber J01–J12, J17–J19, J42; Tools → Abgrenzung license_issuer_gui; Tests nicht in diesem Pfad

# 3) Bekannte Runtime-/Bootstrap-Dateien
rg -n "settings\.json|current_user\.json|workflow_profiles\.json|migration_manifest\.json|license\.json|database-migration-journal|_state\.json|audit\.log|platform\.log" -g "*.py" modules qm_platform interfaces src scripts packaging
# → J02–J12, J03, J01, J07

# 4) Event-Payloads / Snapshots (JSON-Persistenz vs. relational)
rg -n "EventEnvelope|payload_json|outbox|snapshot" -g "*.py" modules qm_platform
# → J19 (In-Memory); Training-Assignment-Snapshots relational → Abgrenzung

# 5) Source-kontrollierte JSON/JSONL im Tree
rg --files -g "*.json" -g "*.jsonl" -g "!.venv/**" -g "!build/**" -g "!packaging/dist*/**"
# → license/license.json (J01), modules/documents/workflow_profiles.json (J03),
#    qm_platform/persistence/migration_manifest.json (J02)
```

PowerShell-Aequivalent fuer Befehl 5, falls `rg --files` mit Globs unpraktisch ist:

```powershell
Get-ChildItem -Recurse -Include *.json,*.jsonl -File |
  Where-Object { $_.FullName -notmatch '\\(\.venv|build|packaging\\dist)' } |
  ForEach-Object { $_.FullName.Substring((Get-Location).Path.Length + 1) }
```

### Gefunden, aber nicht inventarisiert (mit Abgrenzung)

| Fund | Befehl | Zuordnung / Abgrenzung |
|---|---|---|
| `tools/license_issuer_gui` `config.json` / `issues.jsonl` | 2 | begruendete Ausschlusszeile oben; kein Produkt-Runtime |
| CLI/HTTP `print(json.dumps(...))` und UI-Anzeige | 2 | Transport; Abschnitt "Nicht als eigene JSON-Persistenz" |
| Test-`tmp_path` JSON/JSONL | bewusst ausserhalb Befehl 2 (`tests/` nicht gesucht) | Testfixtures; Abgrenzung |
| Build-/Gate-/Drill-Output unter `build/` | 2 / 3 | J13–J16 bzw. Abgrenzung als Evidenz, nicht Wahrheit |
| Packaging-Kopie von `workflow_profiles.json` | 3 / 5 | Abgrenzung als Materialisierung von J03 |

### Inventarisiert, aber nicht aktiv im Tree

| ID | Befund |
|---|---|
| J43 | `.vscode/*.json` sind in `.gitignore` und im Clean-Tree abwesend; optionaler IDE-Pfad, keine Runtime |

Alle uebrigen aktiven Fundstellen der Suche sind den Inventar-IDs **J01–J44** oder einer dokumentierten Abgrenzung zugeordnet. J00 bleibt damit nicht blockiert.

Offene Zielentscheidungen in der Matrix verweisen explizit auf `JSON_STORAGE_OPEN_QUESTIONS.md`: J29/J31 → OQ-02, J39 → OQ-07.

## Wichtigste Befunde

1. Es gibt nur drei source-kontrollierte JSON-Dateien. Nur `workflow_profiles.json` enthaelt mutable fachliche Stammdaten und muss aus dem Runtime-Schreibpfad heraus.
2. `settings.json` ist nicht ein einzelner Datentyp. Bootstrap, technische Settings und fachliche Policies brauchen unterschiedliche Zielowner.
3. Die Documents-JSON-Listen fuer Akteure und Entscheidungen verletzen relationale Integritaet, Historisierung und den kuenftigen UUID-Vertrag.
4. `custom_fields_json` enthaelt bereits Kernfachlogik. Bekannte Teile muessen herausgeloest werden; nur echte flexible Leaf-Metadaten duerfen JSON bleiben.
5. Kommentaranker, Artefaktmetadaten und unveraenderliche Quiz-/Profilsnapshots sind legitime JSON-Spalten, wenn Schema-Version, Hash und Unveraenderlichkeit abgesichert sind.
6. Der synchrone `EventBus` ist kein Speicher. Autoritative Domain-Events benoetigen eine transaktionale Outbox im DB-Owner.
7. Das generische JSONL-Audit ist als Export brauchbar, aber fuer auditpflichtige Fachentscheidungen keine ausreichend gekoppelte Quelle der Wahrheit.
