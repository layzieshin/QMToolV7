# AP-013 Documents-Event-Correlation-Causation-Matrix

## Status
- Arbeitspaket: AP-013
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Event-Schema-Änderungen: nein
- Migration: nein

## Kontext
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert `correlation_id` als technische Klammer und `causation_id` als Verweis auf den auslösenden Vorgang. Beide erklären Ketten, ersetzen aber keinen Actor.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` empfiehlt Correlation/Causation als spätere Audit-Export-Felder, macht aber keine Implementierungsvorgabe.
- Bezug auf AP-009: `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` markiert Release-PDF-/Artefaktfolgeevents und Signatur-/Workflow-Übergänge als Nachweiskettenbedarf.
- Bezug auf AP-010: `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md` benennt Read-Session-Start, Dwell-Tracking und Completion als Kette, bei der Correlation/Causation empfohlen bleiben.
- Bezug auf AP-011: `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` zeigt, dass Documents-Events keine explizite Correlation/Causation übergeben und Signaturereignisse nicht kausal mit Documents-Workflow-Events verbunden sind.
- Bezug auf AP-012: `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md` verlangt, technische Folgeprozesse und `system`-Fälle nicht als Actor-Ersatz zu werten; Causation kann solche Folgeprozesse erklären, ersetzt aber keine Actor-Bestimmung.

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` zur Existenzprüfung von `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`.
  - `ReadFile` für `docs/MASTER_ORCHESTRATION_ROADMAP.md`, `AGENTS.md`, `.cursor/rules/00-agent-workflow.mdc`, `docs/AP-006_AUDIT_ACTOR_ADR.md`, `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`, `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`, `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`, `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` und `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md`.
  - `rg` in `modules/documents` nach `EventEnvelope.create`, `publish_event`, `_publish`, `emit_audit`, `_emit_audit`, `audit_logger.emit`, `correlation_id`, `causation_id`, `event_id`, `SOURCE_PDF`, `RELEASED_PDF`, `read.session`, `comment.synced`, `signature`, `signer_user`, `"system"`, `"unknown"` und `owner_user_id`.
  - `rg` in `modules/signature` nach `EventEnvelope.create`, `audit_logger.emit`, `correlation_id`, `causation_id`, `event_id`, `domain.signature`, `signer_user`, `"system"`, `_publish_event` und `_emit_audit`.
  - `rg` in `qm_platform/events` und `qm_platform/logging` nach `correlation_id`, `causation_id`, `event_id`, EventEnvelope- und AuditLogger-Erzeugung.
  - `rg` in `interfaces/cli/commands/documents_commands.py` und `interfaces/pyqt` nach Documents-Kontextweitergabe, Signatur, Read-/Workflow-/Archivierungsbezug und `system`.
  - `rg` in `tests/*documents*` und `tests/**/documents*` nach Documents-Events, Event-ID, Correlation/Causation, Workflow, Read-Tracking, Archivierung, Signatur, `system` und `unknown`.
  - `ReadFile` zentraler Hotspots in `qm_platform/events/event_envelope.py`, `modules/documents/eventing.py`, `qm_platform/logging/audit_logger.py`, `modules/documents/workflow_use_cases.py`, `modules/documents/service.py`, `modules/documents/pdf_read_tracking_service.py`, `modules/documents/comment_service.py`, `modules/documents/comment_sync_service.py`, `modules/documents/module.py`, `modules/signature/signature_execute_ops.py`, `modules/documents/registry_sync.py`, `modules/registry/projection_api.py`, `modules/registry/service.py`, `qm_platform/logging/log_query_service.py`, `interfaces/pyqt/widgets/audit_log_helpers.py`, `interfaces/pyqt/contributions/audit_logs_view.py` und `tests/modules/test_documents_event_contracts.py`.
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
  - Keine Implementierung, kein Cleanup, keine Event-Schema-, API-, DTO- oder Migrationsbewertung.
  - `modules/signature/*` wurde nicht als vollständiges Signatur-Inventar bewertet; nur Documents-nahe Signatur-/Folgeprozess-Abgrenzung.
  - Backend-Routen wurden nicht vertieft, weil der freigegebene Scope nur Documents-Kontextweitergabe über CLI/PyQt und keine Backend-Feature-Routen umfasst.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Gesamtzahl relevanter Matrixzeilen: 30
- Anzahl Kategorie A: 0
- Anzahl Kategorie B: 10
- Anzahl Kategorie C: 0
- Anzahl Kategorie D: 9
- Anzahl Kategorie E: 6
- Anzahl Kategorie F: 5

Hinweis: Die Kategorien zählen Matrixzeilen, nicht disjunkte Codezeilen. Einzelne Eventfamilien erscheinen bewusst in mehreren Kategorien, wenn z. B. ein Event technisch eine automatisch erzeugte `correlation_id` besitzt, aber Auditlog oder Folgeprozess keine belastbare Kette tragen.

## Kategorie A — Explizite Correlation und Causation vorhanden

| Datei | Zeile | Event/Audit/Folgeprozess | Correlation | Causation | Bewertung | Hinweis |
| --- | ---: | --- | --- | --- | --- | --- |
| keine Produktivfundstelle | - | keine Documents-nahe Event-/Audit-Erzeugung mit explizit weitergereichter `correlation_id` und `causation_id` gefunden | nein | nein | keine Kategorie-A-Funde | `EventEnvelope.create` unterstützt beide Parameter, die geprüften Documents-nahen Aufrufer setzen sie aber nicht explizit. |

## Kategorie B — Correlation vorhanden, Causation fehlt oder ist unklar

| Datei | Zeile | Event/Eventfamilie | Correlation-Quelle | Causation-Status | Nachweisketten-Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- | --- |
| `qm_platform/events/event_envelope.py` | 21-40 | `EventEnvelope.create(...)` | `correlation_id` wird automatisch erzeugt, wenn nicht übergeben | fehlt bei Default | Technische Einzel-Correlation existiert, aber keine Use-Case-/Request-Kette. | Pflichtgrad und Weitergabe später entscheiden. |
| `modules/documents/eventing.py` | 11-31 | Documents-`publish_event(...)` | indirekt automatisch über `EventEnvelope.create` | nicht übergeben | Alle Documents-Events erhalten neue Einzel-Correlation statt durchgereichter Kette. | Request-/Use-Case-Kontext später planen. |
| `modules/documents/workflow_use_cases.py` | 80/131/182/226/259/315/353/385/424/484 | Workflow-Eventfamilie | automatische EventEnvelope-Correlation je Event | nicht übergeben | Workflow-Verlauf ist über Status/Objekt nachvollziehbar, aber nicht als technische Kausalkette. | Workflow-Nachweiskette später definieren. |
| `modules/documents/service.py` | 629/658/690 | Intake-/Template-Events | automatische EventEnvelope-Correlation je Event | nicht übergeben | Import/Template-Erstellung ist nicht kausal mit späterem Workflow-Start verknüpft. | Intake-zu-Workflow-Kette im Nachweispaket kennzeichnen. |
| `modules/documents/service.py` | 514/568 | Metadata-/Change-Request-Events | automatische EventEnvelope-Correlation je Event | nicht übergeben | Nachweisnahe Änderungen sind Einzelereignisse ohne verknüpfenden Auslöser. | Exportstatus und Kettenmodell später prüfen. |
| `modules/documents/service.py` | 904 | `domain.documents.read.confirmed.v1` | automatische EventEnvelope-Correlation | nicht übergeben | Direct-Confirm-Receipt ist nicht mit Read-Session, Training-Kontext oder Request verbunden. | Read-Receipt-Kette nach AP-010 vertiefen. |
| `modules/documents/pdf_read_tracking_service.py` | 41/77/91 | `domain.documents.read.session.*.v1` | automatische EventEnvelope-Correlation je Event | nicht übergeben | `session_id` verbindet Payloads fachlich, ersetzt aber keine Event-Causation. | Read-Tracking-Kette separat planen. |
| `modules/documents/comment_service.py` | 113/139 | Kommentar-Events | automatische EventEnvelope-Correlation je Event | nicht übergeben | Kommentarrecord und Statuswechsel sind nicht kausal verknüpft. | Kommentar-/Review-Nachweiskette später einordnen. |
| `modules/documents/comment_sync_service.py` | 70/91-96 | DOCX-Kommentar-Sync-Event | automatische EventEnvelope-Correlation | nicht übergeben | DOCX-Import, Fremdautor und Sync-Actor bleiben technisch isoliert. | Import-/Sync-Causation später entscheiden. |
| `modules/signature/signature_execute_ops.py` | 47/56/99/106/248-258 | `domain.signature.sign.*.v1` Documents-nah | automatische EventEnvelope-Correlation je Signatur-Event | nicht übergeben | Signaturereignisse sind nicht kausal mit Documents-Workflow-Events verbunden. | Signatur-vs-AuditActor und Workflow-Causation später klären. |

## Kategorie C — Causation vorhanden, Correlation fehlt oder ist unklar

| Datei | Zeile | Event/Audit/Folgeprozess | Causation | Correlation | Bewertung | Hinweis |
| --- | ---: | --- | --- | --- | --- | --- |
| keine Produktivfundstelle | - | keine Documents-nahe Nutzung von `causation_id` gefunden | nein | nein | keine Kategorie-C-Funde | Der Begriff existiert im `EventEnvelope`, wird aber in den geprüften Documents-nahen Erzeugern nicht gesetzt. |

## Kategorie D — Weder Correlation noch Causation belastbar

| Datei | Zeile | Event/Audit/Folgeprozess | aktueller Zustand | Risiko | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- |
| `qm_platform/logging/audit_logger.py` | 15-27 | generischer `AuditLogger.emit(...)` | Auditzeilen enthalten `audit_id`, aber keine `correlation_id` oder `causation_id`. | Fachliche Auditzeilen sind nicht technisch mit Events verkettet. | Audit-/Event-Zusammenführung später entscheiden. |
| `modules/documents/eventing.py` | 34-48 | Documents-`emit_audit(...)` | Delegiert nur `action`, `actor`, `target`, `result`, `reason`. | Documents-Auditlog kann nicht belastbar auf Event-ID oder Causation zeigen. | AuditLogger-Kontextmodell später planen. |
| `modules/documents/workflow_use_cases.py` | 93/140/193/235/268/329/362/394/433/503 | Workflow-Auditfamilie | Auditlog-Zeilen ohne Correlation/Causation; teils Event im gleichen Use Case vorhanden. | Event und Auditlog können nur über Zeit/Ziel/Action heuristisch zusammengeführt werden. | Export darf Kette nicht als sicher behaupten. |
| `modules/documents/service.py` | 184-190 | DOCX->PDF-Source-PDF-Audit | Audit ohne Correlation/Causation, Event ohne Causation. | Technischer Folgeprozess kann isoliert erscheinen. | Folgeprozess-Causation später entscheiden. |
| `modules/documents/service.py` | 193-216 | `_ensure_release_pdf_artifact` | RELEASED_PDF-Erzeugung im gelesenen Code ohne eigenes Event/Audit. | Technische Freigabeartefakterzeugung ist nur indirekt über Freigabe-Event erkennbar. | Klären, ob eigenes Nachweisereignis oder Causation-Kopplung nötig ist. |
| `modules/documents/workflow_use_cases.py` | 512-528 | `create_new_version_after_archive` | Sync ohne Event (`event=None`) erzeugt Registry-Fallback-ID. | Neue Version nach Archiv hat keine Event-/Causation-Kette. | Produktivnähe und Auditpflicht später entscheiden. |
| `modules/documents/comment_service.py` | 113/139 | Kommentar-Event + Record | Record enthält Autor/Statusänderer, Event hat keine belastbare Kette. | Export müsste Record und Event heuristisch verbinden. | Kommentar-Export-Readiness später prüfen. |
| `modules/documents/comment_sync_service.py` | 70/91-96 | DOCX-Kommentar-Sync | Payload enthält `actor_user_id`, Envelope ohne Actor und ohne Causation. | Sync-Actor, DOCX-Autor und Folgeereignis bleiben schwer trennbar. | Kommentar-/DOCX-Sync separat planen. |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | 102/125/154 | GUI-Signatur-Placement-Audit | Adapter-Audit über AuditLogger ohne Event-/Causation-Bezug. | UI-Vorbereitungs-/Abbruchereignisse sind nicht fachlich mit Workflow-Events verkettet. | Als Adapter-Audit getrennt von Service-Audit einordnen. |

## Kategorie E — Technische Folgeprozesse mit `system` oder technischem Actor

| Datei | Zeile | Folgeprozess | Actor-/Systembezug | Causation-Status | Bewertung | spätere Behandlung |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/documents/service.py` | 148-190 | DOCX->PDF-Erzeugung für `SOURCE_PDF` vor Signatur | Audit-Actor `actor_user_id or state.owner_user_id or "system"` | nicht gesetzt | `system`/Owner-Fallback wäre nur mit auslösendem Workflow-Event erklärbar; aktuell isoliert/eingeschränkt. | AP-012-Fallback-Policy plus Causation-Pflichtgrad anwenden. |
| `modules/documents/service.py` | 193-216 | RELEASED_PDF-Erzeugung nach Freigabe | technischer Folgeprozess ohne eigenen Actor | nicht gesetzt | Fachliche Freigabe und technisches Artefakt sind nicht als Eventkette getrennt. | Entscheiden, ob eigenes Event oder Causation zum Approval-Event nötig ist. |
| `modules/documents/workflow_use_cases.py` | 424/433-438 | Archivierung | Audit-Fallback `actor_user_id or "system"` | nicht gesetzt | `system`-Archivierung wäre ohne Causation nicht von fehlendem Actor unterscheidbar. | Supervisor-Entscheidung aus AP-012 offen. |
| `modules/documents/module.py` | 74-87 | Documents-Module-Lifecycle | systemnaher Runtime-Vorgang ohne Actor | nicht gesetzt | Runtime-Event ist technisch plausibel, aber nicht fachlicher Documents-Actor. | Plattform-runtime separat markieren, nicht als Workflow-Verstoß werten. |
| `modules/signature/signature_execute_ops.py` | 223-258 | Signatur-Audit/-Events | `request.signer_user or "system"` im Audit; `signer_user` im Event | nicht gesetzt | Signaturfehler/-erfolg ist nicht kausal an Documents-Workflow-Transition gekoppelt. | Signatur-/Workflow-Causation separat entscheiden. |
| `qm_platform/logging/log_backup_service.py` | 34/60-74 | Log-Backup | Default `actor="system"` | keine Causation-Felder | Plattform-Backup ist außerhalb Documents-Workflow, aber System-Actor-Policy-relevant. | Plattform-/Runtime-Fund separat markieren. |

## Kategorie F — Supervisor-Entscheidung nötig

| Bereich | Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | --- | --- | --- |
| Workflow-Eventkette | `modules/documents/workflow_use_cases.py` Eventfamilie | Automatische Einzel-Correlation existiert, aber keine durchgehende Workflow-/Request-Correlation und keine Causation. | Sind `correlation_id`/`causation_id` für MVP-Documents-Workflow-Events Pflicht oder nur empfohlen? |
| Technische Artefakterzeugung | `modules/documents/service.py` DOCX->PDF und RELEASED_PDF | Folgeprozesse sind fachlich relevant, aber nicht kausal an Workflow-Event gebunden. | Eigenes Nachweisereignis, System Actor oder Causation zum auslösenden Event? |
| Read-Tracking | `modules/documents/pdf_read_tracking_service.py` `read.session.*` | `session_id` verbindet Payloads, aber nicht als Event-Correlation/Causation. | Reicht `session_id` als fachliches Kettenmerkmal, oder braucht MVP Event-Causation? |
| Signatur-nahe Documents-Flows | `modules/signature/signature_execute_ops.py` und PyQt-SignRequest-Erzeugung | Signaturereignisse haben eigene Eventkette, aber keine Causation zum Documents-Workflow. | Müssen Workflow-Actor, Signatur-Actor und technische Signaturereignisse kausal verbunden werden? |
| Tests/Legacy | `tests/modules/test_documents_event_contracts.py`, `tests/modules/test_documents_event_order.py` | Tests prüfen Event-ID/Payload/Reihenfolge, aber nicht Correlation/Causation; teils Actor-freie Testaufrufe. | Welche Tests sind Legacy-Sicherung, welche sollen später Zielsemantik prüfen? |

## Plattform-, Runtime-, Backend- und Test-Einordnung
- Plattform/EventEnvelope:
  - `EventEnvelope.create` erzeugt immer eine `event_id` und eine `correlation_id`, falls keine Correlation übergeben wird.
  - `causation_id` existiert als Feld, bleibt aber ohne explizite Übergabe `None`.
  - Diese Hilfstypen allein sind kein Verstoß; relevant ist, dass Documents-nahe Aufrufer keine belastbare Kette weitergeben.
- Plattform/Logging:
  - `AuditLogger.emit` hat keine Correlation-/Causation-Felder.
  - `LogQueryService` liest und exportiert vorhandene Audit-/Techniklogs; es erzeugt keine Ketten und entscheidet keine Semantik.
  - `LogBackupService` ist Plattform-/Runtime-nah und nur wegen `system` und Auditlog-Relevanz als separater Hinweis aufgenommen.
- Registry:
  - `registry_sync` und `RegistryProjectionApi` übernehmen `event` und speichern daraus `last_update_event_id`.
  - `RegistryService.apply_documents_state` erzeugt bei fehlendem Event eine synthetische ID `state-sync:<document_id>:<version>:<status>`.
  - Das ist eine technische Referenz auf den letzten Update-Auslöser, aber keine Correlation/Causation-Kette.
- GUI/CLI:
  - CLI und PyQt transportieren Actor-/Signatur-/Workflow-Kontext, aber keine `correlation_id` oder `causation_id`.
  - PyQt-Audit-/Anzeige-Funde sind getrennt einzuordnen; Anzeige von `last_event_id` ist keine Kettenbildung.
- Backend:
  - Keine backendseitigen Documents-Feature-Routen im geprüften Scope vertieft; keine AP-013-relevante Backend-Kette bewertet.
- Tests:
  - `tests/modules/test_documents_event_contracts.py` prüft Event-Payload, `event_id` und `occurred_at_utc`, aber nicht `correlation_id` oder `causation_id`.
  - `tests/modules/test_documents_event_order.py` nutzt `EventEnvelope.create` in einem Service-Double und sichert Persistenz-vor-Publish-Reihenfolge, nicht Kettensemantik.
  - Migration-/Presenter-Tests enthalten `last_event_id` oder Anzeige-/Legacyfelder; sie etablieren keine Produktiv-Correlation.

## Kritischste Funde
1. `modules/documents/eventing.py`: Documents-`publish_event` nimmt keine `correlation_id`/`causation_id` entgegen und erzeugt dadurch je Event nur Default-Correlation.
2. `modules/documents/workflow_use_cases.py`: Workflow-Ereignisse und Workflow-Auditlog-Zeilen sind nicht über Event-ID, Correlation oder Causation belastbar verbunden.
3. `modules/documents/service.py`: `_ensure_release_pdf_artifact` ist technische Folge der Freigabe, aber im gelesenen Code ohne eigenes Event/Audit und ohne Causation.
4. `modules/documents/service.py`: `_ensure_source_pdf_artifact_for_signing` erzeugt ein SOURCE_PDF-Folgeevent/Audit ohne Causation zum Editing-/Signatur-Auslöser.
5. `modules/documents/pdf_read_tracking_service.py`: Read-Session-Start, Incomplete und Completed verwenden `session_id`, aber keine Event-Causation und keinen durchgereichten Request-/Use-Case-Kontext.
6. `modules/signature/signature_execute_ops.py`: Signaturereignisse sind nicht kausal mit Documents-Workflow-Events verbunden.
7. `qm_platform/logging/audit_logger.py`: Auditlog-Zeilen haben keine Correlation/Causation, wodurch Event-/Audit-Zusammenführung nur heuristisch möglich ist.
8. `modules/documents/comment_service.py` und `comment_sync_service.py`: Kommentar-/DOCX-Sync-Ketten sind weder eventseitig noch auditseitig belastbar verkettet.
9. `modules/registry/service.py`: Registry speichert `last_update_event_id`, erzeugt aber bei fehlendem Event synthetische `state-sync:*`-IDs ohne Correlation/Causation-Semantik.
10. Tests sichern Event-Grundform und Reihenfolge, aber nicht Correlation/Causation; das ist kein Fehler, aber ein späterer Test-Gap für Zielsemantik.

## Auswirkungen auf Audit-Export / Nachweispaket
- Tragfähig wirkt aktuell nur die technische Existenz von `event_id`, `occurred_at_utc` und automatisch erzeugter `correlation_id` pro Event.
- Eingeschränkt bleibt:
  - Correlation wird nicht als Use-Case-/Request-Kette durchgereicht.
  - Causation wird in Documents-nahen Event-/Audit-Erzeugern nicht gesetzt.
  - AuditLogger-Zeilen haben keine Kettenfelder.
  - Technische Folgeprozesse können nicht belastbar als Folge eines bestimmten fachlichen Events dargestellt werden.
- Für ein belastbares Nachweispaket müssen spätere Pakete mindestens klären:
  - ob und wann Correlation/Causation Pflicht werden,
  - wie Event- und Auditlog-Zeilen zusammengeführt werden,
  - wie technische Folgeprozesse mit `system` oder Signaturereignissen kausal erklärt werden,
  - wie Read-Tracking-`session_id` gegenüber Event-Causation bewertet wird.

## Nicht-Ziele
- Keine Implementierung.
- Keine API-Änderung.
- Keine Event-Schema-Änderung.
- Keine DTO-, Contract-, Re-Export- oder Wrapper-API-Änderung.
- Keine Auth-/UserContext-/Audit-Implementierung.
- Keine Backend-Feature-Route.
- Keine Migration.
- Keine Dependency-Änderung.
- Kein Cleanup.
- Keine Reparatur bestehender Findings aus AP-002 bis AP-012.
- Keine Entscheidung über konkrete neue Felder, Signaturen, Transportcontainer oder Persistenzänderungen.
- Keine Testsuite-Ausführung und keine Teständerung.

## Offene Supervisor-Entscheidungen
- Sind `correlation_id` und `causation_id` für alle MVP-Documents-Workflow-Events Pflicht oder nur für technische Folgeprozesse und Nachweisketten?
- Soll AuditLogger künftig Event-/Request-Kontext aufnehmen, oder bleibt Event/Audit-Zusammenführung exportseitig heuristisch?
- Braucht RELEASED_PDF-Erzeugung ein eigenes Event/Audit oder reicht Causation zum Approval-Event?
- Muss DOCX->PDF-Erzeugung vor Signatur als Systemfolgeprozess oder als Teil der menschlichen Workflow-Aktion erscheinen?
- Reicht `session_id` für Read-Tracking als fachliche Klammer, oder braucht die Eventkette explizite Correlation/Causation?
- Wie werden Signaturereignisse kausal mit Documents-Workflow-Transitions verbunden, ohne Signatur-Actor und AuditActor zu vermischen?
- Welche Tests sollen später Zielsemantik für Correlation/Causation absichern?

## Vorschlag für spätere Paketierung

| Paketname | Ziel | Scope | Risiko | erforderliche Vorentscheidung |
| --- | --- | --- | --- | --- |
| Documents-Correlation-Causation-Policy-ADR | Pflichtgrad, Begriffe und Mindestketten für Workflow, Read-Tracking, Signatur und Artefaktfolgeprozesse fachlich entscheiden. | Reine ADR, keine Umsetzung. | mittel, weil spätere Event/API-Grenzen betroffen sein können. | Ob MVP-Export harte Kettenfelder verlangt. |
| Documents-Audit-Export-Readiness-Matrix | Event-, Audit-, Registry- und Readmodel-Quellen je Nachweiszeile mit `belastbar/eingeschränkt/legacy` klassifizieren. | Analyse/Inventar, keine Exportimplementierung. | mittel. | Nachweisstatus und Correlation/Causation-Pflichtgrad. |
| Documents-Workflow-Actor-Implementierungsvorbereitung | Nur nach Policy: kleinste Umsetzungsvorbereitung für Actor/Causation an genau einem Workflow-Slice. | Vorbereitung, keine Implementierung ohne weitere Freigabe. | mittel bis hoch. | Actor-Pflicht, System Actor und Causation-Policy entschieden. |

Keines dieser Pakete ist mit AP-013 gestartet.

## Ausgeführte Gates
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/DTO-/Migrationsentscheidung enthalten.
- Such-/Analysekommandos:
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien -> erfolgreich.
  - `rg`-Suchen in `modules/documents`, `modules/signature`, `qm_platform/events`, `qm_platform/logging`, `interfaces/cli/commands/documents_commands.py`, `interfaces/pyqt` und `tests` -> erfolgreich.
  - `ReadFile` zentraler Event-/Audit-/Registry-/Read-/Signatur-Hotspots -> erfolgreich.
- Keine Testsuite ausgeführt, weil AP-013 ein Analyse-/Inventarpaket ist und keine Codeänderungen vorgenommen wurden.
- Keine Linter oder Typechecker ausgeführt, weil keine solchen Tools für dieses Paket gefordert sind und keine erfundenen Tools verwendet werden sollen.

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
- Keine bestehenden Findings repariert.
- Keine bestehende Dokumentation geändert.
- Nur `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob ein reines ADR-Paket `Documents-Correlation-Causation-Policy-ADR` freigegeben oder zurückgestellt wird; keine Implementierung automatisch starten.
