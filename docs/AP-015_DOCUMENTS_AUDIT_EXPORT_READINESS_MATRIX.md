# AP-015 Documents-Audit-Export-Readiness-Matrix

## Status
- Arbeitspaket: AP-015
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Event-Schema-Änderungen: nein
- Audit-Export-Implementierung: nein
- Migration: nein

## Kontext
- Bezug auf AP-006/AP-006A: Actor-Qualität muss für MVP-Audit-Exports getrennt als `belastbar`, `eingeschränkt` oder `legacy` bewertet werden. Correlation/Causation ersetzen keinen Actor.
- Bezug auf AP-009/AP-011: Documents-Workflow, Read-Receipt, Kommentare, technische Artefaktfolgeprozesse und Signatur-nahe Ereignisse haben unterschiedliche Actor- und Event-Reifegrade.
- Bezug auf AP-012: Owner-/`system`-Fallbacks dürfen nicht als belastbarer AuditActor erscheinen. Technische `system`-Folgeprozesse müssen gesondert dargestellt werden.
- Bezug auf AP-013/AP-014: Documents-nahe Events erzeugen aktuell überwiegend nur Einzel-/Default-Correlation, setzen keine Causation und AuditLogger-Zeilen besitzen keine Correlation-/Causation-Felder. Für MVP-Nachweisketten sind Actor-Status und Kettenstatus getrennt zu bewerten.

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` zur Existenzprüfung von `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`.
  - `ReadFile` für `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md`, `.cursor/rules/00-agent-workflow.mdc`, `docs/AP-006_AUDIT_ACTOR_ADR.md`, `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`, `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`, `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md`, `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`, `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`, `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md`, `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md`, `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` und `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`.
  - `rg` in `modules/documents` nach `EventEnvelope.create`, `publish_event`, `_publish`, `emit_audit`, `_emit_audit`, `audit_logger.emit`, `domain.documents`, `actor_user_id`, `actor_role`, `correlation_id`, `causation_id`, `audit_id`, `SOURCE_PDF`, `RELEASED_PDF`, `read.session`, `comment.*`, `signature`, `signer_user`, `system`, `unknown` und `owner_user_id`.
  - `rg` in `modules/signature` nach Documents-nahen Signaturereignissen, `signer_user`, `domain.signature`, `audit_logger.emit`, `actor_user_id`, `correlation_id` und `causation_id`.
  - `rg` in `qm_platform/events` und `qm_platform/logging` nach EventEnvelope-, AuditLogger-, LogQuery- und Export-Hilfsfunktionen.
  - `rg` in `interfaces/cli/commands/documents_commands.py` und `interfaces/pyqt` nach Documents-Kontext-/Actor-/Signatur-/Audit-Weitergabe.
  - `rg` in `tests/*documents*` und `tests/**/documents*` nach Documents-Event-/Actor-/Read-/Signatur-/Legacy-Funden.
  - `ReadFile` zentraler Hotspots in `modules/documents/service.py`, `modules/documents/workflow_use_cases.py`, `modules/documents/pdf_read_tracking_service.py`, `modules/documents/comment_service.py`, `modules/documents/comment_sync_service.py`, `modules/documents/eventing.py`, `modules/signature/signature_execute_ops.py`, `qm_platform/events/event_envelope.py`, `qm_platform/logging/audit_logger.py` und `qm_platform/logging/log_query_service.py`.
- Geprüfte Bereiche:
  - `modules/documents/*`
  - `modules/signature/*` nur Documents-nah
  - `qm_platform/events/*`
  - `qm_platform/logging/*`
  - `interfaces/cli/commands/documents_commands.py`
  - relevante PyQt-Documents-/Audit-/Signatur-Kontextweitergabe
  - `tests/*documents*`
  - `tests/**/documents*`
  - freigegebene ADR-/Inventar-/Roadmap-/Regeldateien
- Ausgeschlossene Bereiche:
  - Keine Backend-Feature-Routen vertieft, weil keine Documents-Backend-Exportimplementierung freigegeben ist.
  - Keine API-/Event-Schema-/DTO-Bewertung als Umsetzungsspezifikation.
  - Keine Tests ausgeführt; Tests wurden nur gelesen bzw. per Suchtreffer eingeordnet.

## Zusammenfassung
- Gesamtzahl relevanter Matrixzeilen: 28
- Anzahl Kategorie A: 0
- Anzahl Kategorie B: 6
- Anzahl Kategorie C: 4
- Anzahl Kategorie D: 5
- Anzahl Kategorie E: 5
- Anzahl Kategorie F: 8

Hinweis: Die Kategorien zählen Matrixzeilen, nicht disjunkte Codezeilen. Ein Flow kann zusätzlich in Kategorie F erscheinen, wenn seine Exportfähigkeit eine Supervisor-Entscheidung benötigt.

## Kategorie A — Exportfähig belastbar

| Exportfall | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | Export-Risiko | nächster Entscheidungstyp | Begründung |
| --- | --- | --- | --- | --- | --- | --- |
| keine Produktivfundstelle | - | - | - | - | - | Kein geprüfter Documents-MVP-Fall erfüllt zugleich belastbaren Actor, belastbare Kette, verbindbares Domain-Event/Auditlog und keine bekannte blockierende Lücke. |

## Kategorie B — Eingeschränkt exportfähig

| Exportfall | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | Export-Risiko | nächster Entscheidungstyp | Begründung |
| --- | --- | --- | --- | --- | --- | --- |
| Dokument importieren / aus Template erstellen | eingeschränkt | ketten-eingeschränkt | Domain-Event vorhanden; Auditlog nicht als fachlicher Begleiteintrag erkennbar; Registry über Event-ID aktualisierbar | mittel | Implementierungspaket nötig nach Kontextentscheidung | `import_existing_pdf`, `import_existing_docx` und `create_from_template` haben verpflichtende Actor-Parameter und Events, aber Actor-Quelle ist CLI/PyQt/Adapter und Correlation/Causation wird nicht durchgereicht. |
| Metadata / Change Request | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Domain-Event vorhanden; Auditlog nicht durchgehend vorhanden/verbindbar | mittel | Implementierungspaket nötig | Metadata-Update und Change Request haben expliziten Actor und Service-Prüfung, aber Kette/Auditlog-Kopplung ist nicht belastbar. |
| Review akzeptieren / ablehnen | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | mittel | API-/Schema-Entscheidung nötig für Kettenkontext | Reviewer wird verpflichtend übergeben und service-seitig geprüft; Auditlog hat aber keine Correlation/Causation und Event/Audit sind nur über Ziel/Zeit/Action verbindbar. |
| Approval akzeptieren / ablehnen | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | mittel bis hoch | API-/Schema-Entscheidung nötig | Approver wird verpflichtend geprüft; Freigabe kann Release-PDF und Signaturfolge auslösen, aber Causation fehlt. |
| Gültigkeitsverlängerung / Jahresreview | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | mittel | Implementierungspaket nötig | `extend_annual_validity` verlangt Actor, Signatur und Reason; Kettenkontext zum Signatur-/Review-Nachweis fehlt. |
| Direkte Read-Bestätigung | eingeschränkt / unklar | ketten-eingeschränkt | Domain-Event vorhanden; Auditlog nicht erkennbar; Event-Actor ist zugleich `user_id` | hoch | Supervisor-Klärung nötig | `confirm_released_document_read` setzt `actor_user_id=user_id`; belastbar nur bei eindeutig belegter Selbst-Kenntnisnahme nach AP-010. |

## Kategorie C — Legacy-only exportierbar

| Exportfall | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | Export-Risiko | nächster Entscheidungstyp | Begründung |
| --- | --- | --- | --- | --- | --- | --- |
| Workflow-Rollenvergabe mit fehlendem Actor | legacy/eingeschränkt | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | hoch | Implementierungspaket nötig nach AP-012 | Optionaler Actor und Audit-Fallback auf Owner/`system`; ohne explizite Quelle nicht als belastbar exportierbar. |
| Workflow-Start / Editing-Abschluss / Abbruch mit Fallback | legacy/eingeschränkt | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | hoch | Implementierungspaket nötig | Interaktive Workflow-Aktionen können Owner-/`system`-Fallbacks enthalten; AP-012 stuft diese nicht als belastbaren AuditActor ein. |
| Archivierung ohne menschlichen Actor | legacy/eingeschränkt | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | hoch | Supervisor-Klärung nötig | Archivierung erlaubt `actor_user_id` optional und Audit-Fallback `system`; ob Systemarchivierung zulässig ist, bleibt offen. |
| DOCX-/Import-/Kommentar-Autoren und `unknown` | legacy | ketten-legacy | Kein belastbarer AuditActor; ggf. nur Record-/Payload-Metadaten | mittel | Migration/Legacy-Strategie nötig | DOCX-Autor und `unknown` sind Herkunftsmetadaten, keine AuditActors. Export nur als Legacy-/Importmetadatum zulässig. |

## Kategorie D — Nicht belastbar exportierbar

| Exportfall | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | Export-Risiko | nächster Entscheidungstyp | Begründung |
| --- | --- | --- | --- | --- | --- | --- |
| Read-Tracking Start / Incomplete / Completed | legacy/eingeschränkt | ketten-eingeschränkt | Domain-Events vorhanden, aber ohne Event-Actor; Auditlog nicht erkennbar | blockierend für belastbaren MVP-Audit-Export | Implementierungspaket nötig nach Supervisor-Klärung | `PdfReadTrackingService` publiziert `read.session.*` ohne `actor_user_id`; `session_id` ist kein Actor- oder Causation-Ersatz. |
| Kommentar-Erstellung / Kommentar-Status | eingeschränkt | ketten-eingeschränkt | Domain-Events vorhanden, aber Actor nur im Record, nicht im Envelope; Auditlog nicht erkennbar | hoch | API-/Schema-Entscheidung nötig | Kommentarservice nimmt Actor entgegen, publiziert ihn aber nicht als Event-Actor; Event/Record-Verbindung wäre exportseitig indirekt. |
| Kommentar-Sync | eingeschränkt/legacy | ketten-eingeschränkt | Domain-Event vorhanden; Actor nur im Payload; DOCX-Autor im Record; Auditlog nicht erkennbar | hoch | ADR oder API-/Schema-Entscheidung nötig | Sync-Actor, DOCX-Autor und Importmetadaten sind nicht sauber als Auditkette getrennt. |
| RELEASED_PDF-Erzeugung ohne eigenes Nachweisereignis | unklar / technischer Prozess | ketten-eingeschränkt | Im gelesenen Code kein eigenes Event/Audit für RELEASED_PDF-Erzeugung erkennbar | blockierend für vollständig belastbare Freigabe-Nachweiskette | Supervisor-Klärung nötig | Fachliche Approval-Entscheidung und technische Release-PDF-Erzeugung sind nicht separat nachweisbar oder kausal verbunden. |
| Auditlog-Zeilen zu Documents-Use-Cases | eingeschränkt | ketten-eingeschränkt | Auditlog vorhanden, aber ohne Correlation/Causation; Domain-Event nur heuristisch verbindbar | hoch | API-/Schema-Entscheidung nötig | `AuditLogger.emit` schreibt `audit_id`, Action, Actor, Target, Result, Reason und Zeit; keine Event-ID, Correlation oder Causation. |

## Kategorie E — Technischer Folgeprozess gesondert darzustellen

| Folgeprozess | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | Export-Risiko | nächster Entscheidungstyp | Begründung |
| --- | --- | --- | --- | --- | --- | --- |
| DOCX->PDF / `SOURCE_PDF` vor Signatur | eingeschränkt/legacy | ketten-eingeschränkt | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | hoch | Supervisor-Klärung nötig | Actor-Fallback `actor_user_id or owner_user_id or "system"` und keine Causation zum auslösenden Editing-/Signatur-Kontext. |
| RELEASED_PDF nach Approval | unklar / technischer Prozess | ketten-eingeschränkt | Kein eigenes Event/Audit im gelesenen Code | blockierend für technische Vollkette | Supervisor-Klärung nötig | Muss separat vom menschlichen Approval dargestellt werden; offenes Thema eigenes Event/Audit vs. Causation zum Approval. |
| Documents-nahe Signaturereignisse | eingeschränkt | ketten-eingeschränkt | Signatur-Domain-Events und Signatur-Audit vorhanden; nicht kausal mit Documents-Workflow verbunden | hoch | ADR nötig | Signatur-Actor ist nicht automatisch Documents-AuditActor; Signatur-Events brauchen Causation zu Workflow-Transition oder getrennte Exportspur. |
| Documents-Modul-Lifecycle | kein fachlicher Actor nötig/offen | ketten-legacy/offen | Runtime-Domain-Event vorhanden; kein fachlicher Documents-Auditfall | niedrig | keine Entscheidung nötig für MVP-Documents-Export | Als Plattform-/Runtime-Kontext separat markieren, nicht als fachlicher Documents-Nachweisfall zählen. |
| Log-Backup / Plattform-Backup | System Actor eingeschränkt/offen | ketten-legacy/offen | Auditlog vorhanden; außerhalb Documents-Workflow | mittel | Supervisor-Klärung nötig nur für Plattform-Export | Relevant wegen `system`, aber kein Documents-Workflow-Exportfall; separat ausweisen. |

## Kategorie F — Supervisor-Entscheidung nötig

| Thema | betroffene Exportfälle | Grund der Unklarheit | benötigte Entscheidung |
| --- | --- | --- | --- |
| Auditlog-Kopplung | alle auditnahen Documents-Flows | AuditLogger hat keine Correlation/Causation und keinen Event-Verweis. | Bekommt Auditlog eigene Kettenfelder, oder bleibt Verbindung exportseitig heuristisch? |
| `causation_id`-Referenz | Workflow, Release, Read, Signatur, Kommentare | AP-014 lässt offen, ob Causation auf Event-ID, Command-ID oder Use-Case-ID zeigt. | Technische Zielreferenz für Causation entscheiden. |
| Release-PDF-Nachweis | Freigabe / RELEASED_PDF | Technische Artefakterzeugung hat im gelesenen Code kein eigenes Event/Audit. | Eigenes Nachweisereignis oder Causation zum Approval-Event? |
| Read-Tracking-Quelle | Read-Tracking / Read Receipt / Kenntnisnahme | `session_id` verbindet Payloads, aber nicht Actor/Kette. | Reicht Sessiondaten als Hilfsmetadatum, oder sind Actor/Event/Causation-Felder Pflicht? |
| Workflow-Fallbacks | Rollen, Start, Editing, Abort, Archivierung | Owner/`system` kann fehlenden Actor kaschieren. | Welche Bestandspfade sind legacy, welche brauchen Actor-Pflicht? |
| Kommentar-/DOCX-Sync | Kommentar-Erstellung, Status, Sync | Actor steht teils im Record/Payload, nicht im Envelope; DOCX-Autor ist Fremdmetadatum. | Welche Kommentar-/Sync-Ereignisse sind MVP-exportrelevant und brauchen belastbaren Event-Actor? |
| Signatur-Exportgrenze | Documents-nahe Signaturereignisse | Signatur-Actor und Documents-AuditActor sind getrennt; Kausalbezug fehlt. | Teil des Documents-Exports oder separater Signatur-Export mit Verknüpfung? |
| Test-/Legacy-Einordnung | Documents-Tests und Fake-Actors | Tests sichern Verhalten, aber nicht Zielsemantik für Export. | Welche Tests sind Legacy-Sicherung, welche sollen später Zielsemantik prüfen? |

## Readiness je MVP-Documents-Flow

| MVP-Documents-Flow | Kategorie | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | Export-Risiko | nächster Entscheidungstyp |
| --- | --- | --- | --- | --- | --- | --- |
| Dokument erstellen / Import | B | eingeschränkt | ketten-eingeschränkt | Event vorhanden; Auditlog nicht vollständig verbindbar | mittel | Implementierungspaket nötig |
| Workflow-Rollenvergabe | C/F | legacy/eingeschränkt | ketten-eingeschränkt | Event+Audit nur heuristisch verbindbar | hoch | Supervisor-Klärung + Implementierungspaket nötig |
| Workflow-Start | C/F | legacy/eingeschränkt | ketten-eingeschränkt | Event+Audit nur heuristisch verbindbar | hoch | Implementierungspaket nötig |
| Editing-Abschluss | C/F | legacy/eingeschränkt | ketten-eingeschränkt | Event+Audit nur heuristisch; signaturnah | hoch | Supervisor-Klärung nötig |
| Review akzeptieren / ablehnen | B | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Event+Audit nur heuristisch verbindbar | mittel | API-/Schema-Entscheidung nötig |
| Approval akzeptieren / ablehnen | B/F | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Event+Audit nur heuristisch; Release-/Signaturfolge offen | mittel bis hoch | API-/Schema-Entscheidung nötig |
| Freigabe / Release | B/D/E | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Approval-Event vorhanden; technische Release-Folge unvollständig | hoch | Supervisor-Klärung nötig |
| RELEASED_PDF / technische PDF-Folgeprozesse | D/E/F | unklar / technischer Prozess | ketten-eingeschränkt | kein eigenes Release-PDF-Event/Audit erkennbar | blockierend | Supervisor-Klärung nötig |
| DOCX->PDF-Sync | E | eingeschränkt/legacy | ketten-eingeschränkt | Event+Audit vorhanden, aber Fallback und keine Causation | hoch | Supervisor-Klärung nötig |
| Archivierung / Abbruch | C/F | legacy/eingeschränkt | ketten-eingeschränkt | Event+Audit nur heuristisch verbindbar | hoch | Supervisor-Klärung nötig |
| Gültigkeitsverlängerung / Jahresreview | B | eingeschränkt bis belastbar nach Quellklassifikation | ketten-eingeschränkt | Event+Audit nur heuristisch verbindbar | mittel | Implementierungspaket nötig |
| Read-Tracking / Read Receipt / Kenntnisnahme | B/D/F | unklar/eingeschränkt/legacy je Pfad | ketten-eingeschränkt | Direct Confirm mit Event; Tracked Read ohne Event-Actor/Auditlog | blockierend | Supervisor-Klärung + Implementierungspaket nötig |
| Kommentar-Erstellung / Kommentar-Status / Kommentar-Sync | D/F | eingeschränkt/legacy | ketten-eingeschränkt | Events vorhanden, aber Actor/Kette/Auditlog unzureichend | hoch | API-/Schema-Entscheidung nötig |
| Documents-nahe Signaturereignisse | E/F | eingeschränkt | ketten-eingeschränkt | Signatur-Event/Audit vorhanden, aber nicht mit Documents kausal verbunden | hoch | ADR nötig |
| Auditlog-Zeilen zu Documents-Use-Cases | D/F | abhängig vom übergebenen Actor; oft eingeschränkt | ketten-eingeschränkt | Auditlog vorhanden; Domain-Event nur heuristisch verbindbar | hoch | API-/Schema-Entscheidung nötig |

## Event-/Auditlog-Readiness-Matrix

| Quelle | aktueller Beitrag | Verbindbarkeit | Readiness | Risiko |
| --- | --- | --- | --- | --- |
| Documents-Domain-Events | Tragen `event_id`, `occurred_at_utc`, Default-`correlation_id`, Payload und teils `actor_user_id`. | Ohne durchgereichte Correlation/Causation nur innerhalb einzelner Events sicher. | eingeschränkt | Default-Correlation kann fälschlich als Nachweiskette gelesen werden. |
| Documents-Auditlog | Trägt Action, Actor, Target, Result, Reason und Timestamp. | Ohne Event-ID/Correlation/Causation nur heuristisch mit Domain-Events verbindbar. | eingeschränkt | Export könnte Event/Audit-Zusammenhang zu belastbar darstellen. |
| Registry / Readmodel | Speichert letzte Event-ID/Actor/Zeit bzw. Registry-Update-Verweis. | Nützlich als letzter Zustand, aber keine vollständige Auditkette. | eingeschränkt | Readmodel-Zustand kann Historie nicht ersetzen. |
| Read-Tracking-Sessiondaten | Enthält `session_id`, User, Dokumentversion, Page-Dwell und Completion. | Fachlich hilfreich, aber ohne Event-Actor/Causation. | eingeschränkt/legacy | Sessiondaten können Actor-Nachweis nicht allein tragen. |
| Signatur-Domain-Events | Tragen Signatur-Actor (`signer_user`) und Signaturergebnis. | Nicht kausal mit Documents-Transition verbunden. | eingeschränkt | Signatur-Actor kann mit AuditActor verwechselt werden. |
| Bestehende CSV/PDF-Audit-Exporte | Exportieren vorhandene Auditlog-Felder. | Keine fachliche Documents-Nachweiskette. | legacy/eingeschränkt | Bestehender Log-Export ist kein belastbarer Documents-MVP-Audit-Export. |

## Tests, Legacy, Plattform, Backend
- Tests:
  - `tests/modules/test_documents_event_contracts.py` prüft Event-Payloads, `event_id`, `occurred_at_utc` und einige Actor-Felder, aber keine Correlation/Causation-Zielsemantik.
  - Tests mit Fake-Actors wie `owner-1`, `qmb-1`, `reviewer-1` oder fehlendem Actor werden nicht als Produktivquelle gewertet.
  - Tests wurden nicht ausgeführt und nicht geändert.
- Legacy:
  - Owner-/`system`-Fallbacks, `unknown`-Importautoren und Altpfade ohne Kettenkontext dürfen nur mit sichtbarer Einschränkung exportiert werden.
  - Rückwirkende Rekonstruktion bestehender Ketten wird nicht angenommen.
- Plattform-runtime:
  - Module-Lifecycle, Log-Backup und technische Logs sind gesondert von fachlichen Documents-Nachweisfällen zu behandeln.
  - `LogQueryService` exportiert vorhandene Audit-/Techniklogs, entscheidet aber keine Documents-Exportsemantik.
- Backend:
  - Keine backendseitigen Documents-Feature-Routen oder Exportflüsse im freigegebenen Scope gefunden bzw. vertieft.
  - Backend bleibt Transport/Host und darf spätere Nachweisentscheidungen nicht fachlich treffen.

## Kritischste exportrelevante Lücken
1. `qm_platform/logging/audit_logger.py`: Auditlog-Zeilen haben keine Correlation/Causation und keinen Event-Verweis; Event/Audit-Zusammenführung ist nur heuristisch.
2. `modules/documents/pdf_read_tracking_service.py`: Read-Session-Start, Incomplete und Completed publizieren Events ohne Event-Actor und ohne Causation.
3. `modules/documents/service.py`: RELEASED_PDF-Erzeugung ist technische Freigabefolge, aber im gelesenen Code ohne eigenes Event/Audit und ohne Causation.
4. `modules/documents/service.py`: DOCX->PDF-`SOURCE_PDF`-Erzeugung nutzt Owner/`system`-Fallback und keine Causation zum Auslöser.
5. `modules/documents/workflow_use_cases.py`: Rollen, Start, Editing, Abort und Archivierung enthalten optionale Actor oder Owner-/`system`-Fallbacks.
6. `modules/documents/comment_service.py`: Kommentar-Events enthalten keinen Envelope-Actor, obwohl der Service Actor-Parameter nutzt.
7. `modules/documents/comment_sync_service.py`: Sync-Actor steht nur im Payload, DOCX-Autor im Record, Event-Actor und Causation fehlen.
8. `modules/signature/signature_execute_ops.py`: Signaturereignisse sind nicht kausal mit Documents-Workflow-Transitions verbunden.
9. `modules/documents/eventing.py`: Documents-`publish_event` reicht keine Correlation/Causation durch.
10. Bestehende Audit-CSV/PDF-Exporte sind Log-Exporte, kein fachlich belastbarer Documents-MVP-Audit-Export.

## Offene Supervisor-Entscheidungen
- Darf ein Documents-Exportfall als belastbar gelten, wenn Domain-Event und Auditlog nur heuristisch über Zeit/Ziel/Action verbindbar sind?
- Bekommt Auditlog eigene Correlation/Causation-/Event-Verweisfelder, oder erfolgt eine spätere Kopplung ausschließlich exportseitig?
- Reicht ein Domain-Event ohne Auditlog für einzelne Documents-Nachweise, oder braucht jeder MVP-Nachweisfall beide Spuren?
- Brauchen technische Folgeprozesse wie RELEASED_PDF, DOCX->PDF, Kommentar-Sync und Signatur eigene Exportzeilen?
- Sind Signaturereignisse Teil des Documents-Exports oder eines separaten Signatur-Exports mit kausaler Verknüpfung?
- Sind Read-Tracking-Sessiondaten Nachweisquelle oder nur Hilfsmetadaten für einen separat actor-belastbaren Receipt?
- Wie werden Legacy-Events ohne Actor, ohne Kette oder mit Owner-/`system`-/`unknown`-Fallback im Export konkret markiert?
- Welche Workflow-Fallback-Pfade müssen vor einem ersten belastbaren MVP-Audit-Export zwingend bereinigt oder als Legacy ausgeblendet werden?

## Nicht-Ziele
- Keine Audit-Export-Implementierung.
- Kein Exportformat.
- Keine API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Keine Migration.
- Keine Auth-/UserContext-/AuditActor-Implementierung.
- Keine Backend-Feature-Route.
- Keine Änderung an Code, Tests, bestehenden ADRs oder Inventaren.
- Keine Reparatur bestehender Findings.
- Keine Entscheidung über konkrete neue Felder, Tabellen, DTOs, Endpunkte oder Persistenzänderungen.

## Ausgeführte Gates
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Such-/Analysekommandos:
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien -> erfolgreich.
  - `rg`-Suchen in `modules/documents`, `modules/signature`, `qm_platform/events`, `qm_platform/logging`, `interfaces/cli/commands/documents_commands.py`, `interfaces/pyqt` und `tests/*documents*` -> erfolgreich.
  - `ReadFile` zentraler Documents-/Signatur-/Event-/Audit-/Export-Hotspots -> erfolgreich.
- Keine Testsuite ausgeführt, weil AP-015 ein Analyse-/Inventarpaket ist und Tests ausdrücklich ausgeschlossen sind.
- Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine neuen Exporte, Re-Exports oder Wrapper-APIs angelegt.
- Keine Auth-/UserContext-/Audit-Implementierung durchgeführt.
- Keine Backend-Feature-Routen erstellt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Kein Cleanup durchgeführt.
- Keine Event-Schema-Änderungen durchgeführt.
- Keine Audit-Export-Implementierung durchgeführt.
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob ein reines ADR-Paket `Documents-Auditlog-Event-Kopplungs-ADR` freigegeben oder zurückgestellt wird; keine Implementierung automatisch starten.
