# QMToolV7 – Ist-Soll-Mapping und schrittweiser Umbauplan

**Repository:** `layzieshin/QMToolV7`
**Modul:** `modules/documents`
**Vorgabe:** Bestehendes Modul umbauen, **nicht neu bauen**.

## 1. Bestehende Substanz, die erhalten werden soll

Im aktuellen Code sind bereits wichtige Bausteine vorhanden:

- `DocumentStatus`, `DocumentHeader`, `DocumentVersionState`, `DocumentArtifact`
- `WorkflowProfile` mit Phasen, Vier-Augen-Regel und signaturpflichtigen Übergängen
- Profilvarianten in `modules/documents/workflow_profiles.json`
- Rollenpools über `WorkflowAssignments`
- Workflow-Use-Cases für Start, Einreichung, Prüfung, Freigabe, Ablehnung und Abbruch
- Artefaktablage mit aktuellen Artefakten je Typ
- DOCX→PDF-Konvertierung
- kumulative Signaturkette
- Gültigkeitsverlängerung mit `extension_count`
- Archivierung und Erzeugung einer neuen Version aus dem Archiv
- öffentliche API-Grenze in `modules/documents/api.py`
- Event-, Registry- und Audit-Anbindungen
- Kommentar- und Lesefunktionen

Diese Funktionen werden refaktoriert und erweitert. Sie werden nicht pauschal ersetzt.

## 2. Ist-Soll-Mapping

| Ist-Baustein | Soll | Art des Umbaus |
|---|---|---|
| `DocumentStatus.PLANNED` | separates `DocumentPlan` | neues Objekt ergänzen, Altstatus temporär migrieren, danach entfernen |
| `DocumentStatus.IN_PROGRESS` | `DRAFT` | Enum/DB/API kompatibel migrieren, Übergangs-Alias vorübergehend erlauben |
| `APPROVED` als faktisch freigegeben/teilweise veröffentlicht | klare Trennung `APPROVED`/`PUBLISHED` | neue Publish-Use-Case und API-Filter |
| kein Ablaufstatus | `EXPIRED` | automatischer Statuswechsel und Zugriffsfilter |
| kein Annullierungsstatus | `ANNULLED` | endgültiger Auditstatus + Korrekturfassung |
| `DocumentVersionState` bündelt Dokument-, Versions- und Workflowdaten | getrennte Aggregate/Tabellen | schrittweise normalisieren; vorerst Adapter auf Altstruktur |
| `DocumentHeader` mit Verteilungsfeldern | Dokumentmetadaten ohne Trainingszielgruppen | Verteilungsfelder deprecaten; Training separat |
| feste `DocumentType`-Enum | konfigurierbare Dokumentenarten | Stammdatentabelle + Kompatibilitätsadapter für Enum-Werte |
| `ControlClass` separat | kein fachliches Eingabefeld; höchstens technische Übergangsmetadaten | Redundanz prüfen, später deprecaten oder intern ableiten |
| Workflowprofil enthält Phasenliste | feste Status + konfigurierbare Übergänge | Profilschema versionieren und auf Transition-Definitionen umstellen |
| unversionierte JSON-Profile | `WorkflowProfileVersion` | persistierte Profile und Versionen; JSON als Seed/Migration |
| `WorkflowAssignments` mit drei Sets | konkrete Rollenpools je Workflowinstanz | erweitern um Zustimmungsregel, Entscheidungen, Poolversion und Berechtigungsprüfung |
| keine eigene Workflowinstanz | `WorkflowInstance` | neue Entität; bestehenden State zunächst referenzieren |
| keine Einreichungsrunden | `SubmissionRound` | neue Entität für wiederholte Ablehnungs-/Einreichungszyklen |
| `reviewed_by`/`approved_by` als Sets im State | unveränderliche `WorkflowDecision`-Datensätze | Altwerte migrieren, Sets nur noch als Read-Model ableiten |
| Signatur-/Artefaktkette je Version | zusätzlich Workflowinstanz/Runde zuordnen | bestehende Artefakte erweitern, nicht neu implementieren |
| `valid_from` wird bei Freigabe gesetzt | `valid_from = published_at` | Freigabe- und Publish-Use-Case trennen |
| Standard 365 Tage | Standard zwei Jahre, konfigurierbar | Konfiguration + Migration, bestehende Verlängerungslogik behalten |
| Verlängerung nur in `APPROVED` | `PUBLISHED` und `EXPIRED` | Statusprüfung anpassen |
| nach dritter Verlängerung weiter `next_review_at` | danach `next_review_at = NULL` | kleine Regeländerung |
| Archivierung nur aus `APPROVED` | begründete Archivierung aus zulässigen Zuständen | Use-Case verallgemeinern, aktiven Workflow vorher beenden |
| neue Version nur aus `ARCHIVED` | aus aktueller/archivierter Historie, höchstens ein offener Nachfolger | neuer zentraler Use-Case; alten Wrapper weiterführen |
| API `list_current_released_documents()` | nur gültige `PUBLISHED` | Semantik schärfen, alter Methodenname vorübergehend delegieren |
| Systemrolle `ADMIN` als fachlicher Override | Admin technisch; fachlich nur mit Modulrolle | Service-Gates umbauen |
| direkte Actor-/Systemrollenprüfungen | konfigurierbare Modulrollen + konkrete Workflowzuordnung | neues Autorisierungsmodell vor die Use-Cases setzen |
| keine gelenkten Kopien | global optionales Druck-/Kopienmodell | neue Entitäten/API/Events, bestehendes PDF-Abrufsystem nutzen |

## 3. Zielentitäten und empfohlene Persistenz

Neue/normalisierte Tabellen oder Repositories:

1. `document_plans`
2. `documents`
3. `document_versions`
4. `document_type_definitions`
5. `workflow_profile_definitions`
6. `workflow_profile_versions`
7. `workflow_instances`
8. `workflow_transition_instances`
9. `workflow_role_assignments`
10. `workflow_decisions`
11. `submission_rounds`
12. `document_change_entries`
13. Erweiterung `document_artifacts` um `workflow_instance_id`, `submission_round_id`, `decision_id`
14. `document_module_roles`
15. `document_module_permissions`
16. `document_user_module_roles`
17. `controlled_print_jobs`
18. `controlled_copies`
19. `copy_recall_cases`
20. `retention_rules` oder entsprechende Felder an `document_versions`

Die konkrete Tabellenaufteilung darf an die bestehende Repositorystruktur angepasst werden. Wichtig sind die fachlichen Grenzen, nicht die Namen.

## 4. Kompatibilitätsstrategie

### 4.1 Keine Big-Bang-Migration

Während der Migration:

- alte API-Methoden bleiben als Adapter bestehen
- bestehende GUI darf weiterhin mit `DocumentVersionState` arbeiten
- neuer normalisierter Kern liefert ein kompatibles Read-Model
- alte Statuswerte werden beim Lesen normalisiert
- neue Writes erfolgen möglichst nur noch über die neuen Use-Cases

### 4.2 Statuskompatibilität

Temporäre Abbildung:

- `PLANNED` → Legacy-Plan bzw. zu migrierender `DocumentPlan`
- `IN_PROGRESS` → `DRAFT`
- `APPROVED` bleibt `APPROVED`, darf aber nicht länger als veröffentlicht gelten
- bisherige freigegebene aktive Bestandsfassungen müssen bei Migration entweder als `PUBLISHED` markiert oder anhand vorhandener Release-Artefakte/Registrydaten eindeutig klassifiziert werden

Keine stille automatische Klassifizierung bei Mehrdeutigkeit. Unklare Datensätze in einen Migrationsbericht aufnehmen.

## 5. Phasen des Umbaus

### Phase 0 – Sicherheitsnetz und Bestandsaufnahme

- bestehende Tests vollständig ausführen
- DB-/Dateisicherung dokumentieren
- Golden-Master-Datensatz mit interner VA, externem PDF, Ablehnung, Freigabe, Verlängerung und Archiv anlegen
- aktuelle öffentliche API und Eventnamen erfassen
- Migrationsbericht-Mechanik vorbereiten

**Kein fachlicher Umbau in dieser Phase.**

### Phase 1 – Neue Status und kompatibles Read-Model

- `DRAFT`, `PUBLISHED`, `EXPIRED`, `ANNULLED` ergänzen
- `IN_PROGRESS` als Legacyalias behandeln
- Statusinvarianten zentralisieren
- API noch nicht hart umstellen, aber neue Filtertests ergänzen
- `DocumentVersionState` um interne `version_record_id`, `approved_at`, `published_at`, Annullierungsdaten erweitern

### Phase 2 – `DocumentPlan` auskoppeln

- `DocumentPlan` + Repository + Use-Cases einführen
- atomaren Convert-Use-Case implementieren
- bestehende `PLANNED`-Datensätze migrieren
- GUI/API vorübergehend über Adapter anbinden
- nach erfolgreicher Migration `PLANNED` aus neuen Writes entfernen

### Phase 3 – Dokument und Version sauber trennen

- `Document` als dauerhafte Identität persistieren
- versionierbare Snapshots und aktuelle Dokumentmetadaten trennen
- Kurzbeschreibung dokumentgebunden machen
- Titel und Änderungsanlass versionsgebunden machen
- Kennungsreservierung und Entwurfsverwerfung implementieren
- konfigurierbare Dokumentenarten einführen

### Phase 4 – Workflowinstanz, Einreichungsrunden und Kommentarbindung

- `WorkflowInstance`, `SubmissionRound`, `WorkflowDecision` ergänzen
- vorhandene `reviewed_by`, `approved_by` und Signaturflags migrieren/ableiten
- Ablehnung immer nach `DRAFT`
- Rücknahme `APPROVED → DRAFT` als neue Workflowinstanz
- maximal eine aktive Workflowinstanz erzwingen

### Phase 5 – Versionierte Übergangsprofile

- bestehende JSON-Profile als Seeds importieren
- Profildefinition + Profilversion persistieren
- feste Status, konfigurierbare Übergänge
- `ONE_OF_POOL`, `ALL_ASSIGNED`, Frist, Signaturpflicht und `revoke_if_changed`
- Profilsnapshot in Workflowinstanz
- bestehende `phases`-Profile über Adapter in Transitionen übersetzen

### Phase 6 – Modulrollen und Autorisierung

- Modulrollen und atomare Berechtigungen einführen
- Systemrolle `ADMIN` von fachlichen Overrides trennen
- QMB als fachlicher Verwalter
- konkrete Workflowzuordnung als zweite Autorisierungsebene
- Vier-Augen-Prüfung auf unmittelbar aufeinanderfolgende ausgeführte Stufen umstellen
- Ersatzpflicht vor Rollenentzug/Benutzerdeaktivierung als Port zum Usermanagement bereitstellen

### Phase 7 – Veröffentlichung, Ablauf und Verlängerung

- eigener Publish-Use-Case
- `valid_from = published_at`
- bisherige `PUBLISHED`-Version im selben Transaktionsrahmen archivieren
- API nur auf gültige `PUBLISHED`-Fassungen umstellen
- Ablaufjob/Event `PUBLISHED → EXPIRED`
- Verlängerung auf `PUBLISHED`/`EXPIRED` anpassen
- Standardintervall zwei Jahre, maximal drei Verlängerungen, danach kein `next_review_at`

### Phase 8 – Artefakt-, Kommentar- und Auditverknüpfung

- vorhandene Artefakte um Workflow-/Rundenbezug erweitern
- Ablehnungsartefakt-Regeln umsetzen
- finale Veröffentlichung weiterhin aus vorhandener PDF-/Signaturlogik erzeugen
- Auditformat vereinheitlichen
- alle QMB-Overrides mit Alt/Neu/Begründung

### Phase 9 – Gelenkte Ausdrucke

- globale Modulkonfiguration
- Print-API
- Kopiennummern je Version
- sichtbarer Kopienvermerk
- Rückrufevent bei Nachfolgeveröffentlichung
- Sammelabschluss mit vernichtet/nicht gefunden

### Phase 10 – Aufräumen

Erst nach erfolgreicher Migration und Tests:

- `PLANNED` und `IN_PROGRESS` aus produktiven Writes entfernen
- Legacyadapter kennzeichnen/deprecaten
- redundante `ControlClass` fachlich entfernen oder als rein interne Ableitung belassen
- Verteilungsfelder im Documents-Modul entfernen/deprecaten
- alte JSON-Profilverwaltung durch Seed-/Exportfunktion ersetzen

## 6. Transaktionsgrenzen

Folgende Vorgänge müssen konsistent/atomar sein:

- Plan → Dokument + Version 1 + `DRAFT` + Audit; danach Plan löschen
- Workflowstart inklusive Profil, Rollenpools und Pflichtprüfung
- Veröffentlichung einer Nachfolgeversion inklusive Archivierung der Vorgängerversion
- Ersetzung eines aktiven Workflowakteurs plus Entzug/Deaktivierung
- Annullierung plus Sperrung der Fassung
- Vergabe mehrerer Kopiennummern in einem Druckauftrag

## 7. Öffentliche API – Migrationsziel

Empfohlene neue Fähigkeiten:

- `list_current_published_documents(now)`
- `get_current_published_document(document_id, now)`
- `get_published_pdf(document_id, now)`
- `create_controlled_print_job(document_id, count, actor, source_module)`
- `create_plan(...)`, `convert_plan_to_draft(...)`
- `create_next_version(document_id, reason, actor)`
- `start_workflow(version_record_id, profile_version_id, assignments, actor)`
- `execute_transition(...)`
- `publish(...)`, `extend_validity(...)`, `archive(...)`, `annul(...)`

Bestehende Methoden werden zunächst delegierende Wrapper.

## 8. Eventmigration und Dashboard-Aufgaben

Repo-Befund:

- Der aktuelle `EventBus` ruft nur aktuell registrierte Subscriber synchron auf und speichert Events nicht dauerhaft.
- Das Dashboard liest Aufgaben derzeit über `DocumentsReadmodelUseCases` aus Status und Zuweisungen.
- Das Documents-Modul besitzt bereits v1-Events und Eventvertragstests.
- Kommentare besitzen eigene Eventstellen, deren Actor- und Objektbezug erweitert werden soll.

Vorgehen:

1. vollständigen v2-Katalog aus `QMToolV7_Dokumentenlenkung_Eventkatalog.md` als Contracts festlegen,
2. für jeden erfolgreichen Workflow-/Statusübergang ein spezifisches Event mit einheitlichem Routingpayload erzeugen,
3. Actor, Correlation und Causation verpflichtend aus dem Use-Case-Kontext übernehmen,
4. Events erst nach erfolgreichem Fachcommit publizieren,
5. während der Übergangszeit gezielt v1 und v2 parallel publizieren,
6. Dashboard, Training und Registry consumerweise migrieren,
7. Consumer idempotent gegen Doppelzustellung und Dual-Publish machen,
8. zustandsbasiertes Dashboard bis zu einer späteren dauerhaften Outbox/Projection beibehalten,
9. alte Events erst nach Repository-weiter Suche, Consumer-Migration und Vertragstests deprecaten.

Ein fehlender Consumer darf keinen fachlichen Use Case blockieren. Ein flüchtiges Event ist aber keine dauerhafte Aufgabenpersistenz.

## 9. Teststrategie

Für jeden mutierenden Use-Case mindestens:

- Happy Path
- falscher Ausgangsstatus
- fehlende Modulberechtigung
- fehlende konkrete Workflowzuweisung
- Vier-Augen-Verletzung
- fehlende Pflichtdaten/Quelldatei
- Transaktionsabbruch ohne Teilzustand
- Auditinhalt
- Eventinhalt
- Artefakt-/Hashbezug
- Wiederholungs-/Idempotenzfall, soweit relevant

Zentrale Invariantentests:

- maximal eine gültige `PUBLISHED`-Version
- maximal eine offene Nachfolgeversion
- maximal eine aktive Workflowinstanz je Version
- `ANNULLED` ist endgültig
- `APPROVED` ist nicht öffentlich abrufbar
- `EXPIRED` ist nicht les-/druckbar für normale Nutzer
- keine fachliche Adminmacht ohne Modulrolle
- keine Aktion nur aufgrund einer allgemeinen Modulrolle ohne konkrete Workflowzuweisung
- keine zwei aufeinanderfolgenden Aktionen durch dieselbe Person bei Vier-Augen-Profil
- Ablehnung führt immer zu `DRAFT`
- Profiländerung beeinflusst laufende Instanz nicht

## 10. Nicht im ersten Umbaupaket

- GUI-Neugestaltung
- automatische Dokumentreferenzen
- aktives Wasserzeichen
- automatischer DOCX-Diff
- neue Kommentar-Blockerregeln oder ein Kommentarsystem-Neuentwurf; bestehende Word-/PDF-Kommentarfunktionen bleiben erhalten
- Trainingsmodul
- Abweichungsmodul
- physische Löschung historischer Daten

## 11. Abnahmekriterien des Gesamtumbaus

Der Umbau ist fachlich abgeschlossen, wenn:

1. die Status- und Versionsinvarianten durch Service und DB abgesichert sind,
2. Bestandsdaten ohne Verlust migriert wurden,
3. bestehende Signatur- und Artefaktketten weiterhin funktionieren,
4. andere Module nur gültige `PUBLISHED`-Versionen erhalten,
5. Rollen und Berechtigungen auf beiden Ebenen geprüft werden,
6. alle relevanten Aktionen auditierbar sind,
7. die komplette Testsuite sowie neue Invariantentests grün sind,
8. jeder erfolgreiche Workflow-/Statusübergang einen getesteten v2-Eventvertrag besitzt,
9. Word- und PDF-Kommentare einschließlich Statushistorie und Runden-/Artefaktbezug erhalten sind,
10. kein Big-Bang-Rewrite oder paralleles zweites Documents-Modul entstanden ist.
