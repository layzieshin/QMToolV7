# AP-008 Service-Actor-Parameter-Matrix

## Status
- Arbeitspaket: AP-008
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Migration: nein

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` auf `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md` zur Existenzprüfung.
  - `ReadFile` für `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`, `docs/AP-004_USER_CONTEXT_ADR.md`, `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`, `docs/AP-006_AUDIT_ACTOR_ADR.md`, `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`, `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`, `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md` und `.cursor/rules/00-agent-workflow.mdc`.
  - `rg` in `modules/*` nach Service-/Use-Case-Definitionen, `actor_user_id`, `actor_role`, `get_current_user()`, `EventEnvelope.create`, `emit_audit`, `_emit_audit`, `audit_logger.emit`, `actor=`, `"system"` und `"unknown"`.
  - `rg` in `qm_platform/*` nach `EventEnvelope.create`, `AuditLogger.emit`, `LogBackupService.create_backup`, `actor_user_id`, `correlation_id` und `causation_id`.
  - `rg` in `interfaces/*` nach Adapter-Actor-Weitergabe und Anzeige-/Legacy-Fällen, nur zur Einordnung der Service-Grenzen.
  - `ReadFile` gezielter Hotspots in Usermanagement, Documents, Incident/CAPA, Training, Logging und Events.
- Geprüfte Bereiche:
  - `modules/usermanagement/*`
  - `modules/documents/*`
  - `modules/incident_management/*`
  - `modules/training/*`
  - `qm_platform/logging/*`
  - `qm_platform/events/*`
  - `interfaces/cli/*`
  - `interfaces/pyqt/*`
  - `tests/*`
  - freigegebene ADR-/Roadmap-/Regeldateien
- Ausgeschlossene Bereiche:
  - Keine absichtlich ausgeschlossenen Bereiche innerhalb des freigegebenen Scopes.
  - Phase-2-Module wurden nicht vorgezogen.
  - `modules/signature/*` wurde in den Suchtreffern gesehen, aber nicht vertieft, weil AP-008 auf MVP-Audit-Actor-Use-Cases aus AP-007 fokussiert.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Gesamtzahl relevanter Service-/Use-Case-Fundstellen: 37
- Anzahl Kategorie A: 13
- Anzahl Kategorie B: 7
- Anzahl Kategorie C: 8
- Anzahl Kategorie D: 10
- Anzahl Kategorie E: 6
- Anzahl Kategorie F: 8

Hinweis: Die Kategorien zählen Matrixzeilen, nicht disjunkte Codezeilen. Eine Service-Funktion kann z. B. zugleich einen expliziten Parameter haben und wegen Fallback oder unklarer Quelle in Kategorie F erscheinen.

## Kategorie A — Explizite Actor/User-Parameter

| Datei | Zeile | Funktion/Methode | Parameter | Actor-/User-Quelle | Nachweisstatus | MVP-Bereich |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 58 | `assign_workflow_roles` | `actor_user_id`, `actor_role` | optionaler Service-Parameter | eingeschränkt | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 107 | `start_workflow` | `actor_user_id`, `actor_role` | optionaler Service-Parameter | eingeschränkt | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 154 | `complete_editing` | `actor_user_id`, `actor_role` | optionaler Service-Parameter | eingeschränkt | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 205 | `accept_review` | `actor_user_id`, optional `actor_role` | verpflichtender Reviewer-Parameter | belastbar nach Quellklassifikation | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 280 | `accept_approval` | `actor_user_id`, optional `actor_role` | verpflichtender Approver-Parameter | belastbar nach Quellklassifikation | Dokumentenlenkung |
| `modules/documents/workflow_use_cases.py` | 446 | `extend_annual_validity` | `actor_user_id` | verpflichtender nicht-leerer Service-Parameter | belastbar nach Quellklassifikation | Dokumentenlenkung |
| `modules/documents/comment_service.py` | 73 | `create_pdf_comment` | `actor_user_id`, `actor_role` | expliziter Kommentar-Actor und Rolle | eingeschränkt | Dokumentenlenkung |
| `modules/documents/comment_service.py` | 121 | `set_status` | `actor_user_id` | expliziter Status-Actor | eingeschränkt | Dokumentenlenkung |
| `modules/training/manual_assignment_service.py` | 23 | `grant_manual_assignment` | `granted_by` | expliziter ausführender User; Zieluser separat `user_id` | belastbar nach Quellklassifikation | Schulung, Kompetenz & Befugnisse |
| `modules/training/exemption_service.py` | 29 | `grant_exemption` | `granted_by` | expliziter ausführender User; Zieluser separat `user_id` | belastbar nach Quellklassifikation | Schulung, Kompetenz & Befugnisse |
| `modules/training/training_comment_service.py` | 104 | `resolve_comment` | `resolved_by` | expliziter Bearbeiter | belastbar nach Quellklassifikation | Schulung, Kompetenz & Befugnisse |
| `modules/incident_management/incident_ops.py` | 27 | `submit_incident` | `user` | Ops-Parameter, von Facade aktuell implizit geliefert | eingeschränkt | Fehler / Abweichungen / CAPA light |
| `modules/incident_management/action_ops.py` | 29 | `create_action` / `complete_action` | `user` | Ops-Parameter, von Facade aktuell implizit geliefert | eingeschränkt | Aufgaben- und Fristenmanagement / CAPA light |

## Kategorie B — Implizite Actor/User-Quellen

| Datei | Zeile | Funktion/Methode | implizite Quelle | Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- |
| `modules/incident_management/service.py` | 53 | `_user` | `usermanagement_service.get_current_user()` | Alle Incident/CAPA-Ops erhalten User aus lokaler Current-User-Quelle statt explizitem Kontext. | Use-Case-Grenze für UserContext/RequestContext klassifizieren. |
| `modules/training/api.py` | 143 | `_require_admin_or_qmb` | `self._um.get_current_user()` | Training-Admin- und Berichtsfunktionen ziehen User/Rolle implizit. | Training-Admin-Flows als eingeschränkt markieren. |
| `modules/usermanagement/auth_ops.py` | 72 | `logout` | `self._session.get_current_user()` | Logout-Actor hängt von lokaler Sessiondatei ab. | Session-/Logout-Actor später trennen. |
| `modules/documents/workflow_use_cases.py` | 95 | `assign_workflow_roles` | `actor_user_id or updated.owner_user_id or "system"` | Owner/System-Fallback kann ausführenden Actor ersetzen. | Actor-Pflicht/Fallback-Policy für Workflow-Rollen klären. |
| `modules/documents/workflow_use_cases.py` | 142 | `start_workflow` | `actor_user_id or updated.owner_user_id or "system"` | Workflow-Start kann ohne expliziten Actor auditierbar wirken. | Documents-Actor-Matrix verfeinern. |
| `modules/documents/workflow_use_cases.py` | 435 | `archive_approved` | `actor_user_id or "system"` | Fachliche Archivierung kann als `system` erscheinen. | System-Actor-Policy und Actor-Pflicht entscheiden. |
| `qm_platform/logging/log_backup_service.py` | 34 | `create_backup` | Default `actor="system"` | System Actor kann berechtigt sein, ist aber ohne Job-/Request-Kontext unklar. | System-/Service-Actor-Regel für Backups festlegen. |

## Kategorie C — Auditrelevante Events ohne belastbaren Actor

| Datei | Zeile | Event-/Audit-Call | aktueller Actor-Status | Risiko für MVP-Audit-Export | Blocker: ja/nein/offen |
| --- | ---: | --- | --- | --- | --- |
| `modules/usermanagement/auth_ops.py` | 37 | `domain.usermanagement.auth.failed.v1` | kein Actor, nur Username im Payload | Fehlversuche haben keinen belastbaren Actor; kann für Security-/Audit-Kontext relevant sein. | offen |
| `modules/usermanagement/user_admin_ops.py` | 51 | `domain.usermanagement.user.created.v1` | Zieluser als `actor_user_id` | Adminanlage kann als Handlung des angelegten Users erscheinen. | ja |
| `modules/usermanagement/user_admin_ops.py` | 164 | `domain.usermanagement.user.qmb_flag.changed.v1` | geänderter User als `actor_user_id` | QMB-/Rollenänderung verfälscht ausführenden Actor. | ja |
| `modules/usermanagement/user_admin_ops.py` | 225 | `domain.usermanagement.user.password_changed.v1` | Zieluser oder `None` | Passwortänderung trennt ausführenden User nicht sicher. | offen |
| `modules/documents/pdf_read_tracking_service.py` | 41 | `domain.documents.read.session.started.v1` | kein Actor im Event | Read-Session-Start ist für Kenntnisnahme nicht actor-belastbar. | ja |
| `modules/documents/pdf_read_tracking_service.py` | 91 | `domain.documents.read.session.completed.v1` | kein Actor im Event; Receipt enthält `session.user_id` | Lesebestätigung kann im Event nicht direkt als ausführender Actor nachgewiesen werden. | ja |
| `modules/documents/comment_service.py` | 147 | `EventEnvelope.create(... payload=payload)` | Actor-Parameter wird nicht an Envelope übergeben | Kommentarereignisse haben trotz Service-Actor keinen Event-Actor. | offen/ja |
| `modules/training/quiz_import_service.py` | 200 | `EventEnvelope.create(name=name, module_id="training", payload=payload)` | kein Actor | Quiz-Import ist adminrelevant, aber Event ohne Actor. | offen |

## Kategorie D — Späterer Parameter-/Kontextbedarf

| Use Case | Service/Funktion | benötigt UserContext | benötigt RequestContext | benötigt AuditActor | System Actor ausreichend | offene Entscheidung |
| --- | --- | --- | --- | --- | --- | --- |
| Documents Review/Approval | `DocumentsWorkflowUseCases.accept_review` / `accept_approval` | ja | ja, empfohlen | ja | nein | Quelle des heutigen `actor_user_id` aus CLI/PyQt muss als belastbar klassifiziert werden. |
| Documents Workflow Start/Rollen/Abort | `assign_workflow_roles`, `start_workflow`, `abort_workflow` | ja | ja | ja | nein | Owner-/System-Fallback zulässig oder legacy? |
| Documents Archivierung | `archive_approved` | ja | ja | ja | nein/offen | Darf `system` archivieren, oder immer menschlicher QMB/Admin? |
| Documents Read Receipt | `PdfReadTrackingService.start` / `finalize` | ja | ja | ja | nein | Receipt-User vs. ausführender Actor im Event trennen. |
| Documents Workflow-Kommentare | `WorkflowCommentService.create_pdf_comment` / `set_status` | ja | ja | ja | nein | Actor in EventEnvelope nachziehen oder im Export über Record ableiten? |
| Usermanagement Adminaktionen | `create_user`, `set_user_qmb`, `change_password` | ja | ja | ja | nein/offen | Selbstregistrierung, Adminanlage, Bootstrap und Passwortänderung unterscheiden. |
| Incident/CAPA | `IncidentManagementService` -> `*_ops(user=...)` | ja | ja | ja | nein | Facade zieht aktuell `_user()` implizit; Service-Grenze festlegen. |
| Training Admin/Tags/Quiz | `TrainingApi._require_admin_or_qmb` und delegierte Adminfunktionen | ja | ja | ja/offen | nein | Admin/QMB-Gate und Actor-Quelle trennen. |
| Training manuelle Zuweisung/Ausnahme | `ManualAssignmentService`, `ExemptionService` | ja | ja | ja | nein | `granted_by`/`revoked_by` Quelle bestätigen. |
| Log Backup | `LogBackupService.create_backup` | nein/offen | ja/offen | ja, System/Service Actor | ja, wenn systeminitiiert | Backup-Actor-Regel und Benennung festlegen. |

## Kategorie E — Nicht auditrelevant oder nur Anzeige
- `interfaces/pyqt/contributions/audit_logs_view.py`: Anzeige, Filter und Backup-Button-Sichtbarkeit; `get_current_user()` an Zeile 81 ist hier primär UI-/Sichtbarkeitskontext und keine fachliche Actor-Bestimmung.
- `qm_platform/logging/log_query_service.py`: Query-/Export-Hilfen für vorhandene Audit-/Log-Zeilen; keine Erzeugung eines fachlichen Audit Actors.
- `modules/usermanagement/contracts.py` und vergleichbare `contracts.py`-DTOs: Datenmodelle ohne Event-Erzeugung, keine Actor-Bestimmung.
- `modules/*/repository.py`: Persistenz von Actor-/User-Feldern, aber keine fachliche Actor-Entscheidung; Repository-Grenze bleibt technisch.
- `modules/documents/comment_extractors/docx_comment_reader.py`: DOCX-Autor bzw. `unknown` ist Import-/Quellmetadatum, nicht automatisch Audit Actor.
- `tests/*`: Fake-User, Actor-Strings und Rollenmatrizen sind Test-/Fixture-Funde; nicht automatisch produktive Actor-Quellen.

## Kategorie F — Supervisor-Entscheidung nötig

| Datei | Zeile | Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | ---: | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 95 | `actor_user_id or updated.owner_user_id or "system"` | Mehrere mögliche Actor-Quellen an einer Service-Grenze. | Owner-Fallback verbieten, erlauben oder als legacy/eingeschränkt markieren. |
| `modules/documents/workflow_use_cases.py` | 407 | `actor_user_id: str | None = None` bei `archive_approved` | Archivierung erlaubt Actor-freien Aufruf mit späterem `system`-Fallback. | Archivierung immer menschlicher Actor oder erlaubter System Actor? |
| `modules/usermanagement/user_admin_ops.py` | 51 | `actor_user_id=user.user_id` | Zieluser-vs-ausführender-User bei Adminanlage/Selbstregistrierung. | Usermanagement-Actor/Target-Regel pro Use Case. |
| `modules/usermanagement/user_admin_ops.py` | 255 | `ensure_admin_credentials` delegiert auf `create_user` / `change_password` | Bootstrap/Seed kann technisch oder menschlich ausgelöst sein. | Bootstrap als System/Service Actor oder Admin Actor klassifizieren. |
| `modules/incident_management/service.py` | 53 | `_user()` | Service-Facade ist fachliche Grenze, zieht aber implizit lokalen User. | Spätere Grenze für expliziten UserContext/RequestContext. |
| `modules/training/api.py` | 199 | `replace_quiz_binding(... confirmed_by: str)` | `confirmed_by` wird delegiert, aber Quellqualität ist nicht im API-Gate erkennbar. | Training-Admin-Actor-Quelle und Auditrelevanz von Quiz-Bindings klären. |
| `qm_platform/events/event_envelope.py` | 35 | `correlation_id=correlation_id or str(uuid4())` | Correlation wird erzeugt, aber nicht durch Service-/Request-Kontext durchgereicht. | Pflichtgrad von Correlation/Causation für MVP-Audit-Export. |
| `qm_platform/logging/log_backup_service.py` | 34 | `actor: str = "system"` | Systemaktion vs. userinitiierter Backup-Aufruf unklar. | System-Actor-Namensschema und Service-Account-Policy. |

## Kritischste Service-Gaps
1. `modules/incident_management/service.py:53`: Incident/CAPA-Facade zieht Actor/User implizit aus `get_current_user()`; das betrifft viele CAPA-light-Use-Cases.
2. `modules/usermanagement/user_admin_ops.py:51`: Useranlage hat keinen ausführenden Actor-Parameter und nutzt Zieluser als Actor.
3. `modules/usermanagement/user_admin_ops.py:164`: QMB-Flag-Änderung hat keinen ausführenden Actor-Parameter und nutzt den geänderten User.
4. `modules/documents/pdf_read_tracking_service.py:41`: Read-Session-Start erzeugt ein Event ohne Actor; kritisch für Kenntnisnahme.
5. `modules/documents/pdf_read_tracking_service.py:91`: Read-Session-Abschluss/Receipt erzeugt ein Event ohne Actor; kritisch für Nachweispakete.
6. `modules/documents/workflow_use_cases.py:95`: Documents-Rollenvergabe hat optionale Actor-Parameter und Owner-/System-Fallbacks.
7. `modules/documents/comment_service.py:147`: Kommentar-Service nimmt Actor entgegen, übergibt ihn aber nicht an das Event.
8. `modules/training/api.py:143`: Training-Admin-Facade zieht Current User implizit und vermischt Gate/Quelle.
9. `qm_platform/logging/audit_logger.py:15`: Plattform-AuditLogger schreibt freie Actor-Strings ohne Quellenstatus.
10. `qm_platform/events/event_envelope.py:27`: `actor_user_id` ist optional, Correlation/Causation werden nicht aus einem expliziten RequestContext erzwungen.

## Vorschlag für spätere Paketierung

| Paketname | Ziel | Scope | Risiko | erforderliche Vorentscheidung |
| --- | --- | --- | --- | --- |
| Documents-Service-Actor-Matrix vertiefen | Documents-Workflow, Read-Receipt und Kommentare pro Use Case auf Actor/Target/Event-Felder herunterbrechen. | Nur `modules/documents/*` als Analysepaket. | niedrig bis mittel; keine Umsetzung. | Owner-/System-Fallback-Entscheidung und Nachweisstatus-Vokabular. |
| Usermanagement-Actor-Target-Policy | Useranlage, Selbstregistrierung, QMB-Flag, Passwort und Bootstrap fachlich trennen. | Nur Usermanagement-Use-Cases als ADR/Analyse. | mittel, weil spätere Auth-/Adminflows betroffen sind. | Actor/Target-Regel für Adminaktionen und Bootstrap/System Actor. |
| Incident-Context-Grenzen-Inventar | Incident/CAPA-Facade und Ops-Funktionen nach UserContext/RequestContext/AuditActor-Bedarf gruppieren. | Nur `modules/incident_management/*` als Analysepaket. | mittel, wegen vieler betroffener Use Cases. | Explizite UserContext-Grenze und Admin/QMB-Semantik. |

Keines dieser Pakete ist mit AP-008 gestartet.

## Auswirkungen auf Audit-Export / Nachweispaket
- Tragfähig wirken:
  - Documents-Review/Approval und Gültigkeitsverlängerung haben bereits explizite Actor-Parameter und service-nahe Prüfungen.
  - Training Manual Assignment und Exemption trennen Zieluser und `granted_by`/`revoked_by` grundsätzlich.
  - Incident-Ops verwenden intern konsistent `auth.user_id(user)`, wenn ein belastbarer `user` ankommt.
- Eingeschränkt bleiben:
  - Die Quelle vieler heutiger Service-Parameter ist CLI-/PyQt-/Facade-Current-User und damit nur eingeschränkt belastbar.
  - Documents-Fallbacks auf Owner/`system` und optionale Actor-Parameter.
  - Usermanagement-Adminaktionen ohne ausführenden Actor.
  - Training-Admin-Facade mit implizitem `get_current_user()`.
  - AuditLogger/EventEnvelope ohne zentrale Quellenvalidierung und ohne verpflichtenden RequestContext.
- Vor belastbarem MVP-Audit-Export zu adressieren:
  - Actor/Target-Trennung für Usermanagement.
  - Read-Receipt-/Read-Session-Actor an Service-/Event-Grenze.
  - Incident/CAPA-Facade-Grenze weg von implizitem Current User.
  - Documents-Owner-/System-Fallback-Policy.
  - Exportkennzeichnung von `belastbar/eingeschränkt/legacy` und Correlation/Causation-Pflichtgrad.

## Ausgeführte Gates
- Such-/Analysekommandos:
  - `Glob` Existenzprüfung für `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md` -> Datei existierte nicht.
  - `ReadFile` der freigegebenen ADR-/Roadmap-/Regeldateien -> erfolgreich.
  - `rg`-Suchen in `modules/*`, `qm_platform/*` und `interfaces/*` nach Service-/Actor-/Eventmustern -> erfolgreich.
  - `ReadFile` zentraler Service-/Use-Case-Hotspots -> erfolgreich.
- Ergebnis:
  - Service-Actor-Parameter-Matrix erstellt.
  - Keine Testsuite ausgeführt, weil AP-008 ein Analyse-/Inventarpaket ist.
  - Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein rein analytisches Paket `Documents-Service-Actor-Matrix vertiefen` freigegeben wird; keine Implementierung automatisch starten.
