# AP-022 RequestContext-/Kettenkontext-Transportstrategie ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Auditlog-Schema-Änderung: nein
- Audit-Export-Implementierung: nein
- Exportformat-Entscheidung: nein
- RequestContext-/CommandContext-/ExecutionContext-Implementierung: nein
- Command-/Use-Case-ID-Implementierung: nein
- Migration: nein

## Kontext
- Bezug auf AP-004: `docs/AP-004_USER_CONTEXT_ADR.md` trennt UserContext als Identitätskontext vom technischen Request-Kontext. UserContext liefert Identitätsbasis, entscheidet aber keine Rollen-, Actor- oder Nachweissemantik selbst.
- Bezug auf AP-006/AP-006A: `docs/AP-006_AUDIT_ACTOR_ADR.md` und `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` definieren AuditActor als explizit bestimmte handelnde Instanz und verlangen getrennte Bewertung von Actor-Qualität und technischen Ketten.
- Bezug auf AP-013/AP-014: `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` und `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md` zeigen, dass Documents-nahe Events aktuell Default-Correlation erhalten, aber keine durchgereichte Use-Case-/Request-Kette und keine Causation.
- Bezug auf AP-015/AP-016: `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md` und `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md` bewerten fehlende Event-/Auditlog-Kopplung als `ketten-eingeschränkt` und verorten die führende Nachweisentscheidung in Services.
- Bezug auf AP-020: `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md` entscheidet, dass Auditlog für belastbare mehrstufige Nachweise auditlog-seitig verfügbare Ketteninformationen braucht, ohne Schema zu entscheiden.
- Bezug auf AP-021: `docs/AP-021_USE_CASE_COMMAND_ID_STRATEGY_ADR.md` legt Use-Case-ID als bevorzugte service-seitige Klammer und Command-ID als bevorzugten unmittelbaren Causation-Auslöser fest, ohne ID-Formate oder Implementierung zu entscheiden.
- Aktueller Hotspot:
  - `src/backend/api.py` enthält nur `GET /health`; keine fachlichen Backend-Routen und kein RequestContext-Transportmodell.
  - `interfaces/cli/commands/documents_commands.py` und PyQt-Documents-Flows ermitteln Current User und leiten `actor_user_id`/`actor_role` oder Signaturdaten an Services weiter, aber keine Correlation, Causation, Use-Case-ID oder Command-ID.
  - `qm_platform/events/event_envelope.py` unterstützt `event_id`, `correlation_id`, `causation_id` und `actor_user_id`; ohne Übergabe entsteht je Event eine neue Default-Correlation.
  - `qm_platform/logging/audit_logger.py` erzeugt `audit_id`, aber keine Kettenreferenzen.
  - `modules/documents/eventing.py`, Documents-Workflow-, Read-Tracking-, Kommentar- und Signatur-nahe Flows erzeugen Events/Auditlogs ohne durchgängigen Request-/Use-Case-/Command-Kontext.

## Begriffsabgrenzung
- **UserContext**: Expliziter Identitätskontext für den authenticated/effective user an der Service-Grenze. Er kann Grundlage für Autorisierung und Actor-Bewertung sein, ist aber nicht selbst RequestContext, Kettenkontext, Rolle, QMB-Entscheidung oder AuditActor.
- **RequestContext**: Technischer Ausführungskontext eines konkreten Adapter-/Backend-/CLI-/GUI-Aufrufs. Er kann Herkunft, Aufrufbezug, Request-/Trace-Metadaten und Kettenreferenzen transportieren. Er entscheidet keine fachlichen Rollen, keine Actor-Qualität und keine Nachweisbewertung.
- **Kettenkontext**: Teilmenge oder Begleitkonzept des RequestContext, das Use-Case-ID, Command-ID, Correlation-ID, Causation-ID und ggf. Parent-/Teilkettenbezüge als technische Nachweiskette beschreibt. Ob Kettenkontext später ein eigenes Objekt oder Teil eines gemeinsamen Kontextcontainers wird, bleibt offen.
- **Use-Case-ID**: Technische Klammer eines service-seitigen fachlichen Use-Case-Aufrufs oder einer service-seitigen Nachweisentscheidung. Sie gruppiert zusammengehörige Commands, Events, Auditlogs, technische Folgeprozesse, Signatur- und Read-Teilketten.
- **Command-ID**: Technische Identität eines konkreten Auftrags innerhalb eines Use Cases. Sie ist bevorzugter unmittelbarer Auslöser für Causation, wenn ein Command Event, Auditlog oder technischen Folgeprozess verursacht.
- **Correlation-ID**: Technische Klammer für zusammengehörige Nachweisartefakte. Sie kann im Zielbild aus einer Use-Case-ID entstehen, einer Use-Case-ID entsprechen oder unabhängig transportiert werden; die konkrete technische Beziehung bleibt offen.
- **Causation-ID**: Technischer Verweis auf den unmittelbaren Auslöser innerhalb einer Kette, bevorzugt Command-ID, Event-ID oder gleichwertiger freigegebener Auslöserkontext je Use Case. Causation erklärt Auslöserrichtung, nicht Verantwortung.
- **Actor / AuditActor**: Fachlich bestimmte handelnde Instanz eines auditrelevanten Use Cases. Actor- und AuditActor-Bewertung bleiben Service- und Audit-Policy-Entscheidungen und werden nicht durch RequestContext oder Kettenkontext ersetzt.

Diese Begriffe dürfen nicht still vermischt werden. UserContext identifiziert, RequestContext transportiert, Kettenkontext verkettet, Use-Case-ID gruppiert, Command-ID beauftragt, Correlation-ID klammert, Causation-ID erklärt Richtung, Actor/AuditActor erklärt Verantwortlichkeit.

## Entscheidung
Empfohlene Ziel-Policy:

RequestContext und Kettenkontext sollen im Zielbild von Adaptern bis zur Service-Grenze als technische Kontextinformationen transportiert werden. Sie sind Transport- und Nachweiskettenkontext, keine fachliche Entscheidungsinstanz. GUI, CLI und Backend dürfen Kontext erzeugen, übernehmen oder weiterreichen, aber keine fachlichen Actor-, Rollen-, QMB-, Signatur- oder Nachweisentscheidungen daraus ableiten.

Services bleiben die fachliche Grenze für auditrelevante Use Cases. An der Service-Grenze sollen im Zielbild UserContext und Request-/Kettenkontext gemeinsam verfügbar sein, aber begrifflich getrennt bewertet werden. Services entscheiden Autorisierung, Invarianten, Actor-/AuditActor-Semantik, Target/Subject, Event-/Auditlog-Kopplung, technische Folgeprozess-Einordnung und Transaktionsgrenzen.

Der Kettenkontext soll die nach AP-021 bevorzugte Use-Case-/Command-ID-Strategie transportierbar machen: Use-Case-ID als Klammer für eine service-seitige Nachweisentscheidung, Command-ID als bevorzugter unmittelbarer Causation-Auslöser, Correlation-ID als technische Gruppierung und Causation-ID als Auslöserreferenz. Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Feldmodell und kein Schema.

Fehlender oder nur impliziter Request-/Kettenkontext führt bei mehrstufigen Nachweisketten grundsätzlich zu `ketten-eingeschränkt` oder `ketten-legacy`. Das betrifft nicht automatisch den Actor-Status. Ein belastbarer Actor heilt keine fehlende Kette; eine saubere Kette heilt keinen unklaren Actor.

## Transportverantwortung

| Schicht | Darf transportieren | Darf nicht entscheiden |
| --- | --- | --- |
| GUI / PyQt | technischen Aufrufkontext, vorhandene UserContext-Referenz, Client-/UI-Herkunft, ggf. vorhandene Kettenreferenzen aus einem vorherigen Schritt, Signatur-Eingaben als Eingabe zum Use Case | finale Rollen-/QMB-/Actor-/AuditActor-/Nachweisqualität, ob eine Kette `kettenbelastbar` ist, ob Signatur-Actor gleich AuditActor ist |
| CLI | technischen Aufrufkontext, aktuelle CLI-Herkunft, vorhandene Auth-/User-Referenz, Eingaben und ggf. weitergereichte Kettenreferenzen | fachliche Autorisierung als alleinige Wahrheit, finale Actor-Quelle, Nachweisstatus, Exportfähigkeit |
| Backend | validierten Transport-/Request-Kontext, Auth-/Session-/Token-Bezug nach separater Auth-Entscheidung, Trace-/Correlation-Bezug, weitergereichte Parent-/Causation-Bezüge | Businesslogik, fachliche Rollen-/QMB-/Befugnisentscheidung, AuditActor-Semantik, Documents-/Signatur-Nachweisentscheidung |
| Services | UserContext und Request-/Kettenkontext als Eingaben an der Use-Case-Grenze | nichts an Adapter delegieren, was Actor, Rollen, Invarianten, Target/Subject, Transaktion oder Nachweisstatus fachlich entscheidet |
| Repositories / Storage | persistenznotwendige IDs oder Nachweisdaten nach service-seitiger Entscheidung | Kontextquelle, Rollenprüfung, Actor-Auswahl oder Kettenstatus-Bewertung |

Adapter dürfen Kettenreferenzen nicht erfinden, um Lücken zu kaschieren. Wenn kein belastbarer Parent-/Request-/Use-Case-Kontext vorhanden ist, muss der spätere Nachweisstatus dies sichtbar machen.

## Service-Grenze
- Zielbild an der Service-Grenze:
  - UserContext oder gleichwertiger Identitätskontext als getrennte Eingabe.
  - RequestContext oder gleichwertiger technischer Ausführungskontext.
  - Kettenkontext mit vorhandener Use-Case-ID, Command-ID, Correlation-ID, Causation-ID oder Parent-Referenz, soweit für den Use Case vorhanden.
  - Adapter-/Transportherkunft als technisches Metadatum, z. B. GUI, CLI, Backend, Job oder Import.
  - Eingabedaten des fachlichen Use Cases getrennt vom Kontext.
- Technische Metadaten bleiben:
  - Clienttyp, Transportart, Trace-/Correlation-Werte, Command-/Use-Case-IDs, Session-/Request-Hinweise, Quellpfade und Diagnosekontext.
  - Diese Werte können Nachweisketten erklären, aber keine fachliche Berechtigung oder Verantwortlichkeit alleine begründen.
- Fachlich bei Services verbleibt:
  - Rollen-/Befugnisprüfung, QMB/Admin-Semantik, Vier-Augen-Regel, Workflow-Zulässigkeit.
  - Actor-/AuditActor-Auswahl und Nachweisstatus.
  - Entscheidung, ob Signatur-Actor, Workflow-User, System Actor oder Service account für eine konkrete Nachweiszeile relevant ist.
  - Entscheidung, welche Domain-Events, Auditlogs und technische Folgeprozesse aus derselben Nachweisentscheidung entstehen.

Rollen-/Actor-/Nachweisentscheidungen dürfen nicht in Adapter wandern, weil Adapter nur UI-/CLI-/Transportwissen haben, keine vollständige Service-Invariante und keine zuverlässige Transaktionssicht. Adapter-Gates können UX unterstützen, ersetzen aber keine service-seitige Autorisierung oder Auditbewertung.

## Kettenbildung
- Use-Case-ID:
  - soll im Zielbild einen service-seitigen fachlichen Use-Case-Aufruf oder eine Nachweisentscheidung gruppieren.
  - kann Correlation-Basis sein oder neben Correlation transportiert werden; diese technische Beziehung bleibt offen.
  - darf nicht als Actor, Rolle, Session oder Target missverstanden werden.
- Command-ID:
  - soll im Zielbild einen konkreten Auftrag innerhalb der Use-Case-Kette identifizieren.
  - ist bevorzugter Causation-Auslöser für Events, Auditlog-Einträge und technische Folgeprozesse, wenn der Auftrag der unmittelbare Auslöser ist.
  - darf nicht als Autorisierung oder Actor-Entscheidung verstanden werden.
- Correlation-ID:
  - soll zusammengehörige Events, Auditlog-Einträge, technische Logs, Signaturteilketten, Read-Tracking-Teilketten und Artefaktfolgen gruppieren.
  - kann aus transportiertem Kontext übernommen oder service-seitig für den Use Case neu gebildet werden; Pflichtgrad und technische Erzeugung bleiben offen.
- Causation-ID:
  - soll aus transportiertem Parent-/Command-/Event-Kontext weitergegeben oder service-seitig als Folgebezug bestimmt werden.
  - soll bei technischen Folgeprozessen und mehrstufigen Nachweisketten den unmittelbaren Auslöser erklären.
  - bleibt ohne konkrete Referenzform: Event-ID, Command-ID, Use-Case-ID oder andere Zielreferenz sind separate Entscheidungen.
- Legacy:
  - Wenn nur `event_id`, `audit_id`, `session_id`, Dateipfad, Status oder Zeitstempel vorhanden sind, darf daraus keine vollständige Use-Case-/Command-Kette behauptet werden.
  - Default-Correlation je Event ist keine belastbare durchgereichte Use-Case-Kette.

## Documents-MVP-Auswirkung

| Bereich | Zielwirkung des Request-/Kettenkontexts | Bestandseinordnung |
| --- | --- | --- |
| Workflow-Transitions | Use-Case-ID klammert den Workflow-Aufruf; Command-ID beschreibt Transition; Correlation/Causation verbinden Event, Auditlog, Registry und technische Folgen. | Heute überwiegend `actor_user_id`/`actor_role`, Event-ID und Auditlog ohne Kettenkopplung; daher `ketten-eingeschränkt` oder bei Fallbacks `ketten-legacy`. |
| Review / Approval | Reviewer-/Approver-Entscheidung bleibt service-seitig; Kettenkontext verbindet Review-/Approval-Command, Domain-Event, Auditlog und mögliche Signatur-/Release-Folgen. | Actor wirkt teils service-nah, aber Kettenkontext fehlt; Event/Audit nur heuristisch verbunden. |
| Release / Freigabe | Fachliche Freigabe und technische Release-Folge bleiben getrennt, aber über Use-Case-/Command-/Causation-Kontext rückführbar. | RELEASED_PDF-Erzeugung ist aktuell nicht als eigene belastbare Kette ausgewiesen. |
| RELEASED_PDF / technische PDF-Folgeprozesse | Technische PDF-Erzeugung soll als Folge eines freigegebenen Commands oder Events erklärbar sein, ohne menschlichen Approval-Actor mit technischem Folgeprozess zu vermischen. | Ohne Causation mindestens `ketten-eingeschränkt`; bei nicht rekonstruierbarem Bestand `ketten-legacy`. |
| Read-Tracking / Read Receipt | `session_id` bleibt fachliche Read-Session-Hilfsklammer; Request-/Kettenkontext soll Start, Dwell, Completion und Receipt in eine Nachweiskette einordnen. | `session_id` ersetzt keine Correlation/Causation und keinen Actor; aktuelle Events sind eingeschränkt. |
| Kommentar-Sync | Sync-Command oder Import-/Use-Case-Kontext soll Sync-Actor, DOCX-Autor, Kommentarstatus und Event/Audit-Bezug trennen. | Aktuell steht Actor teils nur im Payload oder Record; kein belastbarer Kettenkontext. |
| Signatur-nahe Documents-Flows | Documents-Use-Case, Signatur-Command und Signatur-Events brauchen gemeinsamen Parent-/Kettenbezug, ohne Signatur-Actor automatisch zum Documents-AuditActor zu machen. | `SignRequest` ist policy-nah als Auftrag erkennbar, aber ohne Command-ID und ohne Documents-Causation. |

## Nachweisstatus
- `kettenbelastbar` ist erst möglich, wenn:
  - ein service-seitiger Use-Case-/Correlation-Bezug die relevanten Nachweisartefakte gruppiert,
  - ein Command-, Event- oder gleichwertiger Auslöserbezug die Causation relevanter Folgeprozesse erklärt,
  - Event und Auditlog nicht nur über Zeit, Action, Target, Dateipfad oder Status heuristisch verbunden werden,
  - Services die fachliche Nachweisentscheidung getroffen haben.
- `ketten-eingeschränkt` gilt, wenn:
  - nur Default-Correlation je Event vorhanden ist,
  - Auditlog keine belastbare Kettenreferenz besitzt,
  - `session_id`, `last_event_id`, Dateipfad, Target oder Status nur als Hilfsreferenz dienen,
  - technische Folgeprozesse, Signaturereignisse oder Read-Completion ohne klaren Parent erscheinen.
- `ketten-legacy` gilt, wenn:
  - Altbestand oder Import ohne rekonstruierbaren Request-/Kettenkontext vorliegt,
  - Ketten nur nachträglich geraten würden,
  - Owner-/`system`-/`unknown`-Fallbacks oder freie Strings keine belastbare Kontextquelle erkennen lassen.

Actor-Nachweisstatus bleibt getrennt:
- `belastbar`, `eingeschränkt` und `legacy` aus AP-006A bewerten Actor-Quelle und Actor-Qualität.
- `kettenbelastbar`, `ketten-eingeschränkt` und `ketten-legacy` bewerten technische und fachliche Verkettung.
- Eine belastbare Kette macht einen unklaren Actor nicht belastbar.
- Ein belastbarer Actor macht eine fehlende Causation nicht belastbar.

## Umgang mit aktuellem Zustand

| Fundtyp | Aktueller Zustand | Policy-Bewertung | Spätere Behandlung |
| --- | --- | --- | --- |
| Backend | Nur Health-Route, kein fachlicher Transportkontext. | Kein Verstoß; noch keine Backend-Feature-Grenze für RequestContext vorhanden. | Backend darf später transportieren, aber nicht fachlich entscheiden. |
| CLI Documents | Ermittelt Current User und Rolle, ruft öffentliche Documents-/Signature-APIs mit `actor_user_id`/`actor_role` und SignRequest auf. | Transportiert punktuelle Identitäts-/Rollenwerte, aber keine Kettenreferenzen; Rollen-Gates bleiben UX/Legacy. | Keine Änderung in AP-022; spätere Service-Grenze pro Use Case planen. |
| PyQt Documents | Ermittelt Current User, baut Workflow-/Signatur-/PDF-Viewer-Aufrufe und Adapter-Auditlogs. | Adapter transportiert Kontextfragmente, aber keine Kettenwahrheit; UI-Audit getrennt einordnen. | Keine Änderung in AP-022; spätere Vereinheitlichung offen. |
| EventEnvelope | Hat `correlation_id` und `causation_id`; erzeugt Default-Correlation. | Fähigkeit vorhanden, aber ohne durchgereichten Kontext keine Use-Case-Kette. | Keine Event-Schema-Entscheidung in AP-022. |
| AuditLogger | Hat `audit_id`, aber keine Kettenfelder. | Für mehrstufige Nachweise `ketten-eingeschränkt`. | Keine Auditlog-Schema-Entscheidung in AP-022. |
| Documents-Workflow | Services erzeugen Event und Auditlog, aber ohne gemeinsame Kettenreferenz. | Service-Nachweisentscheidung ist Zielort, aktuelle Kettenkopplung eingeschränkt. | Später klein schneiden, keine Reparatur jetzt. |
| Read-Tracking | Nutzt `session_id` für Read-Session. | Hilfsmetadatum, keine vollständige Request-/Event-/Audit-Kette. | Spätere Read-Context-Policy nötig. |
| Kommentar-Sync | Actor teils im Payload, DOCX-Autor als Fremdmetadatum. | Eingeschränkt/legacy für Nachweiskette. | Spätere Kommentar-/Import-Kettenentscheidung nötig. |
| Signatur | `SignRequest` enthält Signaturdaten und `signer_user`, aber keine Command-/Use-Case-ID. | Auftrag konzeptionell erkennbar, aber nicht als belastbarer Kettenkontext. | Spätere Signatur-/Documents-Teilkettenentscheidung nötig. |

## Nicht-Entscheidungen
- Keine konkrete API.
- Keine API-Signatur.
- Kein DTO.
- Kein RequestContext-, CommandContext- oder ExecutionContext-Objekt.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Migration.
- Keine Backend-Route.
- Keine Auth-, UserContext-, AuditActor-, Eventkopplungs- oder Audit-Export-Implementierung.
- Keine Command-ID- oder Use-Case-ID-Implementierung.
- Keine Entscheidung über konkrete ID-Formate, Generatoren, Persistenzorte, Header, Felder, Tabellen oder Parameter.
- Keine Entscheidung, ob RequestContext und Kettenkontext später ein gemeinsames Objekt oder getrennte Objekte werden.
- Keine Änderung an Backend, CLI, PyQt, EventEnvelope, AuditLogger, Documents, Signatur, Tests oder bestehenden ADRs/Inventaren.
- Keine Reparatur bestehender Findings.

## Konsequenzen
- Für Services:
  - Services bleiben Ort der fachlichen Entscheidung und müssen später UserContext und Request-/Kettenkontext getrennt auswerten können.
  - Spätere Umsetzungsvorbereitung muss je Use Case klären, welche Kontextinformationen an der Grenze nötig sind.
- Für Adapter:
  - GUI, CLI und Backend dürfen technische Kontexte weiterreichen und anzeigen.
  - Adapter dürfen keine fachliche Ketten-, Actor- oder Rollenwahrheit herstellen.
- Für Events/Auditlog:
  - Die Zielsemantik verlangt durchgängigen Kontext, trifft aber keine Schemaentscheidung.
  - Bestehende Default-Correlation, Event-ID und Audit-ID bleiben nutzbar, aber nicht als vollständige Kette überzuinterpretieren.
- Für Documents-MVP:
  - Workflow, Review/Approval, Release, RELEASED_PDF, Read-Tracking, Kommentar-Sync und Signatur-nahe Flows brauchen später explizite Kontextstrategie je Slice.
  - Bis dahin bleiben fehlende Request-/Kettenkontexte sichtbar eingeschränkt oder legacy.
- Für Audit-Export / Nachweispaket:
  - Kettenstatus und Actor-Status müssen getrennt ausweisbar bleiben.
  - Legacy-Kontextquellen dürfen nicht rückwirkend zu belastbaren Ketten aufgewertet werden.

## Risiken
- Technische Risiken:
  - Zu frühe Festlegung auf ein konkretes Kontextobjekt könnte viele Servicegrenzen, Tests, Events und Auditlogs berühren.
  - Unterschiedliche GUI-/CLI-/Backend-Transportquellen können Doppelwahrheiten erzeugen, wenn keine Service-Grenze dominiert.
  - Ohne durchgehenden Kontext entstehen weiter Einzel-Correlations statt Use-Case-Ketten.
- Fachliche Risiken:
  - Adapter könnten aus Transportdaten fälschlich Actor-, Rollen- oder Nachweisentscheidungen ableiten.
  - Command-ID oder Correlation-ID könnten mit Verantwortung verwechselt werden.
  - Signatur-Actor, Workflow-User und AuditActor könnten vermischt werden, wenn Kettenkontext als Actor-Ersatz gelesen wird.
- Audit-/Nachweisrisiken:
  - Exporte könnten Default-Correlation, `session_id`, `last_event_id` oder `audit_id` als belastbare Kette darstellen.
  - Technische Folgeprozesse ohne Causation können menschliche Verantwortung verdecken oder isoliert erscheinen.
  - Legacy-Flows ohne Kontext können überinterpretiert werden, wenn ihr Status nicht sichtbar bleibt.

## Offene Supervisor-Entscheidungen
- Sollen RequestContext und Kettenkontext später ein gemeinsames Objekt, getrennte Objekte oder Teil eines breiteren ExecutionContext werden?
- Wird Use-Case-ID als eigener Wert eingeführt oder entspricht sie einer Correlation-Basis?
- Wird Command-ID zwingend eingeführt oder bleibt sie zunächst Policy-Begriff?
- Soll `causation_id` technisch bevorzugt auf Command-ID, Event-ID, Use-Case-ID oder je Use Case unterschiedlich zeigen?
- Wie werden Backend-, CLI- und PyQt-Kontextquellen später vereinheitlicht, ohne Adapter zur fachlichen Wahrheit zu machen?
- Welche Legacy-Flows ohne Request-/Kettenkontext werden `ketten-eingeschränkt`, welche `ketten-legacy`?
- Brauchen technische Folgeprozesse eigene Teilkontexte, z. B. RELEASED_PDF, DOCX->PDF, Kommentar-Sync, Read-Tracking und Signatur?
- Müssen Auditlog und Event später denselben Request-/Use-Case-Kontext direkt tragen, oder reicht eine andere auditlog-seitig verfügbare Kopplung?
- Welche Kontextinformationen sind Mindestvoraussetzung für einen belastbaren Documents-MVP-Nachweisslice?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-004_USER_CONTEXT_ADR.md`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`
  - `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`
  - `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`
  - `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`
  - `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md`
  - `docs/AP-021_USE_CASE_COMMAND_ID_STRATEGY_ADR.md`
  - `src/backend/__main__.py`
  - `src/backend/api.py`
  - `src/backend/__init__.py`
  - `interfaces/cli/commands/documents_commands.py`
  - `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py`
  - `interfaces/pyqt/presenters/documents_signature_ops.py`
  - `interfaces/pyqt/widgets/pdf_viewer_dialog.py`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
  - `qm_platform/logging/logger_service.py`
  - `modules/documents/eventing.py`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/service.py`
  - `modules/documents/pdf_read_tracking_service.py`
  - `modules/documents/comment_sync_service.py`
  - `modules/signature/signature_execute_ops.py`
  - `modules/signature/contracts.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-022_REQUEST_CONTEXT_CHAIN_CONTEXT_TRANSPORT_STRATEGY_ADR.md`.
  - `Glob` zur Einordnung der vorhandenen Backend-Dateien.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Backend-/CLI-/PyQt-/Event-/Audit-/Documents-/Signatur-Hotspots.
  - `rg` in `src/backend`, `interfaces/cli`, `interfaces/pyqt`, `qm_platform/events`, `qm_platform/logging`, `modules/documents` und `modules/signature` nach RequestContext-, UserContext-, Current-User-, Actor-, Correlation-, Causation-, Command-, Use-Case-, Session-, Event-, Audit- und Signaturbegriffen.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/Auditlog-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-022 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Keine Auditlog-Schema-Änderungen durchgeführt.
- Keine Audit-Export-Implementierung durchgeführt.
- Keine Exportformat-Entscheidung getroffen.
- Keine RequestContext-/CommandContext-/ExecutionContext-Implementierung durchgeführt.
- Keine Command-/Use-Case-ID-Implementierung durchgeführt.
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-022_REQUEST_CONTEXT_CHAIN_CONTEXT_TRANSPORT_STRATEGY_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein reines ADR-Paket zur konkreten Priorisierung eines ersten Documents-MVP-Nachweisslices oder ein enges Umsetzungsvorbereitungspaket ohne Implementierung für genau einen Slice freigegeben wird; keine Implementierung automatisch starten.
