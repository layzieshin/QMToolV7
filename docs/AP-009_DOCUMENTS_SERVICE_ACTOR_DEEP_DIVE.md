# AP-009 Documents-Service-Actor-Deep-Dive

## Status
- Arbeitspaket: AP-009
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Migration: nein

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` auf `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` zur Existenzprüfung.
  - `ReadFile` für `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`, `docs/AP-004_USER_CONTEXT_ADR.md`, `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`, `docs/AP-006_AUDIT_ACTOR_ADR.md`, `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`, `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`, `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md`, `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md` und `.cursor/rules/00-agent-workflow.mdc`.
  - `rg` in `modules/documents/*` nach `actor_user_id`, `actor_role`, `EventEnvelope.create`, `emit_audit`, `_emit_audit`, `_publish`, `actor=`, `"system"`, `"unknown"`, `get_current_user()`, `read.session`, `comment`, `workflow`, `archive`, `validity`, `signature` und `sign`.
  - `rg` in `interfaces/cli/commands/documents_commands.py` nach Documents-Kommandos und Actor-Weitergabe.
  - `rg` in `interfaces/pyqt/*documents*` und `interfaces/pyqt/contributions/documents_workflow/*` nach Documents-Actor-Weitergabe, Signatur-Actor und Adapterzustand.
  - `rg` in `tests/*documents*` und `tests/**/documents*` nach Documents-Test-/Fixture-Fällen.
  - `ReadFile` gezielter Hotspots in `modules/documents/service.py`, `workflow_use_cases.py`, `pdf_read_tracking_service.py`, `comment_service.py`, `comment_sync_service.py`, `eventing.py` und den Documents-Adaptern.
- Geprüfte Bereiche:
  - `modules/documents/*`
  - `interfaces/cli/commands/documents_commands.py`
  - `interfaces/pyqt/*documents*`
  - `interfaces/pyqt/contributions/documents_workflow/*`
  - `interfaces/pyqt/widgets/pdf_viewer_dialog.py`
  - `tests/*documents*`
  - `tests/**/documents*`
  - freigegebene ADR-/Roadmap-/Regeldateien
- Ausgeschlossene Bereiche:
  - Keine absichtlich ausgeschlossenen Documents-Bereiche innerhalb des freigegebenen Scopes.
  - Nicht-Documents-Module wurden nicht vertieft.
  - Signaturmodul-Internals wurden nicht inventarisiert; nur Documents-nahe Signatur-Actor-Übergaben wurden eingeordnet.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Gesamtzahl relevanter Documents-Actor-Fundstellen: 35
- Anzahl Kategorie A: 12
- Anzahl Kategorie B: 9
- Anzahl Kategorie C: 9
- Anzahl Kategorie D: 8
- Anzahl Kategorie E: 8
- Anzahl Kategorie F: 9

Hinweis: Die Zahlen zählen Matrixzeilen. Einzelne Service-Flows erscheinen bewusst in mehreren Kategorien, wenn sie z. B. einen expliziten Actor-Parameter besitzen, aber zusätzlich einen Fallback oder eine unklare Adapterquelle haben.

## Kategorie A — Explizite Actor/User-Übergabe

| Datei | Zeile | Funktion/Methode | Parameter | Actor-/User-Quelle | Nachweisstatus | MVP-Flow |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/documents/service.py` | 613 | `import_existing_pdf` | `actor_user_id`, `actor_role` | expliziter Service-Parameter, Quelle aktuell Adapter | eingeschränkt bis Quelle klassifiziert | Dokument erstellen / Import |
| `modules/documents/service.py` | 642 | `import_existing_docx` | `actor_user_id`, `actor_role` | expliziter Service-Parameter, Quelle aktuell Adapter | eingeschränkt bis Quelle klassifiziert | Dokument erstellen / Import |
| `modules/documents/service.py` | 671 | `create_from_template` | `actor_user_id`, `actor_role` | expliziter Service-Parameter, Quelle aktuell Adapter | eingeschränkt bis Quelle klassifiziert | Dokument erstellen |
| `modules/documents/service.py` | 531 | `add_change_request` | `actor_user_id`, `actor_role` | expliziter Service-Parameter mit Owner/QMB/Admin-Prüfung | eingeschränkt bis Quelle klassifiziert | Audit-/Nachweisexport-nahe Dokumentenereignisse |
| `modules/documents/workflow_use_cases.py` | 58 | `assign_workflow_roles` | `actor_user_id`, `actor_role` | optionaler Service-Parameter | eingeschränkt | Dokument erstellen / Workflow vorbereiten |
| `modules/documents/workflow_use_cases.py` | 107 | `start_workflow` | `actor_user_id`, `actor_role` | optionaler Service-Parameter | eingeschränkt | Dokument prüfen/freigeben |
| `modules/documents/workflow_use_cases.py` | 205 | `accept_review` | `actor_user_id`, optional `actor_role` | verpflichtender Reviewer-Parameter | belastbar nach Quellklassifikation | Dokument prüfen/freigeben |
| `modules/documents/workflow_use_cases.py` | 247 | `reject_review` | `actor_user_id`, optional `actor_role` | verpflichtender Reviewer-Parameter | belastbar nach Quellklassifikation | Dokument ablehnen |
| `modules/documents/workflow_use_cases.py` | 280 | `accept_approval` | `actor_user_id`, optional `actor_role` | verpflichtender Approver-Parameter | belastbar nach Quellklassifikation | Dokument veröffentlichen |
| `modules/documents/workflow_use_cases.py` | 341 | `reject_approval` | `actor_user_id`, optional `actor_role` | verpflichtender Approver-Parameter | belastbar nach Quellklassifikation | Dokument ablehnen |
| `modules/documents/workflow_use_cases.py` | 446 | `extend_annual_validity` | `actor_user_id` | verpflichtender nicht-leerer Service-Parameter | belastbar nach Quellklassifikation | Gültigkeit verlängern |
| `modules/documents/comment_service.py` | 73 | `create_pdf_comment` | `actor_user_id`, `actor_role` | expliziter Kommentar-Actor | eingeschränkt, Event-Actor fehlt | Kommentar-/Review-Events |

## Kategorie B — Eingeschränkte Actor-Quellen

| Datei | Zeile | Funktion/Methode | eingeschränkte Quelle | Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- |
| `modules/documents/workflow_use_cases.py` | 95 | `assign_workflow_roles` | `actor_user_id or updated.owner_user_id or "system"` | Owner/System-Fallback kann ausführenden Actor ersetzen. | Owner-/System-Fallback-Policy entscheiden. |
| `modules/documents/workflow_use_cases.py` | 142 | `start_workflow` | `actor_user_id or updated.owner_user_id or "system"` | Workflow-Start kann ohne expliziten Actor auditierbar wirken. | Actor-Pflicht für Workflow-Start prüfen. |
| `modules/documents/workflow_use_cases.py` | 195 | `complete_editing` | `actor_user_id or updated.owner_user_id or "system"` | Editing-Abschluss und ggf. Signaturübergang kann Fallback-Actor erhalten. | Actor-Pflicht/Fallback-Regel für Editing abschließen. |
| `modules/documents/workflow_use_cases.py` | 396 | `abort_workflow` | `actor_user_id or updated.owner_user_id or "system"` | Workflow-Abbruch kann Owner/System statt ausführenden User zeigen. | Abbruch als auditrelevante Aktion mit Actor-Pflicht markieren. |
| `modules/documents/workflow_use_cases.py` | 435 | `archive_approved` | `actor_user_id or "system"` | Fachliche Archivierung kann als `system` erscheinen. | Klären, ob Archivierung immer menschlichen Actor braucht. |
| `modules/documents/workflow_use_cases.py` | 505 | `extend_annual_validity` | `actor_user_id or "system"` trotz vorheriger Validierung | Codepfad enthält System-Fallback, auch wenn Actor validiert wird. | Als Review-Hinweis für spätere Bereinigung markieren. |
| `modules/documents/service.py` | 172 | `_ensure_source_pdf_artifact_for_signing` | `actor_user_id or state.owner_user_id or "system"` | Automatische DOCX->PDF-Erzeugung vor Signatur kann unklaren Actor erhalten. | System-/Service-Actor vs. ausführender User entscheiden. |
| `interfaces/cli/commands/documents_commands.py` | 23 | `_resolve_current_user_and_role` | lokaler Current User aus Usermanagement | CLI-Adapterquelle ist für Backend/Multiuser nur eingeschränkt belastbar. | Später UserContext/RequestContext statt lokaler Session. |
| `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py` | 318 | `_complete_editing` Fehler-Audit | Fallback `actor = "system"` im GUI-Fehlerpfad | GUI schreibt freien Actor bei Fehler-Audit, nicht Service-Actor. | Adapter-Audit getrennt von fachlichem Service-Audit einordnen. |

## Kategorie C — Events ohne belastbaren Actor

| Datei | Zeile | Event-/Audit-Call | aktueller Actor-Status | Risiko für MVP-Audit-Export | Blocker: ja/nein/offen |
| --- | ---: | --- | --- | --- | --- |
| `modules/documents/pdf_read_tracking_service.py` | 41 | `domain.documents.read.session.started.v1` | kein `actor_user_id` im Event | Read-Session-Start ist nicht actor-belastbar. | ja |
| `modules/documents/pdf_read_tracking_service.py` | 77 | `domain.documents.read.session.incomplete.v1` | kein `actor_user_id` im Event | Unvollständige Kenntnisnahme kann nicht eindeutig einem Actor im Event zugeordnet werden. | offen/ja |
| `modules/documents/pdf_read_tracking_service.py` | 91 | `domain.documents.read.session.completed.v1` | kein `actor_user_id`; Receipt enthält `session.user_id` | Lesebestätigung/Nachweisereignis ist im Event nicht actor-belastbar. | ja |
| `modules/documents/comment_service.py` | 113 | `domain.documents.workflow.comment.created.v1` | Actor nur im Record, nicht im EventEnvelope | Kommentarereignis kann im Event ohne Actor erscheinen. | offen/ja |
| `modules/documents/comment_service.py` | 139 | `domain.documents.workflow.comment.status.changed.v1` | Actor nur im Record, nicht im EventEnvelope | Kommentarstatuswechsel ist ohne Event-Actor eingeschränkt. | offen |
| `modules/documents/comment_sync_service.py` | 70 | `domain.documents.workflow.comment.synced.v1` | `actor_user_id` nur im Payload, nicht im Envelope | Event-Actor fehlt; Import-/Sync-Actor und DOCX-Autor können verwechselt werden. | offen |
| `modules/documents/module.py` | 78 | `domain.documents.module.started.v1` | kein Actor | Lifecycle-Event ist systemnah, aber nicht fachlicher Documents-Actor. | nein/offen |
| `modules/documents/service.py` | 193 | `_ensure_release_pdf_artifact` | kein Event/Audit für RELEASED_PDF-Erzeugung erkennbar | Veröffentlichungsartefakt kann exportnah relevant sein, aber ohne eigene Actor-Spur. | offen |
| `modules/documents/service.py` | 514 | `domain.documents.metadata.updated.v1` | `actor_user_id` wird durchgereicht, aber keine AuditLogger-Zeile | Event-Actor vorhanden, aber Export muss Event/Audit-Quelle trennen. | offen |

## Kategorie D — MVP-Documents-Gaps

| Documents-Flow | Service/Funktion | aktueller Actor-Status | Gap | Blocker für belastbaren MVP-Audit-Export: ja/nein/offen | spätere Behandlung |
| --- | --- | --- | --- | --- | --- |
| Dokument erstellen | `create_document_version` / `import_existing_pdf` / `import_existing_docx` / `create_from_template` | gemischt: Draft ohne Actor, Import/Template mit Actor | Draft-Erstellung kann Owner als Feld haben, aber nicht zwingend Audit Actor/Event. | offen | Erstellungsflow zwischen Draft, Import und Template fachlich trennen. |
| Dokument prüfen/freigeben | `accept_review`, `accept_approval` | expliziter Actor-Parameter | Service-Grenze wirkt tragfähig, Quelle aus CLI/PyQt aber noch eingeschränkt. | offen | Actor-Quelle aus UserContext/RequestContext später absichern. |
| Dokument ablehnen | `reject_review`, `reject_approval` | expliziter Actor-Parameter | Tragfähig nach Quellklassifikation; Ablehnungsgrund als Auditdetail prüfen. | offen | Exportfelder für Grund/Target/Actor definieren. |
| Dokument veröffentlichen | `accept_approval` / `_ensure_release_pdf_artifact` | Approver explizit, Release-PDF-Erzeugung systemnah ohne eigene Actor-Spur | Fachliche Freigabe und technische Artefakterzeugung müssen getrennt nachweisbar sein. | offen/ja | Release-Event-/Artefakt-Kontext fachlich einordnen. |
| Lesebestätigung / Kenntnisnahme | `PdfReadTrackingService.start` / `finalize` | `user_id` in Session/Receipt, kein Event-Actor | Read-Events ohne `actor_user_id` blockieren belastbaren Nachweis. | ja | Read-Receipt-Actor-Anforderung priorisieren. |
| Gültigkeit verlängern | `extend_annual_validity` | verpflichtender Actor, zusätzlich Fallback im Audit-String | Service validiert Actor, Code enthält aber `or "system"`-Fallback. | offen | Fallback prüfen und Signatur-/Actor-Beziehung klären. |
| Dokument signieren | `complete_editing`, `accept_review`, `accept_approval`, SignRequest aus Adapter | Signatur-User aus Adapter/SignRequest; Service nutzt `actor_user_id` | Signatur-Actor, ausführender Actor und Audit Actor sind nicht formal getrennt. | offen/ja | Signatur-Actor-vs-Audit-Actor-ADR/Matrix nötig. |
| Audit-/Nachweisexport-nahe Dokumentenereignisse | `add_change_request`, Kommentare, Metadata, Registry-Sync | teils Actor im Event, teils nur Payload/Record | Export muss mehrere Quellen zusammenführen und Status ausweisen. | ja | Exportmodell darf fehlende/indirekte Actor nicht als belastbar darstellen. |

## Kategorie E — Späterer Kontextbedarf

| Use Case | Service/Funktion | benötigt UserContext | benötigt RequestContext | benötigt AuditActor | System Actor ausreichend | offene Entscheidung |
| --- | --- | --- | --- | --- | --- | --- |
| Dokument-Draft erstellen | `create_document_version` | ja/offen | ja | ja/offen | nein | Ist Draft-Erstellung auditpflichtig, und wer ist Actor bei Owner-Abweichung? |
| Dokument importieren / aus Template erstellen | `import_existing_pdf`, `import_existing_docx`, `create_from_template` | ja | ja | ja | nein | Quelle heutiger Adapter-Actor muss belastbar werden. |
| Workflow-Rollen zuweisen | `assign_workflow_roles` | ja | ja | ja | nein | Owner-Fallback und optionale Actor-Parameter entscheiden. |
| Workflow starten / abbrechen | `start_workflow`, `abort_workflow` | ja | ja | ja | nein | Actor-Pflicht für Start/Abort festlegen. |
| Review/Approval annehmen/ablehnen | `accept_review`, `reject_review`, `accept_approval`, `reject_approval` | ja | ja | ja | nein | Signatur-Actor vs. Audit Actor und Rollenstatus im Export klären. |
| Release-PDF erzeugen | `_ensure_release_pdf_artifact` | nein/offen | ja | ja/offen | offen, ggf. technischer Folgeactor | Technisches Folgeevent durch fachliche Freigabe causation-verknüpfen? |
| Read-Tracking / Receipt | `PdfReadTrackingService.start`, `finalize` | ja | ja | ja | nein | Receipt-User als Actor oder Target/Subject? |
| Workflow-Kommentare | `WorkflowCommentService`, `CommentSyncService` | ja | ja | ja/offen | nein/offen für Import-Sync | PDF-Kommentar-Actor vs. DOCX-Autor/Importmetadatum trennen. |

## Kategorie F — Supervisor-Entscheidung nötig

| Datei | Zeile | Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | ---: | --- | --- | --- |
| `modules/documents/service.py` | 172 | `actor_user_id or state.owner_user_id or "system"` | Technische DOCX->PDF-Erzeugung kann interaktiv oder systemnah sein. | Als System-/Service-Actor oder ausführender User klassifizieren. |
| `modules/documents/workflow_use_cases.py` | 95 | `actor_user_id or updated.owner_user_id or "system"` | Owner-vs-ausführender-User bei Rollenvergabe. | Owner-Fallback zulässig oder legacy? |
| `modules/documents/workflow_use_cases.py` | 142 | `actor_user_id or updated.owner_user_id or "system"` | Workflow-Start kann Owner/System-Actor bekommen. | Actor-Pflicht für Workflow-Start. |
| `modules/documents/workflow_use_cases.py` | 435 | `actor_user_id or "system"` | Archivierung als System ist auditfachlich unklar. | Archivierung immer menschlicher QMB/Admin oder erlaubter System Actor? |
| `modules/documents/pdf_read_tracking_service.py` | 91 | Completed-Read-Event ohne Actor | Receipt-User kann Actor sein, ist aber nicht als Event-Actor geführt. | Read-Receipt-Actor/Target-Regel entscheiden. |
| `modules/documents/comment_sync_service.py` | 57 | `author_display=item.author` | DOCX-Autor ist Importmetadatum, nicht Audit Actor. | Darstellung von Import-/Kommentar-Autoren in Nachweispaketen. |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | 176 | `signer_user=str(user.user_id)` | Signatur-User kommt aus Adapterzustand, AuditActor ist nicht formal getrennt. | Signatur-Actor vs. Audit-Actor abgrenzen. |
| `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py` | 597 | `signing_user_id = str(sign_request.signer_user or user.user_id)` | Gültigkeitsverlängerung nutzt SignRequest-Signer als Actor. | Darf SignRequest-Signer den AuditActor bestimmen? |
| `tests/*documents*` | diverse | Test-Actor wie `admin`, `qmb-1`, `owner-1` | Testnähe nicht automatisch produktiv relevant. | Test-/Fixture-Funde von Produktiv-Actorquellen trennen. |

## Kritischste Documents-Service-Gaps
1. `modules/documents/pdf_read_tracking_service.py:91`: Completed-Read-Event ohne Actor blockiert belastbare Lesebestätigungsnachweise.
2. `modules/documents/pdf_read_tracking_service.py:41`: Read-Session-Start ohne Actor erschwert Nachweiskette vom Öffnen bis Receipt.
3. `modules/documents/workflow_use_cases.py:95`: Rollenvergabe nutzt optionalen Actor und Owner-/System-Fallback.
4. `modules/documents/workflow_use_cases.py:142`: Workflow-Start nutzt optionalen Actor und Owner-/System-Fallback.
5. `modules/documents/workflow_use_cases.py:195`: Editing-Abschluss nutzt Fallbacks und ist signaturnah.
6. `modules/documents/workflow_use_cases.py:435`: Archivierung kann mit `system` statt menschlichem Actor protokolliert werden.
7. `modules/documents/comment_service.py:147`: Kommentarservice nimmt Actor entgegen, publiziert aber Event ohne `actor_user_id`.
8. `modules/documents/comment_sync_service.py:96`: DOCX-Kommentar-Sync publiziert Actor nur im Payload, nicht im EventEnvelope.
9. `modules/documents/service.py:172`: DOCX->PDF-Erzeugung vor Signatur nutzt Actor-/Owner-/System-Fallback.
10. `interfaces/pyqt/presenters/documents_signature_ops.py:84`: Signaturkontext entsteht aus GUI-Current-User; Signatur-Actor und AuditActor sind noch nicht sauber getrennt.

## Vorschlag für spätere Paketierung

| Paketname | Ziel | Scope | Risiko | erforderliche Vorentscheidung |
| --- | --- | --- | --- | --- |
| Documents-Read-Receipt-Actor-ADR | Read-Session, Receipt, Actor, Target und Eventstatus fachlich entscheiden. | Nur Analyse/ADR zu `PdfReadTrackingService` und Nachweispaket-Anforderungen. | mittel, weil MVP-Kenntnisnahme auditkritisch ist. | Nachweisstatus-Vokabular und Receipt-User-vs-Actor-Regel. |
| Documents-Workflow-Fallback-Policy | Owner-/System-Fallbacks für Workflow-Rollen, Start, Editing, Abort, Archivierung und Artefakterzeugung entscheiden. | Nur ADR/Analyse für `workflow_use_cases.py` und `service.py`-Fallbacks. | mittel. | System-Actor-Policy und Actor-Pflicht je Workflowaktion. |
| Documents-Signatur-vs-Audit-Actor-Matrix | SignRequest-Signer, visueller Signaturkontext und fachlicher AuditActor trennen. | Documents-Adapter und Documents-Workflow-Signaturübergänge, ohne Signaturmodul-Implementierung. | mittel bis hoch. | Elektronische Signatur/Nachweisniveau bleibt separate Supervisor-Entscheidung. |

Keines dieser Pakete ist mit AP-009 gestartet.

## Auswirkungen auf Audit-Export / Nachweispaket
- Tragfähig wirken:
  - Review-/Approval-Annahme und -Ablehnung haben explizite Actor-Parameter und Service-Prüfungen auf Reviewer/Approver.
  - Import-/Template-/Change-Request-Flows übergeben Actor-Parameter und können später gut auf UserContext/RequestContext abgebildet werden.
  - `EventEnvelope` enthält bei vielen Workflow-Events `actor_user_id`, wenn der Service-Actor explizit übergeben wird.
- Eingeschränkt bleiben:
  - CLI/PyQt liefern Actor derzeit aus lokalem Current User bzw. Adapterzustand.
  - Workflow-Rollen, Start, Editing und Abort verwenden optionale Actor-Parameter und Owner-/System-Fallbacks.
  - Kommentare und Kommentar-Sync publizieren Events ohne belastbaren EventEnvelope-Actor.
  - Signatur-Actor, SignRequest-Signer und AuditActor sind noch nicht formal getrennt.
- Vor belastbarem MVP-Audit-Export zu adressieren:
  - Read-Tracking-/Receipt-Actor.
  - Documents-Owner-/System-Fallback-Policy.
  - Kommentar-/DOCX-Autor als Metadatum vs. AuditActor.
  - Release-PDF-/Artefaktfolgeevents mit Correlation/Causation zum fachlichen Freigabeevent.
  - Exportkennzeichnung `belastbar/eingeschränkt/legacy` für alle Documents-Actorquellen.

## Ausgeführte Gates
- Such-/Analysekommandos:
  - `Glob` Existenzprüfung für `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` -> Datei existierte nicht.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien -> erfolgreich.
  - `rg`-Suchen in `modules/documents/*`, `interfaces/cli/commands/documents_commands.py`, `interfaces/pyqt/*documents*`, `interfaces/pyqt/contributions/documents_workflow/*` und `tests/*documents*` -> erfolgreich.
  - `ReadFile` zentraler Documents-Service-/Use-Case-Hotspots -> erfolgreich.
- Ergebnis:
  - Documents-Service-Actor-Deep-Dive erstellt.
  - Keine Testsuite ausgeführt, weil AP-009 ein Analyse-/Inventarpaket ist.
  - Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein reines ADR-/Analysepaket `Documents-Read-Receipt-Actor-ADR` freigegeben wird; keine Implementierung automatisch starten.
