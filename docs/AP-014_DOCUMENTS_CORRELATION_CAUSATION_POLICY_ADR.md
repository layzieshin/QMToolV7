# AP-014 Documents-Correlation-Causation-Policy ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert `correlation_id` als technische Klammer für zusammengehörige Requests, Commands, Events oder Auditzeilen und `causation_id` als Verweis auf den auslösenden Vorgang. Beide ersetzen keinen Actor.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` markiert Correlation/Causation als empfohlene Mindestfelder für spätere Audit-Exports, trennt sie aber vom Actor-Nachweisstatus.
- Bezug auf AP-009: `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` identifiziert technische Folgeprozesse wie Release-PDF, DOCX->PDF-Erzeugung, Read-Tracking, Kommentare und Signaturübergänge als Nachweiskettenbedarf.
- Bezug auf AP-010: `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md` empfiehlt Correlation/Causation besonders für Read-Session-Start, Dwell-Tracking und Completion.
- Bezug auf AP-011: `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` zeigt, dass Documents-Events zwar Events und Actor-Felder haben können, aber keine explizit durchgereichte Correlation/Causation.
- Bezug auf AP-012: `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md` verlangt, technische `system`-Folgeprozesse mit ihrem fachlichen Auslöser erklärbar zu halten und nicht als Actor-Ersatz zu werten.
- Bezug auf AP-013: `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` stellt fest, dass aktuell keine Documents-nahe Produktivfundstelle sowohl explizite Correlation als auch Causation weitergibt; AuditLogger-Zeilen besitzen keine Kettenfelder.

## Begriffe
- **Correlation**: Technische Klammer einer zusammengehörigen Request-/Command-/Use-Case-Kette. Sie gruppiert mehrere Events, Auditlog-Einträge, technische Logs und Folgeprozesse, die zu demselben fachlichen Aufruf oder Nachweisvorgang gehören.
- **Causation**: Technischer Verweis auf den auslösenden Command, das auslösende Event oder ein anderes ausdrücklich bestimmtes Use-Case-Ereignis innerhalb einer Kette.
- **Actor**: Handelnde Instanz einer fachlichen oder technischen Aktion. Actor ist von Correlation/Causation getrennt.
- **Workflow-Actor**: Fachlich ausführende Identität eines Documents-Workflow-Schritts.
- **Read-Receipt-Actor**: Ausführender User der Kenntnisnahme nach AP-010.
- **Signatur-Actor**: Identität des Signaturvorgangs; nicht automatisch Workflow- oder AuditActor.
- **Technischer System Actor**: Nicht-menschliche technische Identität für echte System- oder Servicefolgeprozesse.
- **AuditActor**: Im Audit-/Nachweiskontext protokollierte handelnde Instanz; nicht durch Correlation/Causation ersetzbar.
- **Nachweiskette**: Zusammenführung von Domain-Events, Auditlog-Einträgen, technischen Folgeprozessen und ggf. Registry-/Readmodel-Status für einen Audit-Export oder ein Nachweispaket.

## Entscheidung
Empfohlene Zielentscheidung:

`correlation_id` soll im Zielbild die technische Klammer für eine zusammengehörige Documents-Use-Case-Kette sein. Für auditrelevante Documents-MVP-Use-Cases soll eine Correlation verpflichtend sein, sobald mehr als ein Event, Auditlog-Eintrag, technischer Folgeprozess oder Readmodel-/Registry-Update gemeinsam als Nachweiskette verstanden werden soll. Correlation ist nicht identisch mit Actor, UserContext, Rolle, Session, Signatur oder Nachweisqualität.

`causation_id` soll im Zielbild den konkreten auslösenden Vorgang innerhalb einer Correlation referenzieren. Für technische Folgeprozesse und mehrstufige Nachweisketten soll Causation verpflichtend sein, insbesondere bei RELEASED_PDF-Erzeugung, DOCX->PDF-Erzeugung, Kommentar-Sync, Read-Tracking-Completion, Signatur-nahen Folgeereignissen und `system`-Folgeprozessen. Causation erklärt, warum etwas geschah; sie sagt nicht, wer fachlich verantwortlich war.

Für interaktive Einzelaktionen ohne technischen Folgeprozess kann eine Correlation ausreichen, wenn Event, Auditlog und Readmodel nicht als mehrstufige Kette ausgewiesen werden. Sobald ein Event ein anderes Event, eine technische Artefakterzeugung, einen Signaturvorgang, einen Registry-Statuswechsel oder einen Auditlog-Eintrag erklären soll, ist eine Causation fachlich erforderlich.

Bestehende Documents-Events ohne durchgereichte Correlation/Causation bleiben für MVP-Audit-Exports nicht automatisch unbrauchbar, müssen aber als eingeschränkte Nachweiskette ausgewiesen werden. Fehlende Correlation/Causation ist ein Ketten-/Kontextstatus, nicht derselbe Status wie Actor-Qualität `belastbar`, `eingeschränkt` oder `legacy`.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Exportformat, kein Backend-Transportmodell und keine Implementierung.

## Zielsemantik `correlation_id`
- Zielregel:
  - `correlation_id` gruppiert alle technischen und fachlichen Einträge, die zu demselben Documents-Use-Case-Aufruf oder derselben Nachweiskette gehören.
  - Eine Correlation kann mehrere Domain-Events, Auditlog-Einträge, technische Logs, Signaturereignisse, Registry-Updates und Read-Tracking-Ereignisse umfassen.
  - Correlation darf nicht als Actor, User-ID, Rolle, Session-ID, Dokument-ID oder Signatur-ID missverstanden werden.
- Für Documents-MVP verpflichtend, wenn:
  - ein Workflow-Schritt mehrere Ereignisse erzeugt oder Folgeprozesse auslöst,
  - ein Nachweispaket eine Kette vom fachlichen Auslöser bis zu technischem Ergebnis darstellen soll,
  - Read-Tracking-Start, Fortschritt, Completion und Receipt zusammen erklärt werden,
  - Signaturereignisse zusammen mit Documents-Workflow-Transitions ausgewiesen werden,
  - Auditlog- und Domain-Event-Zeilen zusammengeführt werden sollen.
- Für Documents-MVP eingeschränkt/optional, wenn:
  - ein technisches Lifecycle-Event keine fachliche Nachweiskette behauptet,
  - ein Anzeige-/Readmodel-Zugriff nur vorhandenen Zustand liest,
  - Alt-/Legacy-Daten ohne nachträgliche Rekonstruktion nur markiert werden.
- Nicht-Zweck:
  - keine Actor-Bestimmung,
  - keine Autorisierungsentscheidung,
  - keine Signatur- oder Re-Auth-Bewertung,
  - keine Garantie für Audit-Nachweisqualität.

## Zielsemantik `causation_id`
- Zielregel:
  - `causation_id` referenziert den unmittelbaren Auslöser eines Folgeevents, technischen Folgeprozesses oder Auditlog-Eintrags.
  - Causation soll auf ein auslösendes Command, Event oder Use-Case-Ereignis zeigen; welches technische ID-Format dafür genutzt wird, bleibt offen.
  - Causation darf nicht als Actor, Schuldzuweisung oder fachliche Verantwortlichkeit verstanden werden.
- Für Documents-MVP verpflichtend, wenn:
  - eine technische Artefakterzeugung als Folge eines fachlichen Workflow-Events entsteht,
  - ein `system`- oder Service-Folgeprozess durch eine menschliche Aktion ausgelöst wurde,
  - ein Signaturereignis einen Documents-Workflow-Übergang unterstützt oder erklärt,
  - ein Read-Tracking-Completion-Event aus einer gestarteten Read-Session entsteht,
  - Kommentar-Sync aus einem Import-/DOCX-Kontext oder einem expliziten Sync-Command entsteht,
  - ein Auditlog-Eintrag als Begleitnachweis zu einem Domain-Event erscheinen soll.
- Für Documents-MVP offen/zu entscheiden:
  - ob Causation auf `event_id`, Command-ID oder eine spätere Use-Case-ID zeigen soll,
  - ob technische Logs eigene Causation-Felder bekommen,
  - ob Auditlog-Einträge direkt auf Domain-Events zeigen oder exportseitig zusammengeführt werden.
- Nicht-Zweck:
  - keine fachliche Actor-Auswahl,
  - keine Rollen-/QMB-Semantik,
  - keine elektronische Signaturbewertung,
  - kein Ersatz für fehlenden UserContext.

## Mindestpolicy für Documents-MVP

| Bereich | Correlation verpflichtend | Causation verpflichtend | Begründung | Zielstatus für Nachweiskette |
| --- | --- | --- | --- | --- |
| Workflow-Rollen, Start, Abort | ja | ja, wenn Auditlog/Event/Folgeprozess verbunden werden | Interaktive Workflow-Aktion ist auditnah; optionale Actor und Fallbacks dürfen nicht zusätzlich durch lose Ketten verdeckt werden. | belastbare Kette erst nach Kontextweitergabe |
| Review/Approval angenommen/abgelehnt | ja | ja bei Signatur, Registry-Update oder Artefaktfolgeprozess | Diese Events sind MVP-nah und bilden Freigabe-/Ablehnungsketten. | belastbare Kette möglich, Actor separat zu klassifizieren |
| RELEASED_PDF-Erzeugung | ja | ja | Technische Folge der fachlichen Freigabe muss kausal erklärbar sein. | ohne Causation eingeschränkt |
| DOCX->PDF-Erzeugung vor Signatur | ja | ja | Technische Konvertierung kann mit `system`/Owner-Fallback verwechselt werden. | ohne Causation eingeschränkt/legacy |
| Archivierung | ja | ja, falls `system` oder technischer Job beteiligt ist | Archivierung ist fachlich relevant; `system` darf nicht isoliert erscheinen. | ohne Causation eingeschränkt |
| Read-Tracking Start/Incomplete/Completed/Receipt | ja | ja für Completion/Receipt-Kette | `session_id` ist fachliches Payload-Merkmal, aber kein Event-Causation-Ersatz. | ohne Causation eingeschränkt |
| Direct Read Confirm | ja | offen/ja, falls Training-/Read-Session-Kontext vorhanden | Direkte Bestätigung kann Einzelereignis sein, braucht bei Nachweiskette aber Auslöserbezug. | abhängig von Quelle eingeschränkt/belastbar |
| Kommentar erstellt/Status geändert | ja | ja bei Statuswechsel oder Bezug zu Workflow-Review | Kommentarrecord und Event sollen nachvollziehbar zusammenhängen. | ohne Causation eingeschränkt |
| DOCX-Kommentar-Sync | ja | ja | Sync-Actor, DOCX-Autor und Import-/Sync-Auslöser müssen getrennt bleiben. | ohne Causation eingeschränkt/legacy |
| Signatur-nahe Documents-Flows | ja | ja | Signatur-Event ist nicht automatisch Documents-AuditActor und muss kausal an Transition erklärbar sein. | ohne Causation eingeschränkt |
| Modul-Lifecycle / Runtime | nein/offen | nein/offen | Kein fachlicher Documents-Use-Case; systemnah separat markieren. | separat als Runtime-Kontext |
| Legacy-/Import-/Altbestand | nein/offen | nein/offen | Nachträgliche Rekonstruktion darf nicht behauptet werden. | legacy/eingeschränkt sichtbar markieren |

## Auditlog und Domain-Events
- Zielregel:
  - Domain-Events und Auditlog-Einträge sollen in späteren Nachweispaketen konsistent zusammenführbar sein.
  - Auditlog darf nicht nur über Zeit, Zieltext oder Action heuristisch mit Events verbunden werden, wenn eine belastbare Kette behauptet wird.
  - Ob Auditlog künftig eigene Correlation/Causation-Felder erhält oder exportseitig über Event-/Request-Kontext verbunden wird, bleibt eine Supervisor-Entscheidung.
- Mindestpolicy:
  - Für neue auditrelevante Documents-MVP-Ketten soll Auditlog denselben Correlation-Kontext wie das fachliche Domain-Event besitzen oder eindeutig exportseitig daran gebunden werden.
  - Begleitende Auditlog-Einträge zu technischen Folgeprozessen sollen eine Causation zum auslösenden Event/Command besitzen oder im Export als eingeschränkte Kette markiert werden.
  - Auditlog-Actor und Event-Actor bleiben getrennt zu bewerten; dieselbe Correlation macht einen Actor nicht automatisch belastbar.
- Aktueller Bestand:
  - AP-013 zeigt AuditLogger-Zeilen ohne Correlation/Causation.
  - Bestehende Exporte dürfen diese Ketten nicht als vollständig belastbar darstellen.

## Technische `system`-Folgeprozesse
- Zielregel:
  - Ein technischer `system`- oder Service-Actor ist nur nachvollziehbar, wenn der Prozess entweder echt systeminitiiert ist oder über Causation an einen fachlichen Auslöser gebunden wird.
  - Causation trennt den technischen Folgeprozess vom menschlichen Workflow-Actor; sie ersetzt den menschlichen Actor nicht.
- Beispiele:
  - RELEASED_PDF-Erzeugung soll kausal auf Freigabe/Approval oder einen freigegebenen technischen Release-Command zurückführbar sein.
  - DOCX->PDF-Erzeugung vor Signatur soll kausal auf Editing-Complete/Signaturvorbereitung oder einen expliziten Konvertierungs-Command zurückführbar sein.
  - Kommentar-Sync soll kausal auf einen Sync-Command oder Importvorgang zurückführbar sein; DOCX-Autor bleibt Metadatum.
  - Read-Tracking-Completion soll kausal auf die gestartete Read-Session und den finalisierenden Vorgang zurückführbar sein.
  - Signaturereignisse sollen kausal mit der Documents-Transition verknüpft werden, ohne Signatur-Actor und Workflow-/AuditActor gleichzusetzen.
- Offene Grenzen:
  - Ob einzelne technische Prozesse eigene Domain-Events brauchen, bleibt offen.
  - Ob System Actor als eigener Actor-Typ, Service account oder technischer Actor-String geführt wird, bleibt von AP-012/AP-006 abhängig.

## Nachweisstatus
- Correlation/Causation-Status ist ein Kettenstatus:
  - `kettenbelastbar`: Correlation ist durchgereicht und Causation erklärt relevante Folgeprozesse.
  - `ketten-eingeschränkt`: Correlation existiert nur als Einzel-/Default-Correlation oder Causation fehlt bei mehrstufigen Ketten.
  - `ketten-legacy`: Altbestand, Import oder Bestandsereignis ohne rekonstruierbare Kette.
- Actor-Nachweisstatus bleibt getrennt:
  - `belastbar`, `eingeschränkt`, `legacy` aus AP-006A/AP-012 bewertet Actor-Quelle und Actor-Qualität.
  - Eine `kettenbelastbare` Correlation macht einen Actor nicht automatisch `belastbar`.
  - Ein `belastbarer` Actor macht eine fehlende Causation nicht automatisch unproblematisch.
- Für MVP-Audit-Exports:
  - Fehlende Correlation bei mehrstufigen Documents-Nachweisketten ist mindestens `ketten-eingeschränkt`.
  - Fehlende Causation bei technischen Folgeprozessen, Signaturereignissen oder Read-Tracking-Completion ist mindestens `ketten-eingeschränkt`.
  - Legacy-/Importfälle ohne rekonstruierbare Kette müssen sichtbar als `ketten-legacy` oder gleichwertig markiert werden.
  - Die konkrete Exportkennzeichnung bleibt offen; diese ADR definiert keine Exportstruktur.

## Umgang mit AP-013-Funden

| AP-013-Fundtyp | Zielrichtung | Policy-Bewertung | spätere Behandlung |
| --- | --- | --- | --- |
| Keine Kategorie-A-Funde | Zielzustand braucht explizite Kettenweitergabe für MVP-Nachweisketten. | aktueller Bestand eingeschränkt | Keine Reparatur in AP-014. |
| EventEnvelope erzeugt Default-Correlation | Default-Correlation ist technische Einzel-ID, keine durchgereichte Use-Case-Kette. | eingeschränkt für Nachweisketten | Künftige Policy/Implementierungsvorbereitung braucht Kontextquelle. |
| Causation wird nicht gesetzt | Folgeprozesse bleiben ohne Auslöserbezug. | eingeschränkt/legacy je Use Case | Pflichtgrad pro Workflow-/Read-/Signatur-/Artefaktkette festlegen. |
| AuditLogger ohne Kettenfelder | Event-/Audit-Zusammenführung ist heuristisch. | eingeschränkt | Supervisor muss Auditlog-Kopplungsmodell entscheiden. |
| Registry `last_update_event_id` | Nützlich als letzter Eventverweis, aber keine Correlation/Causation. | eingeschränkt | Export darf es nicht als vollständige Kette darstellen. |
| Read-Tracking mit `session_id` | Fachliche Klammer im Payload, kein Ersatz für Event-Causation. | eingeschränkt | Read-Receipt-Kette später konkretisieren. |
| Signaturereignisse ohne Documents-Causation | Signatur ist eigene Eventfamilie ohne Workflow-Auslöserbezug. | eingeschränkt | Signatur-/Workflow-Causation später entscheiden. |
| technische `system`-Folgeprozesse | Müssen entweder echte Systemaktion sein oder kausal an fachlichen Auslöser gebunden werden. | ohne Causation eingeschränkt/legacy | AP-012-System-Policy und diese ADR gemeinsam anwenden. |

## Nicht-Entscheidungen
- Keine konkrete API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Kein Exportformat.
- Kein Backend-Transportmodell.
- Keine RequestContext-Implementierung.
- Keine UserContext-Implementierung.
- Keine AuditActor-Implementierung.
- Keine Änderung an AuditLogger, EventEnvelope, Documents-Services, Signaturmodul, GUI, CLI, Backend oder Tests.
- Keine Entscheidung, welche technische ID-Form `causation_id` konkret referenziert.
- Keine Migration oder rückwirkende Rekonstruktion bestehender Events.
- Keine Entscheidung über elektronische Signatur, Re-Auth oder rechtliches Signaturniveau.

## Konsequenzen
- Für Documents-Services:
  - Services bleiben fachliche Grenze, an der später entschieden wird, welche Ketten zu welchem Use Case gehören.
  - Implementierungsvorbereitung muss pro Use Case klären, wo Correlation/Causation entsteht und wie sie durchgereicht wird.
- Für Events:
  - Bestehendes Event-Schema wird durch AP-014 nicht geändert.
  - Zielsemantik verlangt aber später eine explizite Kettenweitergabe für MVP-Nachweisketten.
- Für Auditlog:
  - Auditlog muss später entweder eigene Kettenfelder erhalten oder zuverlässig exportseitig mit Domain-Events verbunden werden.
  - Bis dahin sind Auditlog/Event-Ketten für MVP-Exports eingeschränkt.
- Für GUI/CLI:
  - GUI/CLI dürfen Kontext transportieren, aber nicht fachlich entscheiden, welche Actor- oder Nachweisqualität gilt.
  - GUI-/CLI-Zustand bleibt keine Actor-Quelle und keine Kettenwahrheit.
- Für Backend:
  - Backend darf später Request-/Transportkontext liefern, aber keine fachlichen Actor-, Rollen- oder Nachweisentscheidungen treffen.
  - Kein Backend-Feature ist durch diese ADR freigegeben.
- Für Audit-Export / Nachweispaket:
  - Actor-Qualität und Kettenqualität müssen getrennt sichtbar bleiben.
  - Technische Folgeprozesse ohne Causation dürfen nicht als vollständig erklärbare Nachweiskette erscheinen.
  - Legacy-Ereignisse ohne Kette dürfen nicht rückwirkend aufgewertet werden.
- Für Tests:
  - Keine Tests werden in AP-014 geändert.
  - Spätere Tests müssen Zielsemantik für Correlation/Causation getrennt von Actor-Semantik prüfen.

## Risiken
- Technische Risiken:
  - Zu frühe API-/Schemafestlegung könnte viele Servicegrenzen berühren.
  - Ohne zentrale Kontextquelle entstehen weiterhin Einzel-Correlations statt Use-Case-Ketten.
  - Auditlog- und Eventmodell können auseinanderlaufen, wenn die Kopplung nicht entschieden wird.
- Fachliche Risiken:
  - Causation kann irrtümlich als Verantwortlichkeit gelesen werden.
  - `system`-Folgeprozesse können trotz Causation menschliche Verantwortung verdecken, wenn Actor-Status nicht getrennt bleibt.
  - Signatur-Actor und Workflow-/AuditActor können vermischt werden.
- Migrationsrisiken:
  - Bestand ohne Kettenfelder kann nicht verlustfrei rückwirkend rekonstruiert werden.
  - Backend-migrierte Use Cases dürfen keine halb lokalen Kettenkontexte behalten.
  - Legacy-/Importfälle brauchen sichtbaren Kettenstatus.
- Audit-/Nachweisrisiken:
  - Exporte könnten Default-Correlation fälschlich als belastbare Nachweiskette darstellen.
  - Technische Folgeprozesse ohne Causation können isoliert oder unbegründet wirken.
  - Fehlende Auditlog/Event-Verbindung kann Nachweispakete angreifbar machen.

## Offene Supervisor-Entscheidungen
- Bekommt Auditlog später eigene Correlation/Causation-Felder, oder erfolgt die Kopplung ausschließlich über Export-/Nachweispaketlogik?
- Soll `causation_id` auf Event-ID, Command-ID oder eine spätere Use-Case-ID zeigen?
- Welche Documents-MVP-Use-Cases benötigen harte Causation-Pflicht vor dem ersten belastbaren Nachweispaket?
- Wie werden bestehende Legacy-Events ohne Kette im Export konkret benannt: `ketten-eingeschränkt`, `ketten-legacy` oder anderes Vokabular?
- Braucht RELEASED_PDF-Erzeugung ein eigenes Event/Audit oder reicht Causation zum Approval-Event?
- Wird `session_id` beim Read-Tracking als fachliche Klammer zusätzlich zur Event-Correlation geführt, und wie wird das im Export dargestellt?
- Wie werden Signaturereignisse kausal mit Documents-Workflow-Transitions verbunden, ohne Signatur-Actor und AuditActor gleichzusetzen?
- Welches technische System-/Service-Actor-Namensschema gilt gemeinsam mit Correlation/Causation?

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
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`.
  - `ReadFile` für alle freigegebenen Grundlagen.
  - Keine Code-Suchläufe, weil der AP-014-Scope nur bestehende ADR-/Inventar-/Regeldateien lesend freigibt.
- Keine Testsuite ausgeführt, weil AP-014 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich verboten sind.
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
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob ein reines Analysepaket `Documents-Audit-Export-Readiness-Matrix` freigegeben oder zurückgestellt wird; keine Implementierung automatisch starten.
