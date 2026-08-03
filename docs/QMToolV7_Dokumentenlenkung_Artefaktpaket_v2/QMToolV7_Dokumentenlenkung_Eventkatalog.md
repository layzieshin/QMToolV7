# QMToolV7 – Vollständiger Event- und API-Katalog der Dokumentenlenkung

**Stand:** 2026-08-03
**Ziel:** Für jeden erfolgreichen fachlichen Workflow- oder Statusübergang existiert ein versioniertes Domain-Event. Die Events enthalten genügend Routingdaten, damit spätere Consumer Aufgaben für die betroffenen Benutzer oder Rollenpools projizieren können.

## Technischer Ist-Befund

- `qm_platform/events/event_bus.py` ist ein synchroner In-Process-Publisher. Ohne Subscriber wird ein Event nicht dauerhaft gespeichert.
- Das persönliche Dashboard lädt Dokumentaufgaben derzeit zustandsbasiert über `DocumentsPoolApi`/`DocumentsReadmodelUseCases`.
- Das Documents-Modul besitzt bereits zahlreiche v1-Events und Vertragstests; sie werden nicht blind entfernt, sondern kontrolliert auf v2 gemappt.
- Word- und PDF-Kommentare besitzen bereits eigene Eventstellen, deren Actor- und Objektbezug erweitert werden soll.

## Verbindliche Lieferregeln

1. Fachzustand und Audit werden atomar persistiert.
2. Erfolgsereignisse werden niemals vor einem fehlgeschlagenen oder zurückgerollten Commit publiziert.
3. Fehlende Consumer dürfen die Fachaktion nicht verhindern.
4. Während der Migration dürfen v1 und v2 parallel publiziert werden, solange Consumer-Doppelwirkungen verhindert werden.
5. Jeder Übergangsevent enthält mindestens `document_id`, `version_record_id`, `from_status`, `to_status`, `transition_id`, `actor_user_id`, `workflow_instance_id`, `submission_round_id`, `correlation_id` und – soweit eine Aufgabe aktiviert wird – `required_action`, `target_user_ids` beziehungsweise `target_pool`, `decision_policy` und `due_at`.
6. Das bestehende zustandsbasierte Dashboard bleibt funktionsfähig. Eine dauerhafte Event-Outbox ist eine spätere technische Erweiterung, keine Voraussetzung des ersten Umbaus.

## API-Katalog

| API | Bereich | Zweck | Ist-/Migrationshinweis |
|---|---|---|---|
| `list_current_published_documents` | Aktive Dokumente | Nur aktuell gültige PUBLISHED-Dokumente liefern | list_current_released_documents liefert aktuell APPROVED; Read-Model aus Fachzustand, nicht aus Eventhistorie |
| `get_current_published_document` | Aktive Dokumente | Aktuelle gültige Version auflösen | Neu/Adapter nötig; Keine APPROVED/EXPIRED/ARCHIVED/ANNULLED zurückgeben |
| `get_published_pdf` | Artefakte | Finales RELEASED_PDF liefern | get_released_pdf_for_reading ohne neue Statuslogik; Status/Gültigkeit unmittelbar vor Ausgabe prüfen |
| `create_controlled_print_job` | Kopien | Kopiennummern atomar vergeben und PDF ausgeben | Neu; Keine Nummern bei Transaktionsfehler verbrauchen |
| `list_tasks_for_user` | Dashboard | Aufgaben aus aktuellem Zustand/Zuweisung liefern | Besteht; Bleibt unabhängig von flüchtigen Events funktionsfähig |
| `list_review_actions_for_user` | Dashboard | Nur konkret zugewiesene offene Aktionen liefern | Besteht; Soll Modulrolle + konkrete Zuweisung prüfen |

## Eventkatalog

| Event | Bereich | Auslöser | Von → Nach | Routing / Folgeaktion | Pflichtpayload | Ist-/Legacy-Mapping |
|---|---|---|---|---|---|---|
| `domain.documents.plan.created.v2` | Planung | DocumentPlan erfolgreich angelegt | — → DocumentPlan | Planersteller; QMB optional: Plan in Planungsliste anzeigen | plan_id; title; actor | kein Ist-Event |
| `domain.documents.plan.updated.v2` | Planung | Planungsdaten geändert | DocumentPlan → DocumentPlan | Planersteller/QMB: Ansicht aktualisieren | plan_id; changed_fields; actor | kein Ist-Event |
| `domain.documents.plan.discarded.v2` | Planung | Plan verworfen | DocumentPlan → — | Planersteller/QMB: Plan entfernen | plan_id; reason; actor | kein Ist-Event |
| `domain.documents.plan.converted.v2` | Planung | Plan atomar in Dokument/Version 1 überführt | DocumentPlan → DRAFT | Owner/Editor; QMB: Editoraufgabe für ersten Entwurf anbieten | plan_id; document_id; version_record_id; owner_user_id | kein Ist-Event |
| `domain.documents.document.created.v2` | Dokument | Dokumentidentität erzeugt | — → Document | Owner/QMB: Dokument in Arbeitsbestand anzeigen | document_uid; document_id; document_type_id | indirekt create_document_version |
| `domain.documents.document.metadata.updated.v2` | Metadaten | Dokumentgebundene Metadaten geändert | Document → Document | Owner/QMB/Registry: Projektion aktualisieren | document_id; changed_fields; old_values; new_values; reason | domain.documents.metadata.updated.v1 |
| `domain.documents.document.owner.changed.v2` | Owner | Interner Owner geändert | Document → Document | Alter/neuer Owner; QMB: Aufgaben-/Verantwortungsprojektion aktualisieren | document_id; old_owner; new_owner; reason | metadata.updated.v1 |
| `domain.documents.version.created.v2` | Versionierung | Version 1 oder Nachfolgeversion angelegt | — → DRAFT | Owner/Editor: Entwurfsaufgabe anzeigen | version_record_id; document_id; visible_version; based_on_version_id; change_reason | kein eindeutiges Ist-Event |
| `domain.documents.version.discarded.v2` | Versionierung | Nie eingereichter DRAFT verworfen | DRAFT → — | Owner/QMB: Entwurfsaufgabe entfernen | version_record_id; document_id; visible_version; released_identifier | kein Ist-Event |
| `domain.documents.version.change_reason.updated.v2` | Änderungen | Änderungsanlass im DRAFT korrigiert | DRAFT → DRAFT | Owner/Editor/QMB: Ansicht aktualisieren | version_record_id; old_reason; new_reason; correction_reason | metadata.updated.v1 teilweise |
| `domain.documents.version.change_entry.added.v2` | Änderungen | Strukturierter Änderungseintrag angelegt | DRAFT → DRAFT | Editor/Reviewer später: Änderungsliste aktualisieren | version_record_id; change_entry_id; section; description | change_request.added.v1 fachlich nicht identisch |
| `domain.documents.version.change_entry.updated.v2` | Änderungen | Änderungseintrag im DRAFT korrigiert | DRAFT → DRAFT | Editor: Änderungsliste aktualisieren | change_entry_id; old_values; new_values; reason | kein Ist-Event |
| `domain.documents.artifact.source.imported.v2` | Artefakte | DOCX/PDF importiert | DRAFT → DRAFT | Owner/Editor/QMB: Quelle verfügbar machen | artifact_id; version_record_id; source_type; filename; sha256; size | domain.documents.artifact.imported.v1 |
| `domain.documents.artifact.source.replaced.v2` | Artefakte | Aktuelle Quelle ersetzt | DRAFT → DRAFT | Owner/Editor/QMB: Neue Quelle markieren | old_artifact_id; new_artifact_id; hashes; reason | artifact.imported.v1 reicht nicht |
| `domain.documents.artifact.pdf.generated.v2` | Artefakte | PDF aus DOCX erzeugt | DRAFT/Workflowstufe → gleich | Workflow/Signatur: PDF für nächsten Übergang bereitstellen | artifact_id; source_artifact_id; sha256; generation_purpose | artifact.imported.v1 für GENERATED |
| `domain.documents.workflow.assignments.updated.v2` | Workflow | Rollenpools festgelegt/geändert | DRAFT/aktive Instanz → gleich | Betroffene Benutzer; Dashboard: Aufgaben-/Eligibility-Projektion aktualisieren | workflow_instance_id; editors; reviewers; approvers; reason | domain.documents.assignments.updated.v1 |
| `domain.documents.workflow.instance.started.v2` | Workflow | Workflow atomar gestartet | DRAFT → DRAFT | Editorpool/Owner: Bearbeitungs-/Einreichungsaufgabe aktivieren | workflow_instance_id; profile_id; profile_version; assignments; next_action | domain.documents.workflow.started.v1 |
| `domain.documents.workflow.instance.aborted.v2` | Workflow | Aktiver Workflow begründet beendet | DRAFT/IN_REVIEW/IN_APPROVAL → DRAFT | Alle Beteiligten; QMB: Offene Workflowaufgaben schließen; Editoraufgabe ggf. öffnen | workflow_instance_id; from_status; reason; cancelled_task_ids | domain.documents.workflow.aborted.v1 |
| `domain.documents.workflow.instance.completed.v2` | Workflow | Workflow erreicht APPROVED | IN_APPROVAL/IN_REVIEW/DRAFT → APPROVED | QMB/Publisher; Beteiligte: Publikationsaufgabe eröffnen | workflow_instance_id; round_id; approved_at; final_artifact_id | approval.accepted.v1 implizit |
| `domain.documents.workflow.runtime_rule.changed.v2` | Workflow | QMB ändert Pool/Laufzeitregel | aktive Instanz → betroffene Stufe | Betroffene Rollen/Benutzer: Entscheidungen ab betroffener Stufe widerrufen und Aufgaben neu projizieren | workflow_instance_id; changed_rule; affected_stage; revoked_decision_ids; reason | assignments.updated.v1 teilweise |
| `domain.documents.workflow.assignee.replaced.v2` | Workflow | Noch nicht tätig gewordener Akteur ersetzt | aktive Stufe → gleiche Stufe | Alter/neuer Akteur; QMB: Alte Aufgabe schließen, neue Aufgabe eröffnen | workflow_instance_id; stage; old_user_id; new_user_id; reason | assignments.updated.v1 |
| `domain.documents.workflow.stage.deadline.exceeded.v2` | Workflow | Aktive Stufenfrist überschritten | IN_REVIEW/IN_APPROVAL → gleich | Zugewiesene Akteure; QMB: Überfällige Aufgabe markieren | workflow_instance_id; round_id; stage; due_at; target_user_ids | kein Ist-Event |
| `domain.documents.workflow.submission_round.started.v2` | Workflow | DRAFT wird erneut/einmalig eingereicht | DRAFT → profilabhängig | Nächster Rollenpool: Nächste Aufgabe eröffnen | workflow_instance_id; round_id; round_no; frozen_change_entry_ids; source_pdf_id | editing.completed.v1 teilweise |
| `domain.documents.workflow.draft.submitted_for_review.v2` | Übergang | Editor reicht bei aktivem Reviewübergang ein | DRAFT → IN_REVIEW | Reviewerpool: Prüfaufgabe eröffnen | transition_id; workflow_instance_id; round_id; target_user_ids; decision_policy; due_at; artifact_id | domain.documents.editing.completed.v1 |
| `domain.documents.workflow.draft.submitted_for_approval.v2` | Übergang | Reviewstufe im Profil übersprungen | DRAFT → IN_APPROVAL | Approverpool: Freigabeaufgabe eröffnen | transition_id; workflow_instance_id; round_id; target_user_ids; policy; due_at; artifact_id | editing.completed.v1 mit to_status |
| `domain.documents.workflow.draft.approved.v2` | Übergang | Review und Approval im Profil übersprungen/ direkte Entscheidung erfüllt | DRAFT → APPROVED | QMB/Publisher: Publikationsaufgabe eröffnen | transition_id; workflow_instance_id; round_id; decision_ids; final_artifact_id | editing.completed.v1 eventuell |
| `domain.documents.workflow.review.accepted.v2` | Übergang | Reviewregel erfüllt, Approval folgt | IN_REVIEW → IN_APPROVAL | Approverpool; Reviewer: Prüfaufgabe schließen, Freigabeaufgabe eröffnen | transition_id; round_id; decision_ids; target_user_ids; due_at; artifact_id | domain.documents.review.accepted.v1 |
| `domain.documents.workflow.review.completed.v2` | Übergang | Reviewregel erfüllt, Approval im Profil übersprungen | IN_REVIEW → APPROVED | QMB/Publisher; Reviewer: Publikationsaufgabe eröffnen | transition_id; round_id; decision_ids; final_artifact_id | review.accepted.v1 mit to_status |
| `domain.documents.workflow.review.rejected.v2` | Übergang | Reviewer lehnt ab | IN_REVIEW → DRAFT | Owner/Editor; weitere Reviewer: Reviewaufgaben schließen, Korrekturaufgabe eröffnen | transition_id; round_id; actor_user_id; reason; rejected_artifact_id; editor_target_ids | domain.documents.review.rejected.v1 |
| `domain.documents.workflow.approval.accepted.v2` | Übergang | Approvalregel erfüllt | IN_APPROVAL → APPROVED | QMB/Publisher; Beteiligte: Freigabeaufgaben schließen, Publikationsaufgabe eröffnen | transition_id; round_id; decision_ids; approved_at; final_artifact_id | domain.documents.approval.accepted.v1 |
| `domain.documents.workflow.approval.rejected.v2` | Übergang | Approver lehnt ab | IN_APPROVAL → DRAFT | Owner/Editor; Reviewer/Approver: Offene Freigabeaufgaben schließen, Korrekturaufgabe eröffnen | transition_id; round_id; actor_user_id; reason; rejected_artifact_id; editor_target_ids | domain.documents.approval.rejected.v1 |
| `domain.documents.workflow.approved.withdrawn.v2` | Übergang | QMB nimmt noch nicht veröffentlichte Freigabe zurück | APPROVED → DRAFT | Owner/Editor; QMB: Publikationsaufgabe schließen, Korrekturaufgabe eröffnen | version_record_id; old_workflow_instance_id; reason; editor_target_ids | kein Ist-Event |
| `domain.documents.workflow.stage.rolled_back.v2` | Übergang | QMB-Laufzeitänderung widerruft betroffene und spätere Entscheidungen | IN_APPROVAL/IN_REVIEW → betroffene Stufe | Betroffene Rollenpools: Aufgaben ab betroffener Stufe neu eröffnen | workflow_instance_id; from_status; to_status; affected_stage; revoked_decision_ids; target_user_ids; reason | kein Ist-Event |
| `domain.documents.document.published.v2` | Lebenszyklus | APPROVED-Fassung ausdrücklich veröffentlicht | APPROVED → PUBLISHED | Training; Registry; normale Nutzer; QMB: Aktive Fassung bereitstellen; Schulungs-/Sichtbarkeitsconsumer informieren | document_id; version_record_id; published_at; valid_from; valid_until; released_pdf_id | Freigabe/Registry derzeit bei APPROVED gekoppelt |
| `domain.documents.document.previous_version.archived.v2` | Lebenszyklus | Nachfolgeversion wird veröffentlicht | PUBLISHED → ARCHIVED | QMB; Kopienprojektion; Registry: Vorgänger aus aktivem Bestand entfernen; Kopienrückruf prüfen | old_version_record_id; new_version_record_id; reason=SUPERSEDED | domain.documents.archived.v1 |
| `domain.documents.document.expiring_soon.v2` | Gültigkeit | Konfigurierter Vorwarnzeitpunkt erreicht | PUBLISHED → PUBLISHED | QMB/Owner: Prüf-/Verlängerungsaufgabe anzeigen | version_record_id; valid_until; days_remaining; target_user_ids | kein Ist-Event |
| `domain.documents.document.expired.v2` | Lebenszyklus | valid_until überschritten | PUBLISHED → EXPIRED | QMB; Training; Registry; andere Consumer: Aktiven Zugriff entziehen; QMB-Folgeaufgabe anzeigen | version_record_id; expired_at; previous_valid_until | kein Ist-Event |
| `domain.documents.document.validity.extended.v2` | Gültigkeit | QMB verlängert Gültigkeit | PUBLISHED/EXPIRED → PUBLISHED | QMB; Training; Registry: Fristen aktualisieren; bei EXPIRED Zugriff wieder aktivieren | version_record_id; old_valid_until; new_valid_until; extension_count; reason; review_outcome | domain.documents.validity.extended.v1 |
| `domain.documents.document.archived.v2` | Lebenszyklus | Version begründet archiviert | persistierter Status → ARCHIVED | QMB; Registry; Aufgabenprojektion: Aktive Aufgaben schließen und Zugriff entziehen | version_record_id; from_status; reason; actor_user_id | domain.documents.archived.v1 |
| `domain.documents.document.annulled.v2` | Lebenszyklus | Fassung formal/fachlich ungültig erklärt | persistierter Status → ANNULLED | QMB; Registry; Training; andere Consumer: Zugriff entziehen; Korrekturprozess ermöglichen | version_record_id; from_status; reason; actor_user_id; invalid_artifact_ids | kein Ist-Event |
| `domain.documents.document.retention.due.v2` | Aufbewahrung | Aufbewahrungsfrist erreicht | ARCHIVED/ANNULLED → gleich | QMB: Aufbewahrungsentscheidung anzeigen | version_record_id; retention_due_at; target_user_ids | kein Ist-Event |
| `domain.documents.document.retention.extended.v2` | Aufbewahrung | QMB verlängert Aufbewahrung | ARCHIVED/ANNULLED → gleich | QMB: Fälligkeitsaufgabe aktualisieren | version_record_id; old_due_at; new_due_at; reason | kein Ist-Event |
| `domain.documents.workflow.comment.synced.v2` | Kommentare | Word-Kommentare aus DOCX synchronisiert | DRAFT → DRAFT | Editor/Workflowbeteiligte: Kommentaransicht aktualisieren | version_record_id; artifact_id; actor_user_id; created_count; updated_count; missing_count | domain.documents.workflow.comment.synced.v1 |
| `domain.documents.workflow.comment.created.v2` | Kommentare | PDF-Kommentar erstellt | IN_REVIEW/IN_APPROVAL → gleich | Workflowbeteiligte: Kommentaransicht aktualisieren | comment_id; version_record_id; context; artifact_id; page_number; anchor; actor_user_id | domain.documents.workflow.comment.created.v1 |
| `domain.documents.workflow.comment.status.changed.v2` | Kommentare | Kommentarstatus geändert | Kontext → gleich | Workflowbeteiligte: Kommentarstatus aktualisieren | comment_id; old_status; new_status; note; actor_user_id | domain.documents.workflow.comment.status.changed.v1 |
| `domain.documents.workflow.comment.source_missing.v2` | Kommentare | Vorher synchronisierter Word-Kommentar fehlt in neuer DOCX | DRAFT → DRAFT | Editor/QMB: Kommentar als Quellabweichung prüfen | comment_id; old_source_key; artifact_id; detected_at | kein Ist-Event |
| `domain.documents.workflow.comment.round.bound.v2` | Kommentare | Kommentar einer Workflowinstanz/Runde zugeordnet | Kontext → gleich | Audit/Workflowbeteiligte: Rundenansicht aktualisieren | comment_id; workflow_instance_id; submission_round_id; artifact_id | kein Ist-Event |
| `domain.documents.copy.print_job.created.v2` | Kopien | Gelenkter Druckauftrag erfolgreich erzeugt | PUBLISHED → PUBLISHED | Benutzer/QMB; Audit: PDF mit Kopienkennzeichnung ausgeben | print_job_id; version_record_id; copy_numbers; actor; source_module | kein Ist-Event |
| `domain.documents.copy.issued.v2` | Kopien | Einzelne Kopie ausgegeben | PUBLISHED → PUBLISHED | QMB/Audit: Kopienregister aktualisieren | print_job_id; copy_no; issued_to optional; issued_at | kein Ist-Event |
| `domain.documents.copy.recall.required.v2` | Kopien | Nachfolgeversion veröffentlicht oder Fassung ungültig | PUBLISHED → ARCHIVED/ANNULLED/EXPIRED | QMB: Rückrufaufgabe mit Kopienliste eröffnen | old_version_record_id; reason; open_copy_numbers; target_user_ids | kein Ist-Event |
| `domain.documents.copy.recall.result.recorded.v2` | Kopien | Kopie zurückgerufen/vernichtet/nicht gefunden | ARCHIVED → ARCHIVED | QMB: Rückrufstand aktualisieren | copy_no; result; actor; reason_if_missing | kein Ist-Event |
| `domain.documents.copy.recall.closed.v2` | Kopien | Rückruf fachlich abgeschlossen | ARCHIVED → ARCHIVED | QMB/Audit: Rückrufaufgabe schließen | version_record_id; recalled; destroyed; missing; close_reason | kein Ist-Event |
| `domain.documents.copy.print.denied.v2` | Kopien | Druck nicht zulässig | nicht aktuell → gleich | Anfragender; QMB optional: Keine Kopie erzeugen | document_id; requested_version; actor; source_module; denial_reason | kein Ist-Event |
| `domain.documents.access.denied.v2` | Zugriff | Geschützte/historische Fassung angefordert | APPROVED/EXPIRED/ARCHIVED/ANNULLED → gleich | Anfragender; Security/Audit optional: Zugriff verweigern | document_id; version_record_id optional; actor/source_module; purpose; reason | kein Ist-Event |
| `domain.documents.read.confirmed.v2` | Lesen/Training | Kenntnisnahme bestätigt | PUBLISHED → PUBLISHED | Training: Lesen/Schulung aktualisieren | receipt_id; user_id; document_id; version_record_id; source | domain.documents.read.confirmed.v1 |
| `domain.documents.read.session.started.v2` | Lesetracking | PDF-Lesesitzung begonnen | PUBLISHED → PUBLISHED | Training/Readmodel: Fortschritt erfassen | session_id; user_id; version_record_id; artifact_id; total_pages | domain.documents.read.session.started.v1 |
| `domain.documents.read.session.incomplete.v2` | Lesetracking | Sitzung unvollständig beendet | PUBLISHED → PUBLISHED | Training/User: Offene Kenntnisnahme anzeigen | session_id; missing_pages; page_seconds | domain.documents.read.session.incomplete.v1 |
| `domain.documents.read.session.completed.v2` | Lesetracking | Sitzung vollständig abgeschlossen | PUBLISHED → PUBLISHED | Training/User: Kenntnisnahme erzeugen/anzeigen | session_id; completed_pages; duration; receipt_id optional | domain.documents.read.session.completed.v1 |
| `domain.documents.module_role.assigned.v2` | Berechtigung | Documents-Modulrolle vergeben | — → — | Betroffener Benutzer/QMB: Eligibility aktualisieren | user_id; module_role_id; assigned_by; optional approval_id | kein Documents-Event |
| `domain.documents.module_role.revoked.v2` | Berechtigung | Documents-Modulrolle entzogen | — → — | Betroffener Benutzer/QMB: Eligibility entfernen | user_id; module_role_id; revoked_by; reason | kein Documents-Event |
| `domain.documents.module_role.revocation_blocked.v2` | Berechtigung | Entzug wegen aktiver Zuweisung blockiert | — → — | QMB/Usermanagement: Ersatzprozess anzeigen | user_id; module_role_id; blocking_workflow_ids | kein Ist-Event |

## Übergänge mit zwingendem Aufgabenrouting

- `DRAFT → IN_REVIEW`: Prüfaufgabe an konkret zugewiesenen Reviewerpool.
- `DRAFT → IN_APPROVAL`: Freigabeaufgabe an konkret zugewiesenen Approverpool.
- `DRAFT → APPROVED`: Publikationsaufgabe an Publisher/QMB, sofern das Profil diesen Direktpfad erlaubt.
- `IN_REVIEW → IN_APPROVAL`: Reviewaufgaben schließen, Freigabeaufgaben eröffnen.
- `IN_REVIEW → APPROVED`: Reviewaufgaben schließen, Publikationsaufgabe eröffnen.
- `IN_REVIEW → DRAFT`: Reviewaufgaben schließen, Korrekturaufgabe an Owner/Editor.
- `IN_APPROVAL → APPROVED`: Freigabeaufgaben schließen, Publikationsaufgabe eröffnen.
- `IN_APPROVAL → DRAFT`: Freigabeaufgaben schließen, Korrekturaufgabe an Owner/Editor.
- `APPROVED → DRAFT`: Publikationsaufgabe schließen, Korrekturaufgabe an Owner/Editor.
- `APPROVED → PUBLISHED`: aktive Fassung für Training/Registry/andere Module publizieren.
- `PUBLISHED → ARCHIVED` bei Nachfolgepublikation: aktive Vorgängerprojektion entfernen und gegebenenfalls Kopienrückruf eröffnen.
- `PUBLISHED → EXPIRED`: aktiven Zugriff entziehen und QMB-Folgeaufgabe eröffnen.
- `EXPIRED → PUBLISHED`: Zugriff wieder aktivieren und Fristprojektionen aktualisieren.
- `beliebig → ARCHIVED/ANNULLED`: offene Aufgaben schließen und Zugriff entziehen.
