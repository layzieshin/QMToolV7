# Track B Change Specification

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

Diese Spezifikation beschreibt den separaten Folge-Track für Backend/Runtime nach dem GUI-Track.

## Status (Ist gegen Ziel)

| Bereich | Status | Hinweis |
| --- | --- | --- |
| B1 Usermodell-Erweiterung | teilweise | Felder + Service/Repository-Pfade umgesetzt; Folgearbeit: erweiterte Admin-Freigabeprozesse |
| B2 Dokumente-Readmodels | umgesetzt | Tasks/Review/Recent/CurrentReleased als API/Service verfügbar, Dashboard/Dokumente umgestellt |
| B3 Training-Readmodels | umgesetzt | OpenAssignments/Overview/QuizCapable-Listen in API/Service + GUI-Anbindung umgesetzt |
| B4 Log Query Service | umgesetzt | Query-Service in Audit & Logs produktiv genutzt, tabellarische Filter + CSV/PDF-Export in GUI aktiviert |
| B5 Runtime/Lizenz-Robustheit | teilweise | non-strict PyQt Runtime-Start + GUI-Deaktivierungen aktiv; persistenter Admin/Debug-Toggle ergänzt |

## Ziel

- GUI-Readmodel-Lücken schließen, ohne Business-Regeln in die GUI zu verschieben.
- Runtime gegen Lizenzprobleme robuster machen.
- Audit/Logs über Query-Service statt GUI-Dateiparsing bereitstellen.

## B1 Usermodell-Erweiterung

- Dateien:
  - `modules/usermanagement/contracts.py`
  - `modules/usermanagement/service.py`
  - `modules/usermanagement/sqlite_repository.py`
  - `modules/usermanagement/schema.sql`
- Neue Felder:
  - `display_name`
  - `email`
  - `department`
  - `scope`
  - `organization_unit`
  - `is_active`
- API-Verträge:
  - Lesen: `get_current_user`, `list_users` liefern die neuen Felder mit.
  - Schreiben: `update_user_profile`, `update_user_admin_fields`, `set_user_active`.

## B2 Dokumente-Readmodels

- Dateien:
  - `modules/documents/api.py`
  - `modules/documents/service.py`
- Neue Readmodel-Methoden:
  - `list_tasks_for_user(user_id, role, scope=None)`
  - `list_review_actions_for_user(user_id, role)`
  - `list_recent_documents_for_user(user_id, role)`
  - `list_current_released_documents()`
- DTOs:
  - `DocumentTaskItem`
  - `ReviewActionItem`
  - `RecentDocumentItem`
  - `ReleasedDocumentItem`

## B3 Training-Readmodels

- Dateien:
  - `modules/training/api.py`
  - `modules/training/service.py`
  - `modules/training/contracts.py`
- Neue Readmodel-Methoden:
  - `list_open_assignments_for_user(user_id)`
  - `list_training_overview_for_user(user_id)`
  - `list_quiz_capable_approved_documents()`

## B4 Log Query Service

- Neue Datei:
  - `qm_platform/logging/log_query_service.py`
- Integration:
  - Registrierung in Runtime-Bootstrap.
  - `audit_logs_view` ruft Query-Methoden statt Datei-Tail auf.
- Methoden:
  - `query_audit(...)`
  - `query_technical_logs(...)`
  - `export_audit_csv(...)`
  - `export_audit_pdf(...)`
  - `export_logs_csv(...)`
  - `export_logs_pdf(...)`

## B5 Runtime/Lizenz-Robustheit

- Dateien:
  - `qm_platform/runtime/lifecycle.py`
  - `interfaces/pyqt/runtime/host.py`
- Verhalten:
  - Fehlende Modullizenz führt zu sauberer Deaktivierung statt Hard-Fail.
  - Abhängige Module werden als blocked markiert.
  - GUI erhält Status, aber entscheidet nicht über Runtime-Regeln.

## Akzeptanzkriterien

- Alle neuen Readmodel-Methoden sind über bestehende Serviceports erreichbar.
- Keine GUI parst technische Logdateien direkt für Fachsichten.
- Fehlende Lizenz stürzt die App nicht ab.
- Tests für neue Contracts/Servicepfade vorhanden.
