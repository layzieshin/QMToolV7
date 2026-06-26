# AP-011 Documents-Event-Actor-Matrix

## Status
- Arbeitspaket: AP-011
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Event-Schema-Änderungen: nein
- Migration: nein

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` auf `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` zur Existenzprüfung.
  - `ReadFile` für `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`, `docs/AP-004_USER_CONTEXT_ADR.md`, `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`, `docs/AP-006_AUDIT_ACTOR_ADR.md`, `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`, `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`, `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md`, `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`, `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`, `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md` und `.cursor/rules/00-agent-workflow.mdc`.
  - `rg` in `modules/documents/*` nach `EventEnvelope.create`, `publish_event`, `_publish`, `_emit_audit`, `emit_audit`, `domain.documents`, `actor_user_id`, `correlation_id`, `causation_id`, `"system"` und `"unknown"`.
  - `rg` in `modules/signature/*` nach `EventEnvelope.create`, `domain.signature`, `audit_logger.emit`, `actor=`, `signer_user`, `actor_user_id`, `correlation_id` und `causation_id`.
  - `rg` in `interfaces/cli/commands/documents_commands.py` und `interfaces/pyqt/*` nach Documents-Actor-Weitergabe, Signaturkontext, Read-Tracking und Adapterzustand.
  - `rg` in `tests/*` nach Documents-Event-/Actor-/Read-Receipt-Testfällen.
  - `ReadFile` zentraler Hotspots in `modules/documents/service.py`, `workflow_use_cases.py`, `pdf_read_tracking_service.py`, `comment_service.py`, `comment_sync_service.py`, `eventing.py`, `module.py`, `modules/signature/signature_execute_ops.py`, `modules/signature/service.py` und `tests/modules/test_documents_event_contracts.py`.
- Geprüfte Bereiche:
  - `modules/documents/*`
  - `modules/signature/*` nur zur Documents-nahen Signatur-/Audit-Abgrenzung
  - `interfaces/cli/commands/documents_commands.py`
  - `interfaces/pyqt/*documents*`
  - `interfaces/pyqt/**/documents*`
  - `tests/*documents*`
  - `tests/**/documents*`
  - freigegebene ADR-/Inventar-/Roadmap-/Regeldateien
- Ausgeschlossene Bereiche:
  - Keine absichtlich ausgeschlossenen Documents-Bereiche innerhalb des freigegebenen Scopes.
  - `modules/signature/*` wurde nicht als vollständiges Signatur-Inventar bewertet; nur Documents-nahe Signatur-Events und Signatur-Actor-Abgrenzung wurden eingeordnet.
  - Nicht-Documents-Module außerhalb der freigegebenen Vorarbeiten wurden nicht vertieft.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Gesamtzahl relevanter Documents-Event-Fundstellen: 30
- Anzahl Kategorie A: 6
- Anzahl Kategorie B: 11
- Anzahl Kategorie C: 6
- Anzahl Kategorie D: 8
- Anzahl Kategorie E: 8
- Anzahl Kategorie F: 9

Hinweis: Kategorie-Zahlen zählen Matrixzeilen. Einzelne Eventstellen erscheinen bewusst in mehreren Kategorien, wenn sie z. B. einen Event-Actor enthalten, aber zusätzlich eingeschränkte Quellqualität oder fehlende Correlation/Causation haben.

## Kategorie A — Events mit belastbarer Actor-Quelle

| Datei | Zeile | Event/Event-Call | Actor-Feld | Actor-Quelle | Nachweisstatus | Documents-Flow |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 226 | `domain.documents.review.accepted.v1` | Envelope `actor_user_id`, Payload `actor_user_id`, Audit `actor` | verpflichtender Reviewer-Parameter; Service prüft Reviewer-Zuordnung | belastbar nach Quellklassifikation | Review annehmen |
| `modules/documents/workflow_use_cases.py` | 259 | `domain.documents.review.rejected.v1` | Envelope `actor_user_id`, Payload `actor_user_id`, Audit `actor` | verpflichtender Reviewer-Parameter; Service prüft Reviewer-Zuordnung | belastbar nach Quellklassifikation | Review ablehnen |
| `modules/documents/workflow_use_cases.py` | 315 | `domain.documents.approval.accepted.v1` | Envelope `actor_user_id`, Payload `actor_user_id`, Audit `actor` | verpflichtender Approver-Parameter; Service prüft Approver-Zuordnung und Four-Eyes-Regel | belastbar nach Quellklassifikation | Approval/Freigabe annehmen |
| `modules/documents/workflow_use_cases.py` | 353 | `domain.documents.approval.rejected.v1` | Envelope `actor_user_id`, Payload `actor_user_id`, Audit `actor` | verpflichtender Approver-Parameter; Service prüft Approver-Zuordnung | belastbar nach Quellklassifikation | Approval/Freigabe ablehnen |
| `modules/documents/workflow_use_cases.py` | 484 | `domain.documents.validity.extended.v1` | Envelope `actor_user_id`, Payload `actor_user_id`, Audit `actor` | verpflichtender nicht-leerer Actor-Parameter; Service validiert Signatur- und Jahresreview-Bedingungen | belastbar nach Quellklassifikation | Gültigkeit verlängern |
| `modules/documents/service.py` | 568 | `domain.documents.change_request.added.v1` | Envelope `actor_user_id` | verpflichtender Actor-Parameter; Service prüft Owner/QMB/Admin-Recht | belastbar nach Quellklassifikation | Change Request / Nachweisexport-nahes Metadatum |

## Kategorie B — Events mit eingeschränkter Actor-Quelle

| Datei | Zeile | Event/Event-Call | eingeschränkte Quelle | Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- |
| `modules/documents/service.py` | 629/658 | `domain.documents.artifact.imported.v1` bei PDF-/DOCX-Import | `actor_user_id` ist verpflichtender Service-Parameter, Quelle aktuell CLI/PyQt/Adapter | Explizites Feld vorhanden, aber ohne freigegebenen UserContext/RequestContext nur eingeschränkt belastbar. | Actor-Quelle je Import-Use-Case klassifizieren. |
| `modules/documents/service.py` | 690 | `domain.documents.template.created.v1` | `actor_user_id` ist verpflichtender Service-Parameter, Quelle aktuell Adapter | Template-Erstellung wirkt actor-belastbar, Quelle ist aber noch nicht freigegeben. | Später an UserContext/RequestContext anbinden oder als eingeschränkt markieren. |
| `modules/documents/service.py` | 514 | `domain.documents.metadata.updated.v1` | `actor_user_id` und `actor_role` sind verpflichtend, aber Quelle ist nicht zentral validiert | Event-Actor vorhanden; Export muss Quellstatus und Rollen-/Actor-Trennung sichtbar halten. | Documents-Metadata-Use-Case in Service-Actor-Matrix absichern. |
| `modules/documents/workflow_use_cases.py` | 80 | `domain.documents.assignments.updated.v1` | optionaler `actor_user_id`; Audit-Fallback auf Owner/`system` | Rollenvergabe kann ohne ausführenden Actor auditierbar wirken. | Actor-Pflicht/Fallback-Policy für Workflow-Rollen entscheiden. |
| `modules/documents/workflow_use_cases.py` | 131 | `domain.documents.workflow.started.v1` | optionaler `actor_user_id`; Audit-Fallback auf Owner/`system` | Workflow-Start kann interaktive Aktion ohne belastbaren Actor darstellen. | Actor-Pflicht für Workflow-Start entscheiden. |
| `modules/documents/workflow_use_cases.py` | 182 | `domain.documents.editing.completed.v1` | optionaler `actor_user_id`; Audit-Fallback auf Owner/`system`; signaturnah | Editing-Abschluss kann fachlich und signaturnah sein, ohne eindeutigen ausführenden Actor. | Editing-/Signatur-Actor-Grenze klären. |
| `modules/documents/workflow_use_cases.py` | 385 | `domain.documents.workflow.aborted.v1` | optionaler `actor_user_id`; Audit-Fallback auf Owner/`system` | Workflow-Abbruch ist auditrelevant, Actor kann aber fehlen. | Actor-Pflicht für Abbruch prüfen. |
| `modules/documents/workflow_use_cases.py` | 424 | `domain.documents.archived.v1` | optionaler `actor_user_id`; Audit-Fallback `system`; Payload enthält nur `actor_role` | Fachliche Archivierung kann ohne menschlichen Actor als System erscheinen. | Archivierung als menschlicher Actor oder System Actor entscheiden. |
| `modules/documents/service.py` | 173 | `domain.documents.artifact.imported.v1` für generiertes `SOURCE_PDF` | Event erhält optionalen Actor; Audit nutzt `actor_user_id or owner_user_id or "system"` | Technische DOCX->PDF-Erzeugung kann fehlenden interaktiven Actor verdecken. | System-/Service-Actor vs. ausführender User entscheiden. |
| `modules/documents/service.py` | 904 | `domain.documents.read.confirmed.v1` | `actor_user_id=user_id`; `user_id` ist zugleich Receipt-Zieluser | Belastbar nur bei eindeutig belegter Selbst-Kenntnisnahme; sonst Actor/Target vermischt. | AP-010-Regel später konkret auf Direct-Confirm-Flow anwenden. |
| `modules/signature/signature_execute_ops.py` | 47/56/99/106 | `domain.signature.sign.*.v1` Documents-nah | `request.signer_user`; Signaturmodul-Event, nicht Documents-Event | Signatur-Actor kann in Documents-Flows fälschlich als AuditActor gelesen werden. | In Signatur-vs-AuditActor-Matrix getrennt behandeln. |

## Kategorie C — Events mit legacy/nicht belastbarer Actor-Quelle

| Datei | Zeile | Event/Event-Call | nicht belastbarer Mechanismus | Risiko für MVP-Audit-Export | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 93/140/193/394 | Workflow-Audit zu Rollen/Start/Editing/Abort | Audit-Actor wird über `actor_user_id or owner_user_id or "system"` gebildet | Owner oder `system` kann ausführenden User ersetzen. | Nicht als belastbar exportieren, bis Fallback-Policy entschieden ist. |
| `modules/documents/workflow_use_cases.py` | 433 | Archivierungs-Audit zu `domain.documents.archived.v1` | Audit-Actor `actor_user_id or "system"` | Fachliche Archivierung kann wie Systemaktion erscheinen. | System-Actor-Zulässigkeit für Archivierung entscheiden. |
| `modules/documents/service.py` | 904 | `domain.documents.read.confirmed.v1` | Zieluser wird als Actor gesetzt, wenn Quelle nicht als Selbst-Kenntnisnahme belegt ist | Lesebestätigung kann Zieluser und ausführenden User vermischen. | Nach AP-010 als eingeschränkt/legacy markieren, falls Quelle unklar ist. |
| `modules/documents/comment_sync_service.py` | 70 | `domain.documents.workflow.comment.synced.v1` | DOCX-Autor steht als `author_display`; `actor_user_id` nur im Payload, nicht im Envelope | Import-/DOCX-Autor kann mit AuditActor verwechselt werden. | Fremdautor als Metadatum ausweisen; Sync-Actor separat klassifizieren. |
| `modules/documents/comment_extractors/docx_comment_reader.py` | 99 | DOCX-Kommentar-Quellschlüssel mit `unknown` | `unknown` als Autor-Fallback für Fremdartefakt | `unknown` ist kein belastbarer Audit Actor. | In Nachweispaketen als Legacy-/Importmetadatum markieren. |
| `interfaces/cli/commands/documents_commands.py` | 122 | Adapter-Actor-Weitergabe an Documents-Events | Current User aus lokaler Session / CLI-Rollenmapping | Adapterzustand kann als finale Actor-Quelle missverstanden werden. | Service-Grenze später auf UserContext/RequestContext absichern. |

## Kategorie D — Events ohne Actor

| Datei | Zeile | Event/Event-Call | auditrelevanter Kontext | Actor erforderlich für MVP: ja/nein/offen | Risiko |
| --- | ---: | --- | --- | --- | --- |
| `modules/documents/pdf_read_tracking_service.py` | 41 | `domain.documents.read.session.started.v1` | Start einer Read-Session für Kenntnisnahme | ja/offen | Nachweiskette vom Öffnen bis Receipt hat keinen Event-Actor. |
| `modules/documents/pdf_read_tracking_service.py` | 77 | `domain.documents.read.session.incomplete.v1` | Unvollständige Read-Session | offen/ja | Unvollständige Kenntnisnahme kann nicht sicher einem Actor zugeordnet werden. |
| `modules/documents/pdf_read_tracking_service.py` | 91 | `domain.documents.read.session.completed.v1` | Abschluss erzeugt ggf. Read Receipt | ja | Lesebestätigung ist ohne Event-Actor nicht belastbar exportierbar. |
| `modules/documents/comment_service.py` | 113 | `domain.documents.workflow.comment.created.v1` | Workflow-/PDF-Kommentar entsteht mit Record-Author | offen/ja | EventEnvelope hat keinen Actor; Actor steht nur im Record. |
| `modules/documents/comment_service.py` | 139 | `domain.documents.workflow.comment.status.changed.v1` | Kommentarstatuswechsel mit `status_changed_by` im Record | offen | EventEnvelope hat keinen Actor; Export müsste Record und Event zusammenführen. |
| `modules/documents/comment_sync_service.py` | 70 | `domain.documents.workflow.comment.synced.v1` | DOCX-Kommentar-Sync | offen | Actor steht nur im Payload; Envelope-Actor fehlt. |
| `modules/documents/module.py` | 78/86 | `domain.documents.module.started.v1` / `domain.documents.module.stopped.v1` | Module-Lifecycle, systemnah | nein/offen | Kein fachlicher Documents-Actor; Systemkontext für technische Nachweise offen. |
| `modules/documents/service.py` | 193 | `_ensure_release_pdf_artifact` ohne eigenes Event | RELEASED_PDF-Erzeugung als technische Folge der Freigabe | offen | Fachliche Freigabe und technische Artefakterzeugung sind nicht als Eventkette getrennt nachvollziehbar. |

## Kategorie E — Correlation/Causation-Kontext

| Datei | Zeile | Event/Event-Call | Correlation vorhanden | Causation vorhanden | Nachweisketten-Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/documents/eventing.py` | 19 | `EventEnvelope.create(...)` in `publish_event` | nicht explizit übergeben | nicht explizit übergeben | EventEnvelope kann technische IDs erzeugen, aber Use-Case-/Request-Kette wird nicht service-seitig durchgereicht. | Pflichtgrad für RequestContext/Correlation/Causation entscheiden. |
| `modules/documents/workflow_use_cases.py` | 80/131/182/226/259/315/353/385/424/484 | Workflow-Eventfamilie | nicht explizit übergeben | nicht explizit übergeben | Review, Approval, Archivierung und Validitätsverlängerung sind nur lose als Einzelereignisse verknüpft. | Workflow-Nachweiskette später mit Request-/Causation-Kontext planen. |
| `modules/documents/service.py` | 629/658/690 | Intake-/Template-Events | nicht explizit übergeben | nicht explizit übergeben | Dokumenterstellung, Artefaktimport und spätere Workflow-Events sind nicht über Causation verbunden. | Intake-zu-Workflow-Kette im Nachweispaket kennzeichnen. |
| `modules/documents/service.py` | 904 | `domain.documents.read.confirmed.v1` | nicht explizit übergeben | nicht explizit übergeben | Direct-Confirm-Receipt ist nicht mit Read-Session oder Training-Kontext gekoppelt. | Read-Receipt-Kette nach AP-010 konkretisieren. |
| `modules/documents/pdf_read_tracking_service.py` | 41/77/91 | Read-Tracking-Events | nicht explizit übergeben | nicht explizit übergeben | Start, incomplete und completed sind über `session_id` im Payload verbunden, aber nicht über Event-Causation. | `session_id` reicht fachlich nicht als Actor-/Causation-Ersatz. |
| `modules/documents/comment_service.py` | 113/139 | Kommentar-Events | nicht explizit übergeben | nicht explizit übergeben | Kommentarrecord, Workflowstatus und Event sind nicht als Auditkette abgesichert. | Kommentar-/Review-Nachweiskette später einordnen. |
| `modules/documents/comment_sync_service.py` | 70 | `domain.documents.workflow.comment.synced.v1` | nicht explizit übergeben | nicht explizit übergeben | DOCX-Import, externer Autor und Sync-Actor bleiben schwer trennbar. | Import-/Sync-Causation und Fremdmetadaten getrennt planen. |
| `modules/signature/signature_execute_ops.py` | 47/56/99/106 | `domain.signature.sign.*.v1` Documents-nah | nicht explizit übergeben | nicht explizit übergeben | Signaturereignisse sind nicht kausal mit Documents-Workflow-Events verbunden. | Signatur-vs-AuditActor und Workflow-Causation separat klären. |

## Kategorie F — Supervisor-Entscheidung nötig

| Datei | Zeile | Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | ---: | --- | --- | --- |
| `modules/documents/pdf_read_tracking_service.py` | 91 | `domain.documents.read.session.completed.v1` ohne Actor | Receipt enthält `session.user_id`, Event aber keinen Actor. | Read-Receipt-Actor/Target-Regel aus AP-010 später in Umsetzungsvorbereitung konkretisieren. |
| `modules/documents/workflow_use_cases.py` | 80 | `domain.documents.assignments.updated.v1` mit optionalem Actor | Rollenvergabe kann auditrelevant sein, Actor aber optional. | Müssen Workflow-Rollenänderungen zwingend einen Actor haben? |
| `modules/documents/workflow_use_cases.py` | 131/182/385 | Workflow-Start, Editing-Complete, Abort mit optionalem Actor | Interaktive Workflow-Aktionen können Owner-/System-Fallback erhalten. | Owner-Fallback verbieten, erlauben oder als legacy/eingeschränkt markieren. |
| `modules/documents/workflow_use_cases.py` | 424 | `domain.documents.archived.v1` | Archivierung erlaubt `system`-Fallback im Audit. | Archivierung immer menschlicher QMB/Admin oder erlaubter System Actor? |
| `modules/documents/service.py` | 173 | Generated `SOURCE_PDF` als `artifact.imported` | Technische DOCX->PDF-Erzeugung kann interaktiv oder systemnah sein. | Als System-/Service-Actor oder ausführender User klassifizieren. |
| `modules/documents/service.py` | 193 | RELEASED_PDF-Erzeugung ohne eigenes Event | Technische Folge der fachlichen Freigabe ist nicht separat nachweisbar. | Braucht Release-PDF-Erzeugung eigenen Actor-/Causation-Kontext im Nachweispaket? |
| `modules/signature/signature_execute_ops.py` | 47/99 | Signatur-Events mit `signer_user` | Signatur-Actor ist nicht automatisch Documents-AuditActor. | Signatur-Actor-vs-AuditActor-Abgrenzung verbindlich machen. |
| `modules/documents/comment_sync_service.py` | 57/70 | DOCX-Autor und Sync-Actor | Fremdautor, Sync-Actor und Event-Actor sind nicht sauber getrennt. | Darstellung von DOCX-/Import-/Kommentar-Autoren im Nachweispaket. |
| `modules/documents/eventing.py` | 19 | Keine explizite Correlation/Causation-Übergabe | Nachweisketten über Request-/Command-Grenzen bleiben offen. | Sind Correlation/Causation für MVP-Documents-Events Pflicht? |

## Kritischste Documents-Event-Gaps
1. `modules/documents/pdf_read_tracking_service.py:91`: Completed-Read-Event ohne Actor blockiert belastbare Lesebestätigungsnachweise.
2. `modules/documents/pdf_read_tracking_service.py:41`: Read-Session-Start ohne Actor erschwert die Nachweiskette vom Öffnen bis Receipt.
3. `modules/documents/workflow_use_cases.py:80`: Workflow-Rollenereignis erlaubt optionalen Actor und Audit-Fallback auf Owner/`system`.
4. `modules/documents/workflow_use_cases.py:131`: Workflow-Start erlaubt optionalen Actor und kann Owner/`system` als Audit-Actor nutzen.
5. `modules/documents/workflow_use_cases.py:182`: Editing-Abschluss ist signaturnah, aber Actor optional und Fallback-basiert.
6. `modules/documents/workflow_use_cases.py:424`: Archivierung kann als `system` erscheinen, obwohl sie fachlich QMB/Admin-nah ist.
7. `modules/documents/comment_service.py:113`: Kommentar-Event hat trotz explizitem Kommentar-Actor keinen Envelope-Actor.
8. `modules/documents/comment_sync_service.py:70`: DOCX-Kommentar-Sync führt Actor nur im Payload, nicht im EventEnvelope.
9. `modules/documents/service.py:173`: DOCX->PDF-Erzeugung vor Signatur nutzt optionalen Actor und Owner-/System-Fallback.
10. `modules/documents/eventing.py:19`: Documents-Events übergeben keine explizite Correlation/Causation für Nachweisketten.

## Vorschlag für spätere Paketierung

| Paketname | Ziel | Scope | Risiko | erforderliche Vorentscheidung |
| --- | --- | --- | --- | --- |
| Documents-Workflow-Fallback-Policy | Owner-/System-Fallbacks für Rollen, Start, Editing, Abort, Archivierung und Artefakterzeugung fachlich entscheiden. | Analyse/ADR zu `modules/documents/workflow_use_cases.py` und `modules/documents/service.py`. | mittel, weil spätere Audit-Export-Belastbarkeit betroffen ist. | System-Actor-Policy und Actor-Pflicht je Workflowaktion. |
| Read-Receipt-Service-Actor-Implementierungsvorbereitung | AP-010-Regeln auf Direct-Confirm- und Tracked-Read-Flows als Umsetzungsvorbereitung herunterbrechen. | Nur Read-Receipt/Read-Tracking, keine Umsetzung ohne weitere Freigabe. | mittel, weil Event-/Service-Grenzen betroffen sein könnten. | Receipt-User-vs-Actor und Legacy-Status entscheiden. |
| Documents-Signatur-vs-Audit-Actor-Matrix | SignRequest-Signer, Signaturmodul-Events und Documents-Workflow-Actor trennen. | Documents-nahe Signaturübergänge und `modules/signature/*` zur Einordnung. | mittel bis hoch, weil Signatur/Nachweis fachlich sensibel ist. | Elektronische Signatur und Nachweisniveau bleiben separate Supervisor-Entscheidung. |

Keines dieser Pakete ist mit AP-011 gestartet.

## Auswirkungen auf Audit-Export / Nachweispaket
- Tragfähig wirken:
  - Review-/Approval-Annahme und -Ablehnung tragen `actor_user_id` im Envelope und im Payload und werden service-seitig gegen Reviewer/Approver geprüft.
  - Gültigkeitsverlängerung verlangt einen nicht-leeren Actor und trägt Actor im Event und Payload.
  - Change Requests tragen einen expliziten Actor und sind service-seitig auf Owner/QMB/Admin begrenzt.
- Eingeschränkt bleiben:
  - Intake-, Template-, Metadata- und viele Workflow-Events tragen zwar Actor-Felder, aber deren Quelle ist ohne UserContext/RequestContext nur eingeschränkt belastbar.
  - Workflow-Rollen, Start, Editing und Abort haben optionale Actor-Parameter und Owner-/System-Fallbacks im Audit.
  - Archivierung kann auditseitig als `system` erscheinen.
  - Read-Tracking-, Kommentar- und DOCX-Sync-Events haben keinen belastbaren Envelope-Actor.
  - Signatur-Events haben einen `signer_user`, sind aber nicht automatisch Documents-AuditActor.
- Vor belastbarem MVP-Audit-Export zu adressieren:
  - Read-Tracking-/Receipt-Actor für Start, Incomplete und Completed.
  - Documents-Owner-/System-Fallback-Policy.
  - Kommentar-/DOCX-Autor als Metadatum vs. AuditActor.
  - Signatur-Actor-vs-AuditActor.
  - Explizite Correlation/Causation oder klare Nachweiskettenkennzeichnung.
  - Exportkennzeichnung `belastbar/eingeschränkt/legacy` je Eventfamilie.

## Ausgeführte Gates
- Such-/Analysekommandos:
  - `Glob` Existenzprüfung für `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` -> Datei existierte nicht.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien -> erfolgreich.
  - `rg`-Suchen in `modules/documents/*`, `modules/signature/*`, `interfaces/cli/commands/documents_commands.py`, `interfaces/pyqt/*` und `tests/*` nach Event-/Actor-/Correlation-/Signaturmustern -> erfolgreich.
  - `ReadFile` zentraler Event-Hotspots -> erfolgreich.
- Ergebnis:
  - Documents-Event-Actor-Matrix erstellt.
  - Keine Testsuite ausgeführt, weil AP-011 ein Analyse-/Inventarpaket ist und vollständige Tests ausdrücklich ausgeschlossen sind.
  - Keine Linter oder Typechecker ausgeführt, weil AP-011 ein Analyse-/Inventarpaket ist und keine erfundenen Tools ausgeführt werden sollen.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Event-Schema-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll als nächstes entscheiden, ob ein reines ADR-/Analysepaket `Documents-Workflow-Fallback-Policy` freigegeben oder zurückgestellt wird; keine Implementierung automatisch starten.
