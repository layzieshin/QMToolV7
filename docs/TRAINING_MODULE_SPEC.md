# Verbindliche Developer-Vorgabe – Schulungsmodul

Status: verbindliche Umsetzungs- und Architekturvorgabe  
Geltungsbereich: `modules/training`, betroffene GUI in `interfaces/pyqt/*`, erforderliche Ergänzungen in `modules/documents` und `modules/usermanagement`

---

## 1. Nicht verhandelbare Regeln

### 1.1 Rollen- und Aufgabengrenze
- Das Schulungsmodul ist **fachlicher Owner** für:
  - trainingsbezogene Dokumentauswahl
  - Dokument-Tags
  - Benutzer-Tags
  - manuelle Aufnahme
  - Befreiung / Ausnahme
  - Quiz-Import
  - Quiz-Zuordnung
  - materialisierte Schulungspflichten pro Benutzer und Dokumentversion
  - Quiz-Durchführung und Trainingsfortschritt
  - Trainingskommentare
- Das Dokumentenmodul bleibt **fachlicher Owner** für:
  - Dokumentstatus
  - freigegebene Dokumentversionen
  - Dokument-Metadaten
  - Released-Artefakte
  - dokumentbezogene Lese-/Öffnungsbestätigung
- Das Usermanagement bleibt **fachlicher Owner** für:
  - Benutzeridentität
  - Rolle
  - Benutzer-Stammdaten wie Abteilung / Scope / Organisationseinheit

### 1.2 Öffentliche Schnittstellen
- Öffentliche Modul-Schnittstellen liegen ausschließlich in `modules/<modul>/api.py`.
- Keine Re-Exports, keine Wrapper-APIs in Hilfsdateien.
- Keine GUI-Fachlogik.
- Keine Controller-Fachlogik.
- Keine Vermischung von Persistenz, Fachlogik und GUI.

### 1.3 SRP / Phase-Isolation
- Jede fachliche Verantwortung bekommt **einen eigenen Dateibereich**.
- Keine God-File-Implementierung.
- Import, Zuordnung, Snapshot-Erzeugung, Kommentare, Quizausführung, Tag-Verwaltung, Inbox-Abfrage und Befreiungen dürfen **nicht** in einer zentralen Datei zusammengezogen werden.

### 1.4 Harte fachliche Regel für Schulungspflicht
Ein Dokument ist für einen Benutzer schulungspflichtig, wenn mindestens eine positive Zuweisung greift:
- Scope-Basis
- Tag-Zuordnung
- manuelle Aufnahme

Danach wird eine aktive Befreiung geprüft.

Verbindliche Priorität:
1. Befreiung / manueller Ausschluss
2. manuelle Aufnahme
3. Tag-Zuordnung
4. Scope-Basis

Zusätzlich verbindlich:
- Tags sind **nur positiv/additiv**.
- Negative Tags sind verboten.
- Ausschlüsse werden ausschließlich als **Befreiung** modelliert.
- Befreiungen sind standardmäßig **versionsbezogen**, optional zusätzlich **befristet**.
- Das Ergebnis wird **materialisiert** gespeichert und nicht nur live zusammengeraten.

---

## 2. Zielbild des Moduls

Das Schulungsmodul erzeugt und verwaltet eine **materialisierte Trainingssicht** je Benutzer und Dokumentversion.

Diese Sicht beantwortet nicht nur `ja/nein`, sondern mindestens:
- schulungspflichtig durch Scope
- schulungspflichtig durch Tag
- schulungspflichtig durch manuelle Aufnahme
- befreit
- nicht relevant

`befreit` ist fachlich **nicht** dasselbe wie `nicht relevant`.

Die GUI liest im Normalfall **nur diese materialisierte Sicht**. Die GUI darf die Zuweisungsregeln nicht selbst neu berechnen.

---

## 3. Verbindliche interne Verantwortlichkeitsbereiche im Schulungsmodul

Jeder Bereich bekommt eigene Datei(en) und eigene Tests.

### 3.1 ReleasedDocumentCatalogReader
Aufgabe:
- liest freigegebene Dokumente aus dem Dokumentenmodul
- ergänzt trainingsrelevante Headerdaten

Verwendete Fremd-API:
- `documents_pool_api.list_by_status(DocumentStatus.APPROVED)`
- `documents_pool_api.get_header(document_id)`

Nicht erlaubt:
- keine Quizlogik
- keine Taglogik
- keine Benutzerzuordnung
- keine Snapshot-Persistenz

### 3.2 ScopeResolver
Aufgabe:
- prüft Scope-Basis zwischen Benutzer und Dokument

Eingaben:
- Dokument-Scope aus Dokumentheader
- Benutzerdaten aus Usermanagement

Nicht erlaubt:
- keine Persistenz
- keine Befreiung
- keine Quizzuordnung

### 3.3 DocumentTagService
Aufgabe:
- verwaltet Tags je Dokumentenkennung

### 3.4 UserTagService
Aufgabe:
- verwaltet Tags je Benutzer

### 3.5 QuizImportService
Aufgabe:
- importiert Quiz-JSON
- validiert Pflichtfelder
- versucht automatische Dokumentzuordnung
- markiert nicht auflösbare Importe für manuelle Zuordnung

### 3.6 QuizBindingService
Aufgabe:
- verwaltet Bindung `document_id -> quiz`

### 3.7 ManualAssignmentService
Aufgabe:
- verwaltet manuelle Aufnahme

### 3.8 ExemptionService
Aufgabe:
- verwaltet Befreiung / Ausnahme
- speichert Grund, Ersteller, Zeitpunkt, optionale Frist, Versionsbezug

### 3.9 TrainingAssignmentResolver
Aufgabe:
- führt Scope, Tags, manuelle Aufnahme und Befreiung in definierter Reihenfolge zusammen

### 3.10 TrainingSnapshotProjector
Aufgabe:
- materialisiert Pflichtsicht pro Benutzer und Dokumentversion
- schreibt das Ergebnis in Trainings-Readmodel

### 3.11 TrainingInboxQueryService
Aufgabe:
- liefert dem angemeldeten Benutzer seine sichtbaren Schulungen
- ausschließlich aus materialisierten Snapshots plus Fortschritt

### 3.12 QuizExecutionService
Aufgabe:
- startet Quiz
- validiert Antworten
- schreibt Ergebnisse

### 3.13 TrainingCommentService
Aufgabe:
- speichert Benutzerkommentare
- liefert Kommentarlisten für QMB/Admin
- setzt Kommentarstatus um

### 3.14 TrainingReportService
Aufgabe:
- Statistik / Logs / Audit-Auswertungen

---

## 4. Verbindliche Datei- und Modulstruktur

### 4.1 Öffentliche Ports
- `modules/training/api.py`
  - enthält ausschließlich die öffentlichen Ports `training_api` und `training_admin_api`
  - enthält keine Fachlogik

### 4.2 Interne Fachdateien
Mindestens getrennt in:
- `released_document_catalog_reader.py`
- `scope_resolver.py`
- `document_tag_service.py`
- `user_tag_service.py`
- `quiz_import_service.py`
- `quiz_binding_service.py`
- `manual_assignment_service.py`
- `exemption_service.py`
- `training_assignment_resolver.py`
- `training_snapshot_projector.py`
- `training_inbox_query_service.py`
- `quiz_execution_service.py`
- `training_comment_service.py`
- `training_report_service.py`

### 4.3 Persistenzdateien
Mindestens getrennt in:
- `training_snapshot_repository.py`
- `training_tag_repository.py`
- `training_quiz_repository.py`
- `training_override_repository.py`
- `training_comment_repository.py`
- `training_report_repository.py`

### 4.4 Bestehende Altstruktur
Die heutige Struktur aus:
- `modules/training/service.py`
- `modules/training/assignment_use_cases.py`
- `modules/training/sqlite_repository.py`
ist für den Zielzustand zu breit und muss aufgespalten werden.

### 4.5 Verboten
- keine zentrale Megaklasse
- keine Sammeldatei mit allen Verantwortlichkeiten
- keine GUI-Datei mit Geschäftslogik
- keine direkte SQL-Logik in GUI oder API-Port-Dateien

---

## 5. Fremd-APIs, die verbindlich verwendet werden sollen

## 5.1 Dokumentenmodul – bestehende APIs übernehmen

### Verbindlich verwenden
#### `documents_pool_api.list_by_status(DocumentStatus.APPROVED)`
Verwendung:
- Quelle aller freigegebenen Dokumentversionen
- Grundlage für Trainings-Snapshots
- Grundlage für Quiz-Zuordnung und manuelle Auswahllisten

#### `documents_pool_api.get_header(document_id)`
Verwendung:
- Scope-relevante Dokumentdaten
- insbesondere `department`, `site`, `regulatory_scope`

#### `documents_pool_api.list_current_released_documents()`
Verwendung:
- nur für Listen / Picker / reine Anzeige
- nicht als alleinige Regelquelle

### Nicht im Trainingskern verwenden
- `documents_pool_api.list_artifacts(...)`
- `documents_workflow_api`
- `documents_service`

Der Trainingskern darf keine Workflow- oder Artefaktverantwortung übernehmen.

## 5.2 Usermanagement – bestehende API nur übergangsweise direkt verwenden

Aktueller Ist-Stand:
- `usermanagement_service.get_current_user()`
- `usermanagement_service.list_users()`

Zielzustand:
- eigenes öffentliches Read-API im Usermanagement, z. B. `usermanagement_read_api`

Erforderliche Read-Funktionen:
- `get_current_user()`
- `get_user(user_id)`
- `list_users()` oder `list_active_users()`

Benötigte Benutzerfelder:
- `user_id`
- `username`
- `role`
- `department`
- `scope`
- `organization_unit`
- `is_active`

---

## 6. Neue bzw. geänderte öffentliche APIs

## 6.1 Dokumentenmodul – neue spezialisierte Read-Confirmation-API erforderlich

Weil die Aktion `Lesen` laut Anforderung **durch das Dokumentenmodul bestätigt werden muss**, reicht `documents_pool_api` nicht aus.

Es ist eine **neue spezialisierte Dokumenten-Schnittstelle** einzuführen, z. B. `documents_read_api`.

### Verbindliche Verantwortung von `documents_read_api`
- released Dokumentversion für Benutzer im Trainingskontext öffnen
- Lese-/Öffnungsbestätigung dokumentmodulseitig erzeugen
- bestätigte Lesebelege für Training abfragbar machen

### Empfohlene öffentliche Funktionen
- `open_released_document_for_training(user_id: str, document_id: str, version: int) -> DocumentReadSession`
- `confirm_released_document_read(user_id: str, document_id: str, version: int, *, source: str) -> DocumentReadReceipt`
- `get_read_receipt(user_id: str, document_id: str, version: int) -> DocumentReadReceipt | None`

Wichtig:
- Diese API ist **nicht** Teil des Dokumentenpools.
- Diese API ist fachlich vom Dokumentenmodul zu verantworten.
- Das Trainingsmodul darf das Lesen nicht mehr allein per UI-Parameter behaupten.

## 6.2 Trainingsmodul – Zielzustand `training_api`

### Beibehalten, aber fachlich umbauen
- `confirm_read(...)` wird **nicht** mehr direkt von der GUI als Wahrheitsquelle verwendet.
- Stattdessen darf diese Funktion nur noch verwendet werden, um eine bereits im Dokumentenmodul bestätigte Lesehandlung in den Trainingsfortschritt zu übernehmen, oder sie entfällt ganz zugunsten eventgetriebener Übernahme.

### Verbindlich neu / ersetzt
- `list_training_inbox_for_user(user_id: str, open_only: bool = False) -> list[TrainingInboxItem]`
  - ersetzt die bisherigen Mischfunktionen
  - liefert nur materialisierte, wirksame Schulungen

### Beibehalten
- `start_quiz(user_id: str, document_id: str, version: int) -> tuple[QuizSession, list[QuizQuestion]]`
- `submit_quiz_answers(session_id: str, answers: list[int]) -> QuizResult`
- `add_comment(user_id: str, document_id: str, version: int, comment_text: str) -> TrainingComment`

### Ergänzen
- `list_comments_for_document(document_id: str, version: int) -> list[TrainingCommentListItem]`
  - nur falls Benutzer-Sicht Kommentare pro Dokument sehen soll

## 6.3 Trainingsmodul – Zielzustand `training_admin_api`

### Wichtige Ergänzung zur Quiz-Ersetzung
Wenn für dieselbe `document_id` und denselben fachlich relevanten Bindungsbereich bereits ein aktives Quiz existiert und ein neues Quiz importiert wird, darf dieses **nicht stillschweigend überschrieben** werden.

Verbindlich:
- Das System muss einen **Ersetzungsfall erkennen**.
- Vor dem Ersetzen muss eine **explizite Abfrage / Bestätigung** erfolgen.
- Ohne bestätigte Ersetzung darf das alte aktive Quiz nicht deaktiviert oder überschrieben werden.
- Die Ersetzung muss historisiert werden.
- Die Historie muss nachvollziehbar machen:
  - welches Quiz ersetzt wurde
  - wodurch es ersetzt wurde
  - wer die Ersetzung bestätigt hat
  - wann die Ersetzung erfolgte

Empfohlene zusätzliche Admin-Funktionen:
- `check_quiz_replacement_conflict(raw_quiz_json: bytes) -> QuizReplacementCheckResult`
- `replace_quiz_binding(conflict_id: str, confirmed_by: str) -> QuizBindingReplacementResult`
- `export_training_matrix(...) -> TrainingMatrixExportResult`

Die Exportfunktion ist verpflichtend, weil die Schulungsmatrix auswertbar und exportierbar sein muss.

## 6.4 Tests als verpflichtender Bestandteil der Umsetzung

Die Umsetzung ist ohne automatisierte Tests **nicht abnahmefähig**.

Es sind mindestens folgende Testarten aufzubauen:
- Domänen-/Service-Tests für Resolver, Import, Binding, Kommentarstatus, Exemptions und Snapshot-Projektion
- Repository-Tests für Persistenz und Historisierung
- API-Tests für `training_api`, `training_admin_api` und die neue dokumentseitige Read-Confirmation-API
- GUI-/Presenter-Tests für Rollen, Sichtbarkeit, Aktivierung und Listenaktualisierung
- Export-Tests für die Schulungsmatrix
- Event-Tests für Event-Erzeugung nach Commit und korrekte Projektion

---

## 6.5 Verbindliches Quiz-Importschema

Das Quiz-Importschema ist verbindlich in JSON zu unterstützen.

Pflichtfelder auf Wurzelebene:
- `document_id: string`
- `document_version: integer`
- `questions: array`

Pflichtfelder je Frage:
- `question_id: string`
- `text: string`
- `answers: array`
- `correct_answer_id: string`

Pflichtfelder je Antwort:
- `answer_id: string`
- `text: string`

Verbindliche Regeln:
- `document_id` ist Pflicht und primärer Zuordnungsschlüssel.
- `document_version` ist Pflicht und muss im Importvertrag mitgeführt werden.
- Jede Frage muss genau **eine** `correct_answer_id` besitzen.
- Jede `correct_answer_id` muss auf genau eine vorhandene Antwort der betreffenden Frage verweisen.
- Pro Frage müssen genau **vier** Antworten importierbar sein, weil das gelieferte Sollschema diesen Aufbau vorgibt.
- `question_id` muss innerhalb eines Quiz eindeutig sein.
- `answer_id` muss innerhalb einer Frage eindeutig sein.
- Die Antwortreihenfolge darf im Quizdurchlauf gemischt werden, die fachliche Korrektheit bleibt aber an `correct_answer_id` gebunden.
- Mehrfachrichtige Antworten sind nicht zulässig.

Verbindliches Schema-Beispiel:

```json
{
  "document_id": "C02VA001",
  "document_version": 1,
  "questions": [
    {
      "question_id": "Q1",
      "text": "Wann darf ein Mitarbeiter das Quiz starten?",
      "answers": [
        { "answer_id": "a1", "text": "Sobald das Dokument als gelesen markiert wurde" },
        { "answer_id": "a2", "text": "Direkt nach dem Login" },
        { "answer_id": "a3", "text": "Erst nach Freigabe durch den Admin" },
        { "answer_id": "a4", "text": "Nur nach Abschluss eines anderen Quiz" }
      ],
      "correct_answer_id": "a1"
    },
    {
      "question_id": "Q2",
      "text": "Wie viele Fragen werden pro Quizdurchlauf gestellt?",
      "answers": [
        { "answer_id": "a1", "text": "3" },
        { "answer_id": "a2", "text": "2" },
        { "answer_id": "a3", "text": "5" },
        { "answer_id": "a4", "text": "Alle Fragen aus dem Pool" }
      ],
      "correct_answer_id": "a1"
    },
    {
      "question_id": "Q3",
      "text": "Wann gilt das Quiz als bestanden?",
      "answers": [
        { "answer_id": "a1", "text": "Wenn alle 3 Fragen richtig beantwortet wurden" },
        { "answer_id": "a2", "text": "Wenn 2 von 3 Fragen richtig sind" },
        { "answer_id": "a3", "text": "Wenn mindestens 50 Prozent erreicht wurden" },
        { "answer_id": "a4", "text": "Wenn das Quiz vollständig geöffnet wurde" }
      ],
      "correct_answer_id": "a1"
    },
    {
      "question_id": "Q4",
      "text": "Was darf der Quiz-Mechanismus bei den Antworten tun?",
      "answers": [
        { "answer_id": "a1", "text": "Die Antwortreihenfolge zufällig mischen" },
        { "answer_id": "a2", "text": "Mehrere richtige Antworten erzeugen" },
        { "answer_id": "a3", "text": "Die Frage überspringen" },
        { "answer_id": "a4", "text": "Die richtige Antwort ausblenden" }
      ],
      "correct_answer_id": "a1"
    }
  ]
}
```

Die Validierung dieses Schemas gehört ausschließlich in den `QuizImportService` und nicht in GUI, Controller oder Repository.

---

## 6.6 Zusätzliche/angepasste öffentliche Funktionen wegen Import, Ersetzung und Export

### Ergänzungen in `training_admin_api`
Verbindlich zusätzlich zu den bereits definierten Methoden:
- `check_quiz_replacement_conflict(raw_quiz_json: bytes) -> QuizReplacementCheckResult`
- `replace_quiz_binding(conflict_id: str, confirmed_by: str) -> QuizBindingReplacementResult`
- `export_training_matrix(...) -> TrainingMatrixExportResult`

### Fachliche Bedeutung
- `check_quiz_replacement_conflict(...)` prüft vor Aktivierung eines neuen Imports, ob bereits ein aktives Quiz für dieselbe fachliche Bindung existiert.
- `replace_quiz_binding(...)` führt den bestätigten Ersetzungsfall aus und historisiert ihn.
- `export_training_matrix(...)` erzeugt den Export der materialisierten Trainingssicht.

### Verbindliche Exportanforderung
Die exportierte Schulungsmatrix muss **nach Benutzer sortiert** mindestens enthalten:
- Benutzer
- welche Dokumente dem Benutzer zugewiesen sind
- welche davon bestanden sind
- welche davon nicht bestanden sind
- welche davon offen sind

Die konkrete Dateiform des Exports ist hiermit noch nicht festgelegt. Fachlich verpflichtend ist der Inhalt, nicht das Dateiformat.

---

## 7. Bestehende Trainingsfunktionen, die entfernt oder ersetzt werden müssen

### Dokumentlisten / Snapshots
- `list_assignable_documents() -> list[TrainingDocumentRef]`
- `list_assignment_snapshots(...) -> list[TrainingAssignmentSnapshot]`
- `rebuild_assignment_snapshots(...) -> int`

### Quiz
- `import_quiz_json(raw_quiz_json: bytes) -> QuizImportResult`
- `list_pending_quiz_mappings() -> list[PendingQuizMapping]`
- `bind_quiz_to_document(import_id: str, document_id: str) -> QuizBinding`
- `list_quiz_bindings() -> list[QuizBinding]`

### Dokument-Tags
- `list_document_tags(document_id: str) -> DocumentTagSet`
- `set_document_tags(document_id: str, tags: list[str]) -> DocumentTagSet`

### Benutzer-Tags
- `list_user_tags(user_id: str) -> UserTagSet`
- `set_user_tags(user_id: str, tags: list[str]) -> UserTagSet`

### Manuelle Aufnahme
- `grant_manual_assignment(user_id: str, document_id: str, reason: str) -> ManualAssignment`
- `revoke_manual_assignment(manual_assignment_id: str) -> None`

### Befreiung
- `grant_exemption(user_id: str, document_id: str, version: int, reason: str, valid_until=None) -> TrainingExemption`
- `revoke_exemption(exemption_id: str) -> None`

### Kommentare
- `list_active_comments(...) -> list[TrainingCommentListItem]`
- `resolve_comment(comment_id: str, resolved_by: str, resolution_note: str | None = None) -> TrainingCommentRecord`
- `inactivate_comment(comment_id: str, inactive_by: str, inactive_note: str | None = None) -> TrainingCommentRecord`

### Reporting
- `get_training_statistics(...) -> TrainingStatistics`
- `list_training_audit_log(...) -> list[TrainingAuditLogItem]`

---

## 7. Bestehende Trainingsfunktionen, die entfernt oder ersetzt werden müssen

### Fachlich zu entfernen
Das Kategorienmodell ist im Zielzustand nicht mehr zulässig:
- `create_category(...)`
- `assign_document_to_category(...)`
- `assign_user_to_category(...)`

Die bisherigen Kategorie-Verträge und Tabellen sind zu entfernen bzw. zu migrieren.

### Zu ersetzen
- `sync_required_assignments()` -> ersetzen durch `rebuild_assignment_snapshots(...)`
- `list_matrix()` -> ersetzen durch `list_assignment_snapshots(...)`
- `import_quiz_questions(document_id, version, raw_questions_json)` -> ersetzen durch `import_quiz_json(raw_quiz_json)`

### Bisherige Nutzerlisten ersetzen
- `list_required_for_user(...)`
- `list_open_assignments_for_user(...)`
- `list_training_overview_for_user(...)`

werden ersetzt durch:
- `list_training_inbox_for_user(...)`

---

## 8. GUI-Vorgabe für die neue Trainingsansicht

Die bestehende `training_placeholder.py` ist nur ein Platzhalter und darf nicht einfach weiter aufgeblasen werden.

Es ist eine neue fachlich saubere Trainings-Workspace-Ansicht zu bauen, strukturell angelehnt an die Dokumentenlenkung.

## 8.1 Grundlayout
Die GUI ist **dreigeteilt**:

### Obere Leiste
- Admin-/QMB-Aktionsleiste
- nur sichtbar für Rollen `ADMIN` und `QMB`
- enthält:
  - `Import Quiz`
  - `Quiz zuordnen`
  - `Statistik / Logs`
  - `Kommentare`

Hinweis:
- Rollenprüfung an bestehende Rollennormalisierung anbinden.
- Sichtbarkeit an bestehende PyQt-Rollenlogik anbinden.

### Mittlerer Bereich
Nutzerabhängige Dokumentenliste.

Darzustellende Spalten:
- Dokumentenkennung
- Titel
- Status
- Owner
- Freigabe am
- Lesestatus

Datenquelle:
- materialisierte Trainings-Inbox
- nicht aus ad-hoc berechneter GUI-Logik

### Untere Leiste
Kontextbezogene Aktionsleiste für das selektierte Dokument.

Buttons:
- `Quiz starten`
- `Lesen` (nur falls noch nicht gelesen; Aktion läuft über Dokumentenmodul)
- `Quiz kommentieren` (erst sichtbar oder aktiv, wenn das Quiz mindestens einmal durchgeführt wurde)

## 8.2 Zusätzliche Kommentaransicht
Es ist eine zusätzliche Listenansicht für Kommentare erforderlich.

Darzustellende Spalten:
- Dokumentenkennung
- Titel
- Benutzer
- Datum
- Kommentartext
- Gelesen / Status

Diese Übersicht ist für QMB/Admin vorgesehen.

## 8.3 GUI-Regeln
- Die GUI berechnet keine Schulungspflicht.
- Die GUI setzt keine Kommentarstatus direkt per Datenbankzugriff.
- Die GUI arbeitet nur über öffentliche APIs.
- Die GUI darf keine Geschäftslogik aus dem Dokumentenmodul oder Trainingsmodul replizieren.
- Die GUI soll bestehende ActionBar-/Tabellenmuster des PyQt-Stacks wiederverwenden.

---

## 9. Verbindlicher Use Case je Aktion in der GUI

## 9.1 Dokumentliste laden
1. Benutzer wird über Usermanagement bestimmt.
2. GUI ruft `training_api.list_training_inbox_for_user(current_user_id, open_only=...)` auf.
3. GUI rendert nur die gelieferten materialisierten Zeilen.

## 9.2 Lesen
1. Benutzer selektiert ein Dokument.
2. GUI ruft **nicht** `training_api.confirm_read(...)` als Primärquelle auf.
3. GUI ruft `documents_read_api.open_released_document_for_training(...)` oder entsprechende dokumentmodulseitige Leseaktion auf.
4. Nach bestätigter Lesehandlung erzeugt das Dokumentenmodul einen Read-Receipt.
5. Das Trainingsmodul übernimmt diesen Receipt in den Trainingsfortschritt.
6. Die GUI lädt die Inbox neu.

## 9.3 Quiz starten
1. Benutzer selektiert ein Dokument.
2. GUI ruft `training_api.start_quiz(...)` auf.
3. Quiz ist nur erlaubt, wenn die Trainingssicht es zulässt.
4. GUI speichert keine Quizlogik lokal.

## 9.4 Quiz kommentieren
1. Benutzer darf erst kommentieren, wenn mindestens ein Quizversuch für das Dokument existiert.
2. GUI ruft `training_api.add_comment(...)` auf.
3. Kommentar wird im Trainingsmodul gespeichert und sofort auf `ACTIVE` gesetzt.

## 9.5 Kommentare bearbeiten (QMB/Admin)
1. QMB/Admin öffnet Kommentarübersicht.
2. GUI lädt nur aktive Kommentare über `training_admin_api.list_active_comments(...)`.
3. QMB/Admin markiert Kommentar als `RESOLVED` oder `INACTIVE`.
4. GUI ruft die entsprechende Admin-API auf.
5. Kommentare mit Status `RESOLVED` oder `INACTIVE` dürfen beim erneuten Auslesen **nicht** mehr in die aktive QMB-Liste übertragen werden.

---

## 10. Verbindliche Kommentarlogik

## 10.0 Verbindliche Testfälle für Kommentare
Mindestens abzudecken:
- Kommentar wird durch Benutzer erstellt und initial auf `ACTIVE` gesetzt
- aktive Kommentare erscheinen in der QMB/Admin-Kommentarliste
- `RESOLVED`-Kommentare erscheinen nicht mehr in der aktiven Liste
- `INACTIVE`-Kommentare erscheinen nicht mehr in der aktiven Liste
- Statuswechsel werden historisiert und per Event publiziert



Kommentare sind eine eigenständige fachliche Verantwortung des Schulungsmoduls.

### 10.1 Speicherung
Benutzerkommentare werden in einer eigenen Trainingstabelle gespeichert.

Ein Kommentar enthält mindestens:
- `comment_id`
- `document_id`
- `version`
- `document_title_snapshot`
- `user_id`
- `username_snapshot` oder `display_name_snapshot`
- `comment_text`
- `status`
- `created_at`
- `updated_at`
- `resolved_by` optional
- `resolved_at` optional
- `resolution_note` optional
- `inactive_by` optional
- `inactive_at` optional
- `inactive_note` optional

### 10.2 Statusmodell
Mindestens:
- `ACTIVE`
- `RESOLVED`
- `INACTIVE`

### 10.3 Initialstatus
- Beim Erstellen wird jeder Kommentar sofort auf `ACTIVE` gesetzt.

### 10.4 QMB-Übertragung
- Beim Auslesen für QMB/Admin werden ausschließlich aktive Kommentare geliefert.
- `RESOLVED` und `INACTIVE` werden aus der aktiven QMB-Kommentarliste ausgeschlossen.

### 10.5 Keine stillen Löschungen
- Kommentare werden nicht physisch verschwinden gelassen, sondern statusbasiert geführt.
- Audit-/Historienfähigkeit bleibt erhalten.

---

## 11. Verbindliche Ereignisarchitektur

## 11.0 Zusätzliche Event-Anforderungen für Quiz-Ersetzung und Export
Verbindlich zusätzlich:
- Bei erkanntem Ersetzungsfall muss ein fachlich nachvollziehbares Konflikt-/Prüfergebnis persistiert werden.
- Bei bestätigter Ersetzung muss ein eigenes Event publiziert werden.
- Exporte der Schulungsmatrix müssen auditierbar sein, mindestens über Log-/Audit-Eintrag.



Das Eventsystem muss bewusst und sparsam eingesetzt werden.

### 11.1 Grundregeln
- Events werden **nur nach erfolgreichem Commit** publiziert.
- Das Eventsystem ist für Modulkopplung, Audit und Projektion da.
- Das Eventsystem ist **nicht** die primäre UI-Wahrheitsquelle.
- Die GUI lädt nach Aktionen über APIs nach.
- Keine Business-Entscheidungen ausschließlich in Event-Handlern ohne persistierte Ergebnisobjekte.

### 11.2 Bestehende technische Basis
Es ist die vorhandene Event-Hülle und der vorhandene EventBus zu nutzen:
- `EventEnvelope`
- `event_bus.publish(...)`
- bei Bedarf `event_bus.subscribe(...)`

### 11.3 Verbindliche Event-Felder
Jedes Event muss den Envelope vollständig nutzen:
- `event_id`
- `name`
- `occurred_at_utc`
- `correlation_id`
- `causation_id` wenn vorhanden
- `actor_user_id`
- `module_id`
- `payload`
- `schema_version`

### 11.4 Verbindliche Dokumenten-Events
Neu im Dokumentenmodul einzuführen:
- `domain.documents.read.confirmed.v1`

Pflicht-Payload:
- `user_id`
- `document_id`
- `version`
- `confirmed_at`
- `source`

Optional:
- `read_receipt_id`

### 11.5 Verbindliche Trainings-Events
Mindestens erforderlich:
- `domain.training.quiz.replacement.detected.v1`
- `domain.training.quiz.replaced.v1`
- `domain.training.matrix.exported.v1`
- `domain.training.quiz.imported.v1`
- `domain.training.quiz.binding.created.v1`
- `domain.training.assignment.snapshot.rebuilt.v1`
- `domain.training.assignment.snapshot.created.v1`
- `domain.training.assignment.snapshot.updated.v1`
- `domain.training.comment.created.v1`
- `domain.training.comment.resolved.v1`
- `domain.training.comment.inactivated.v1`
- `domain.training.quiz.started.v1`
- `domain.training.quiz.completed.v1`
- `domain.training.exemption.granted.v1`
- `domain.training.exemption.revoked.v1`
- `domain.training.manual_assignment.granted.v1`
- `domain.training.manual_assignment.revoked.v1`

### 11.6 Event-Nutzung im Trainingsmodul
Verbindlich:
- Das Trainingsmodul darf `domain.documents.read.confirmed.v1` konsumieren, um Trainingsfortschritt zu aktualisieren.
- Diese Übernahme darf nur erfolgen, wenn der Dokumenten-Read-Receipt zum Benutzer, Dokument und zur Version passt.
- Die Trainingssicht wird danach persistiert und nicht nur im RAM verändert.

### 11.7 Event-Nutzung in der GUI
- GUI darf Businesszustände nicht aus Event-Payloads direkt zusammenbauen.
- GUI darf nach erfolgreicher Aktion refreshen.
- Falls GUI auf Events reagiert, dann nur als Refresh-Hinweis, nicht als fachliche Wahrheit.

---

## 12. Persistenz- und Vertragsmodell

## 12.1 Alte Verträge entfernen oder migrieren
Nicht mehr passend:
- `TrainingCategory`
- altes kategoriebezogenes `TrainingAssignment`

## 12.2 Neue Verträge im Trainingsmodul
Mindestens erforderlich:
- `TrainingAssignmentSnapshot`
- `TrainingProgress`
- `TrainingInboxItem`
- `TrainingDocumentRef`
- `QuizImportResult`
- `PendingQuizMapping`
- `QuizBinding`
- `DocumentTagSet`
- `UserTagSet`
- `ManualAssignment`
- `TrainingExemption`
- `TrainingCommentRecord`
- `TrainingCommentListItem`
- `TrainingStatistics`
- `TrainingAuditLogItem`

## 12.3 Persistenzbereiche
Mindestens getrennt modellieren:
- Dokument-Tags
- Benutzer-Tags
- manuelle Aufnahmen
- Befreiungen
- Quiz-Importe
- Quiz-Bindungen
- Assignment-Snapshots
- Trainingsfortschritt
- Kommentare
- Reporting-/Audit-Readmodel

---

## 13. Verbindliche GUI- und Rollenregeln

### 13.1 Rollen
- Top-Aktionsleiste nur für `ADMIN` und `QMB`
- Nutzeransicht für `ADMIN`, `QMB`, `USER`
- Rollenprüfung an bestehende Rollennormalisierung anbinden

### 13.2 Sichtbarkeit / Aktivierung
- `Import Quiz`, `Quiz zuordnen`, `Statistik/Logs`, `Kommentare` nur sichtbar für `ADMIN` / `QMB`
- `Lesen` nur aktiv, wenn Dokument in Inbox vorhanden und noch nicht bestätigt gelesen
- `Quiz starten` nur aktiv, wenn Trainingseintrag quizfähig ist
- `Quiz kommentieren` erst aktiv, wenn mindestens ein Quizversuch für das Dokument existiert

### 13.3 Tabelleninhalte
Nutzerliste zeigt mindestens:
- Dokumentenkennung
- Titel
- Status
- Owner
- Freigabe am
- Lesestatus

Kommentarliste zeigt mindestens:
- Dokumentenkennung
- Titel
- Benutzer
- Datum
- Kommentartext
- Gelesen / Status

---

## 14. Harte No-Go-Liste

Nicht zulässig sind:
- Kategorienmodell weiter ausbauen
- Schulungspflicht in der GUI berechnen
- `documents_pool_api` zu einer Schreib-API verbiegen
- Trainingsmodul direkt auf Released-Artefakte zugreifen lassen
- Lesen nur per Trainings-UI-Checkbox oder Seitenzähler behaupten
- Kommentarstatus per GUI ohne API ändern
- Kommentare physisch löschen, statt sauber zu statusführen
- Geschäftslogik in eine einzige `service.py` schieben
- Eventhandler als versteckte Hauptlogik missbrauchen

---

## 15. Konkrete Umsetzungsreihenfolge für den Developer

1. Öffentliche Ziel-APIs in `modules/training/api.py` und im Dokumentenmodul definieren.
2. Neues Read-Confirmation-API im Dokumentenmodul einführen.
3. Trainingsverträge neu schneiden.
4. Trainingspersistenz auf neue Tabellen/Repositories umstellen.
5. Kategorienmodell stilllegen bzw. migrieren.
6. Resolver + Snapshot-Projektion implementieren.
7. Quiz-Import und Quiz-Bindung implementieren.
8. Tag-Verwaltung implementieren.
9. Manuelle Aufnahme und Befreiung implementieren.
10. Kommentar-Statusmodell implementieren.
11. Events nach Commit publizieren.
12. Training-GUI als neue dreigeteilte Workspace-Ansicht aufbauen.
13. Tests für APIs, Resolver, Events, GUI-Aktivierungsregeln und Kommentarfilter ergänzen.

---

## 15.1 Verbindlicher Testkatalog

Die folgenden Tests sind **verpflichtend** und müssen automatisiert umgesetzt werden.

### A. Quiz-Import
1. **Import von Quiz im JSON-Format**
   - Ein Quiz im vorgegebenen JSON-Schema kann erfolgreich importiert werden.
   - `document_id` und `document_version` werden korrekt übernommen.
   - Fragen und Antworten werden korrekt persistiert.

2. **Schema-Validierung beim Import**
   - Import schlägt fehl, wenn Pflichtfelder fehlen.
   - Import schlägt fehl, wenn `correct_answer_id` auf keine Antwort verweist.
   - Import schlägt fehl, wenn Frage- oder Antwort-IDs nicht eindeutig sind.

### B. Dokument-Tags
3. **Setzen von Tags für ein Testdokument**
   - Für ein freigegebenes Testdokument können Tags gesetzt und wieder ausgelesen werden.

### C. Dokument-Quiz-Verknüpfung
4. **Verknüpfen von Dokument und Quiz**
   - Ein importiertes Quiz kann einer Dokumentenkennung korrekt zugeordnet werden.

5. **Ersetzen eines Quiz durch Import eines neuen Quiz**
   - Ein zweiter Import für dieselbe fachliche Bindung wird als Ersetzungsfall erkannt.
   - Das alte Quiz wird nicht stillschweigend überschrieben.

6. **Abfrage bei Ersetzen**
   - Vor Ersetzung ist eine explizite Bestätigung erforderlich.
   - Ohne Bestätigung bleibt das alte Quiz aktiv.
   - Mit Bestätigung wird das neue Quiz aktiv und das alte historisiert.

### D. Quiz-Nutzung
7. **User öffnet Quiz**
   - Ein Benutzer kann ein zulässiges Quiz starten.
   - Start wird protokolliert.

8. **User macht falsche Antworten -> Quiz failed**
   - Bei falschen Antworten wird das Ergebnis als nicht bestanden gespeichert.
   - Der Status der zugehörigen Schulung ist danach fachlich als `nicht bestanden` auswertbar.

9. **Historie für Quiz und Nutzer besteht**
   - Quizversuche bleiben historisch nachvollziehbar.
   - Es ist nachweisbar, welcher Benutzer wann welches Quiz mit welchem Ergebnis durchgeführt hat.
   - Historie bleibt auch nach Quiz-Ersetzung erhalten.

### E. Schulungsmatrix / Export
10. **Schulungsmatrix kann exportiert werden**
    - Der Export ist über öffentliche Admin-API auslösbar.
    - Exportergebnis wird protokolliert.

11. **Exportierte Schulungsmatrix ist nach Nutzer sortiert**
    - Der Export enthält nach Benutzer sortiert:
      - zugewiesene Dokumente
      - bestanden
      - nicht bestanden
      - offen

### F. Leselogik in Verbindung mit Dokumentenmodul
12. **Lesen wird dokumentmodulseitig bestätigt**
    - Ein Benutzer kann den Trainingsstatus `gelesen` nicht ohne dokumentmodulseitigen Read-Receipt erhalten.

### G. Kommentare
13. **Kommentar initial aktiv**
    - Neu angelegte Kommentare sind `ACTIVE`.

14. **Resolved/Inactive werden nicht erneut übertragen**
    - In der aktiven Kommentarübersicht erscheinen nur `ACTIVE`-Kommentare.

### H. Events
15. **Events werden nach Commit publiziert**
    - Import, Binding, Ersetzung, Quizstart, Quizabschluss, Kommentarstatus und Export publizieren Events erst nach erfolgreicher Persistenz.

---

## 15.2 Empfohlene Teststruktur

Mindestens getrennt in:
- `tests/training/test_quiz_import_service.py`
- `tests/training/test_document_tag_service.py`
- `tests/training/test_quiz_binding_service.py`
- `tests/training/test_quiz_replacement_flow.py`
- `tests/training/test_quiz_execution_service.py`
- `tests/training/test_training_history.py`
- `tests/training/test_training_matrix_export.py`
- `tests/training/test_training_comment_service.py`
- `tests/training/test_training_events.py`
- `tests/training/test_training_gui_permissions.py`

Die Testtrennung muss die fachlichen Verantwortlichkeiten widerspiegeln. Keine große Sammel-Testdatei.

---

## 16. Minimale Abnahmekriterien

Die Umsetzung ist nur dann fachlich akzeptiert, wenn mindestens Folgendes erfüllt ist:
- Nur freigegebene Dokumente können trainingsrelevant werden.
- Schulungspflicht wird aus Scope / Tags / manueller Aufnahme / Befreiung korrekt materialisiert.
- Negative Tags existieren nicht.
- Befreiungen sind versionsbezogen führbar.
- Quiz-Import kann per JSON automatisch zuordnen.
- Nicht zuordenbare Quizimporte landen in manueller Zuordnung.
- Die GUI zeigt die dreigeteilte Ansicht.
- Top-Leiste ist nur für `ADMIN` und `QMB` sichtbar.
- `Lesen` wird dokumentmodulseitig bestätigt.
- Kommentare werden mit `ACTIVE` angelegt.
- `RESOLVED` und `INACTIVE` tauchen in aktiver Kommentarübersicht nicht mehr auf.
- Events werden nach Commit mit sauberem Envelope publiziert.
- Es gibt keine God-File-Implementierung.
- Öffentliche APIs bleiben in `api.py`.

---

## 17. Ergebnisformel für den Developer

Der Developer soll **kein kleines Feature in die bestehende Placeholder-Logik hineinpatchen**, sondern das Schulungsmodul entlang klarer Verantwortlichkeiten neu schneiden.

Die Leitlinie lautet:
- Dokumentenmodul liefert freigegebene Dokumentfakten und dokumentmodulseitige Lesebestätigung.
- Usermanagement liefert Benutzerfakten.
- Schulungsmodul verantwortet Zuweisung, Quiz, Tags, Overrides, Kommentare und materialisierte Trainingssicht.
- GUI liest nur saubere öffentliche APIs.
- Events koppeln Module und Audit, ersetzen aber nicht die persistierte Fachwahrheit.

