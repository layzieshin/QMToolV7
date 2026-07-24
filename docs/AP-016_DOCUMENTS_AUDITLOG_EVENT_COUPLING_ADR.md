# AP-016 Documents-Auditlog-Event-Kopplungs-ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Audit-Export-Implementierung: nein
- Exportformat-Entscheidung: nein
- Migration: nein

## Kontext
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert AuditActor als explizit bestimmte handelnde Instanz und trennt Actor, Target, System Actor, Unknown, Correlation und Causation.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` verlangt sichtbare Actor-Qualität für MVP-Audit-Exports.
- Bezug auf AP-009/AP-011: Documents-Workflow, Read-Receipt, Kommentare, Signatur-nahe Ereignisse und technische Artefaktfolgeprozesse haben unterschiedliche Actor- und Event-Reifegrade.
- Bezug auf AP-012: Owner-/`system`-Fallbacks dürfen nicht als belastbarer AuditActor erscheinen; technische `system`-Folgeprozesse müssen getrennt erklärbar bleiben.
- Bezug auf AP-013/AP-014: Documents-nahe Events erzeugen aktuell überwiegend Einzel-/Default-Correlation und keine Causation; Auditlog-Zeilen besitzen keine Correlation-/Causation-Felder.
- Bezug auf AP-015: Kein geprüfter Documents-MVP-Fall ist aktuell vollständig exportfähig belastbar, weil Actor-Readiness, Ketten-Readiness und Event-/Auditlog-Verbindbarkeit nicht gleichzeitig erfüllt sind.

## Begriffe
- **Domain-Event**: Technisches/fachliches Ereignis im Eventsystem, das Modulzustand, Integration, Readmodels oder Folgeprozesse informieren kann. Ein Domain-Event ist nicht automatisch ein vollständiger Auditnachweis.
- **Auditlog-Eintrag**: Protokollierter Nachweiseintrag über eine Aktion mit Action, Actor, Target, Ergebnis, Grund und Zeitstempel. Ein Auditlog-Eintrag ist nicht automatisch mit einem Domain-Event verkettet.
- **Auditrelevanter Documents-Use-Case**: Documents-Service-Use-Case mit Nachweischarakter, z. B. Workflow-Transition, Review, Approval, Release, Read Receipt, Kommentarstatus oder technische Folge eines fachlichen Auslösers.
- **Service-Nachweisentscheidung**: Fachliche Entscheidung an der Documents-Service-Grenze, welche Handlung ausgeführt wurde, wer Actor ist, was Target/Subject ist, ob ein System-/Folgeprozess vorliegt und welcher Nachweisstatus gilt. Dies ist ein Policy-Begriff, keine API oder Implementierung.
- **Kopplung**: Nachvollziehbare Beziehung zwischen Domain-Event, Auditlog-Eintrag, technischem Folgeprozess und ggf. Readmodel/Registry-Status.
- **Kettenstatus**: Bewertung nach AP-014, z. B. `kettenbelastbar`, `ketten-eingeschränkt` oder `ketten-legacy`.

## Entscheidung
Empfohlene Zielentscheidung:

Domain-Events und Auditlog-Einträge bleiben getrennte Nachweisartefakte mit unterschiedlichen Zwecken. Domain-Events beschreiben fachliche oder technische Ereignisse für Integration, Readmodel, Folgeprozesse und Zustandsnachvollzug. Auditlog-Einträge beschreiben auditrelevante Handlungen mit Actor, Target, Ergebnis und Begründung. Keines der beiden Artefakte ist pauschal die allein führende fachliche Wahrheit.

Für auditrelevante Documents-MVP-Use-Cases sollen Domain-Event und Auditlog grundsätzlich konsistent aus derselben Service-Nachweisentscheidung entstehen, sofern der Use Case sowohl Zustand/Folgeprozesse als auch Auditnachweis betrifft. Die führende fachliche Quelle ist die service-seitige Nachweisentscheidung, nicht das spätere Eventobjekt und nicht die spätere Auditlog-Zeile.

Wenn ein Use Case nur ein Artefakt erzeugt, muss die Einschränkung sichtbar bleiben: ein Domain-Event ohne Auditlog ist kein vollständiger Auditlog-Nachweis; ein Auditlog ohne belastbare Event-/Kettenkopplung ist nicht automatisch `kettenbelastbar`. Bestehende Documents-Funde ohne Kopplung bleiben `ketten-eingeschränkt` oder `ketten-legacy`, bis ein separates Implementierungspaket freigegeben wird.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Auditlog-Schema, kein Exportformat und keine Implementierung.

## Verhältnis Domain-Event zu Auditlog
- Zielregel:
  - Domain-Event und Auditlog bleiben getrennte Artefakte.
  - Auditlog darf Domain-Events nicht still widersprechen.
  - Domain-Events dürfen Auditlog nicht still überstimmen.
  - Beide sollen für auditrelevante Documents-Use-Cases konsistent aus derselben service-seitigen Actor-/Target-/Kettenentscheidung entstehen.
- Audit-relevante Use Cases sollen grundsätzlich beides erzeugen, wenn:
  - eine fachliche Workflow-Entscheidung getroffen wird,
  - ein User eine Nachweishandlung ausführt,
  - ein technischer Folgeprozess als Teil einer Nachweiskette erklärt werden muss,
  - ein späterer MVP-Audit-Export die Handlung vollständig erklären soll.
- Ausnahmen bzw. eingeschränkte Fälle:
  - Reine Runtime-/Lifecycle-Events dürfen nur Domain-Event sein, solange sie keine fachliche Documents-Handlung behaupten.
  - Reine UI-/Adapter-Audits dürfen getrennt von fachlichem Documents-Service-Audit bleiben.
  - Legacy-/Importfälle dürfen als eingeschränkt oder legacy markiert bleiben.
  - Bestehende Log-CSV/PDF-Exports sind Logauszüge, kein fachlich vollständiger Documents-MVP-Audit-Export.

## Kopplungsziel
- Zielregel:
  - Domain-Event und Auditlog sollen für denselben auditrelevanten Use Case nachvollziehbar als zusammengehörig erkennbar sein.
  - Die Kopplung soll nicht nur über Zeitstempel, Zieltext oder Action-Name geraten werden müssen, wenn `kettenbelastbar` behauptet wird.
  - Die Kopplung soll Kettenstatus, Actor-Status und technische Folgeprozesse getrennt bewertbar machen.
- Geeignete Zielrichtungen, ohne konkrete Feldentscheidung:
  - gemeinsamer Correlation-Kontext für denselben Use-Case-Aufruf,
  - Causation vom Folgeprozess zum fachlichen Auslöser,
  - spätere explizite Referenz zwischen Auditlog und Domain-Event,
  - spätere Use-Case-/Command-Referenz als Klammer,
  - exportseitige Kopplung nur dann, wenn sie auf belastbaren Daten statt Heuristik beruht.
- Ausdrücklich offen:
  - ob Auditlog später eigene Correlation/Causation-Felder bekommt,
  - ob Auditlog auf Domain-Event-ID verweist,
  - ob Domain-Events auf Auditlog-Einträge verweisen,
  - ob eine spätere Use-Case-ID oder Command-ID die Klammer wird,
  - welche technische Referenz `causation_id` konkret verwendet.

## Actor-Konsistenz
- Zielregel:
  - AuditActor wird service-seitig bestimmt und darf nicht getrennt aus Domain-Event, Auditlog, Target, Owner, GUI-/CLI-Zustand oder technischem Fallback geraten werden.
  - Wenn Domain-Event und Auditlog denselben fachlichen Use Case beschreiben, müssen Actor-Identität, Actor-Quelle und Actor-Nachweisstatus konsistent erklärbar sein.
  - Unterschiede zwischen Event-Actor und Auditlog-Actor müssen fachlich begründet und sichtbar klassifiziert werden, z. B. bei technischem Folgeprozess, Signatur-Actor oder System Actor.
- Unzulässig im Zielbild:
  - Event hat menschlichen Actor, Auditlog fällt auf Owner oder `system` zurück.
  - Auditlog hat freien Actor-String, Event hat keinen Actor, und der Export stellt beides als belastbar dar.
  - Zieluser, Read-Receipt-User, Reviewer/Approver-Zuordnung oder DOCX-Autor wird still als AuditActor übernommen.
  - Signatur-Actor wird automatisch als Documents-AuditActor gelesen.
- Legacy-Bewertung:
  - Bestehende freie Actor-Strings, Owner-/`system`-Fallbacks, Event-ohne-Actor-Fälle und Payload-only-Actor bleiben eingeschränkt oder legacy.

## Ketten-Konsistenz
- Zielregel:
  - Correlation/Causation und Kettenstatus müssen zwischen Domain-Event und Auditlog konsistent bewertbar sein.
  - Auditlog ohne belastbaren Kettenbezug darf nicht still als `kettenbelastbar` gelten.
  - Domain-Event mit Default-Correlation, aber ohne durchgereichten Use-Case-Kontext, darf nicht als vollständige Nachweiskette gelten.
- Für neue Documents-MVP-Nachweisketten gilt als Ziel:
  - Domain-Event, Auditlog und technische Folgeprozesse teilen einen erklärbaren Zusammenhang.
  - Folgeprozesse zeigen auf ihren fachlichen Auslöser oder auf einen später freigegebenen Use-Case-/Command-Kontext.
  - Readmodel-/Registry-Verweise dürfen die Kette ergänzen, ersetzen aber nicht automatisch Auditlog-/Event-Kopplung.
- Bestehender Zustand:
  - `EventEnvelope.create` erzeugt `event_id` und Default-`correlation_id`, aber Documents-Aufrufer reichen keine explizite Correlation/Causation durch.
  - `AuditLogger.emit` schreibt `audit_id`, Action, Actor, Target, Result, Reason und Timestamp, aber keine Kettenreferenz.
  - Daher ist die aktuelle Verbindung meist nur heuristisch und als `ketten-eingeschränkt` einzuordnen.

## Documents-MVP-Fälle

| Fall | Zielverhältnis Event/Auditlog | Actor-Konsistenz | Ketten-Konsistenz | Policy-Bewertung |
| --- | --- | --- | --- | --- |
| Workflow-Transitions: Rollen, Start, Editing, Abort | Grundsätzlich Event + Auditlog aus derselben Service-Nachweisentscheidung. | Optionaler Actor und Owner/`system`-Fallback bleiben legacy/eingeschränkt. | Causation/Correlation für Kette erforderlich, wenn Workflow-Verlauf als Nachweis dient. | Ziel: beides konsistent; Bestand eingeschränkt/legacy. |
| Review akzeptieren / ablehnen | Event + Auditlog sollen denselben Reviewer und dieselbe fachliche Entscheidung erklären. | Reviewer-Actor wirkt service-nah tragfähig, Quelle bleibt zu klassifizieren. | Ohne Kopplung nur heuristisch verbindbar. | Eingeschränkt bis Kettenkopplung entschieden ist. |
| Approval akzeptieren / ablehnen | Event + Auditlog sollen denselben Approver und Freigabe-/Ablehnungsgrund erklären. | Approver-Actor wirkt service-nah tragfähig, Quelle bleibt zu klassifizieren. | Release-/Signaturfolge braucht Causation. | Eingeschränkt; technische Folgeprozesse separat. |
| Release / Freigabe | Fachliche Approval-Entscheidung und technische Release-Folge müssen getrennt, aber kausal verbunden bleiben. | Menschlicher Approver ist nicht automatisch Actor des technischen Artefaktjobs. | RELEASED_PDF braucht erklärbare Kopplung zum Approval. | Supervisor-Entscheidung nötig. |
| RELEASED_PDF / technische PDF-Folgeprozesse | Technischer Folgeprozess soll nicht als unsichtbarer Teil des menschlichen Auditlogs verschwinden. | System-/Service-Actor nur mit klarer Folgeprozessklassifikation. | Causation zum fachlichen Auslöser erforderlich. | Gesondert darzustellen; offenes Nachweisereignis. |
| DOCX->PDF-Sync / SOURCE_PDF vor Signatur | Event/Audit für technischen Folgeprozess darf Owner/`system` nicht als fehlenden UserContext kaschieren. | Actor-Fallback bleibt eingeschränkt/legacy. | Muss kausal an Editing-/Signatur-Auslöser erklärbar sein. | Supervisor-Entscheidung nötig. |
| Read-Tracking / Read Receipt | Read-Session-Events, Receipt und ggf. Auditlog müssen Actor/Target sauber trennen. | Session-/Receipt-User ist nur bei belegter Selbst-Kenntnisnahme Actor. | `session_id` ist Hilfsmetadatum, keine vollständige Event-/Audit-Kopplung. | Implementierungsvorbereitung erst nach Supervisor-Klärung. |
| Kommentar-Events | Kommentarrecord, Event und ggf. Auditlog müssen Autor/Status-Bearbeiter/Sync-Actor trennen. | Actor nur im Record oder Payload ist eingeschränkt. | Statuswechsel und Sync brauchen Kettenbezug. | API-/Schema-Entscheidung nötig, aber nicht in dieser ADR. |
| Signatur-nahe Documents-Flows | Signaturereignisse können getrennte Nachweisartefakte bleiben, müssen bei Documents-Workflow-Bezug kausal verknüpfbar sein. | Signatur-Actor ist nicht automatisch Workflow-/AuditActor. | Signatur-Causation zu Documents-Transition offen. | Supervisor-Entscheidung nötig. |

## Nicht-Entscheidungen
- Keine konkrete API.
- Kein DTO.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Migration.
- Keine Backend-Transportentscheidung.
- Keine Implementierung von UserContext, RequestContext, AuditActor oder Audit-Export.
- Keine Entscheidung, ob Auditlog auf Event-ID verweist oder Domain-Events auf Auditlog-Einträge verweisen.
- Keine Entscheidung, ob `causation_id` auf Event-ID, Command-ID oder Use-Case-ID zeigt.
- Keine Reparatur bestehender Documents-, Auditlog-, Event-, Signatur-, Kommentar- oder Read-Tracking-Findings.

## Konsequenzen
- Für Documents-Services:
  - Services bleiben Ort der fachlichen Nachweisentscheidung.
  - Spätere Implementierungspakete müssen pro Use Case definieren, ob Domain-Event, Auditlog oder beide entstehen und wie sie konsistent gekoppelt werden.
- Für Domain-Events:
  - Events bleiben Integration-/Zustandsartefakte und werden nicht automatisch Auditlog.
  - Event-Actor und Event-Kette müssen später aus derselben Service-Entscheidung erklärbar sein wie das Auditlog.
- Für Auditlog:
  - Auditlog bleibt Nachweisartefakt für Handlungen und darf nicht ohne Kettenbezug als vollständig gekoppelt gelten.
  - Bestehende Auditlog-Zeilen bleiben eingeschränkt/legacy, wenn sie nicht belastbar mit Events verbunden sind.
- Für Audit-Export / Nachweispaket:
  - Actor-Qualität, Kettenstatus, Workflowstatus, Signaturstatus und Read-Receipt-Status bleiben getrennt.
  - Export darf Event/Auditlog-Zusammenhang nicht als belastbar behaupten, wenn nur Heuristik vorhanden ist.
- Für GUI/CLI/Backend:
  - Adapter und Backend dürfen Kontext transportieren oder anzeigen, aber nicht fachlich entscheiden, ob Event/Auditlog belastbar gekoppelt sind.
- Für Tests:
  - Keine Tests werden in AP-016 geändert.
  - Spätere Tests müssen Zielsemantik, Legacy-Fälle und technische Folgeprozesse getrennt prüfen.

## Risiken
- Technische Risiken:
  - Zu frühe Feld-/Schemafestlegung könnte EventEnvelope, AuditLogger und Servicegrenzen breit betreffen.
  - Ohne Kopplungsentscheidung bleiben Event/Audit-Verbindungen heuristisch.
  - Domain-Events und Auditlog könnten auseinanderlaufen, wenn spätere Pakete nur eine Seite ändern.
- Fachliche Risiken:
  - Actor kann in Event und Auditlog unterschiedlich wirken.
  - Technische `system`-Folgeprozesse können menschliche Verantwortung verdecken.
  - Signatur-Actor, Workflow-Actor und AuditActor können vermischt werden.
  - Read-Receipt-User kann fälschlich als ausführender Actor gelten.
- Audit-/Nachweisrisiken:
  - Exporte könnten ein vollständiges Nachweisbild behaupten, obwohl nur Domain-Event oder nur Auditlog vorhanden ist.
  - Legacy-Auditlogs ohne Event-/Kettenbezug können überbewertet werden.
  - Release-PDF, DOCX->PDF und Kommentar-Sync bleiben ohne Kopplung schwer prüfbar.

## Offene Supervisor-Entscheidungen
- Braucht Auditlog künftig eigene Correlation/Causation-Felder?
- Soll Auditlog auf Domain-Event-ID verweisen?
- Sollen Domain-Events auf Auditlog-Einträge verweisen?
- Soll eine spätere Use-Case-ID oder Command-ID statt direkter Event-/Auditlog-Referenz die Kopplung bilden?
- Braucht RELEASED_PDF-Erzeugung ein eigenes auditrelevantes Event, ein eigenes Auditlog oder beides?
- Sind Read-Tracking-Sessiondaten nur Hilfsmetadaten oder Teil einer belastbaren Nachweiskette?
- Bleiben Signaturereignisse in einem separaten Signatur-Nachweis, oder werden sie Teil des Documents-Nachweises?
- Wie werden Legacy-Auditlogs ohne Event-/Kettenbezug markiert?
- Welche Documents-MVP-Use-Cases müssen vor einem belastbaren Export zwingend Event + Auditlog erzeugen?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`
  - `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`
  - `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md`
  - `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md`
  - `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`
  - `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`
  - `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
  - `qm_platform/logging/log_query_service.py`
  - `modules/documents/eventing.py`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/service.py`
  - `modules/documents/pdf_read_tracking_service.py`
  - `modules/documents/comment_service.py`
  - `modules/documents/comment_sync_service.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Event-/Auditlog-/Documents-Hotspots.
  - Keine zusätzlichen Code-Suchläufe nötig; AP-013/AP-015 und gezielte Hotspot-Lektüre waren ausreichend.
- Keine Testsuite ausgeführt, weil AP-016 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Keine Exportformat-Entscheidung getroffen.
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob ein reines ADR-Paket `Documents-Release-PDF-Nachweisereignis-ADR` freigegeben oder zurückgestellt wird; keine Implementierung automatisch starten.
