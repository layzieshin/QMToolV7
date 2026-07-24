# AP-017 Documents-Release-PDF-Nachweisereignis ADR

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
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` trennt AuditActor, System Actor, Unknown, Correlation und Causation. Correlation/Causation erklären Ketten, ersetzen aber keinen Actor.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` verlangt sichtbare Actor-Qualität für MVP-Audit-Exports.
- Bezug auf AP-009/AP-011: Documents-Analysen markieren RELEASED_PDF und technische PDF-Folgeprozesse als export- und nachweisrelevante Lücke.
- Bezug auf AP-012: Owner-/`system`-Fallbacks dürfen keinen menschlichen Workflow-Actor ersetzen. Technische Folgeprozesse dürfen nur mit erklärbarer System-/Service-Actor-Semantik erscheinen.
- Bezug auf AP-013/AP-014: RELEASED_PDF-Erzeugung ist aktuell nicht kausal an ein fachliches Ausgangsereignis gekoppelt. Technische Folgeprozesse brauchen im Zielbild Correlation/Causation, wenn sie Teil einer Nachweiskette sind.
- Bezug auf AP-015: RELEASED_PDF ohne eigenes Nachweisereignis ist blockierend für eine vollständig belastbare Freigabe-Nachweiskette.
- Bezug auf AP-016: Domain-Events und Auditlog-Einträge bleiben getrennte Artefakte, sollen aber bei auditrelevanten Documents-Use-Cases konsistent aus derselben Service-Nachweisentscheidung entstehen.
- Aktueller Hotspot:
  - `modules/documents/workflow_use_cases.py` erzeugt bei Approval/Freigabe ein fachliches Approval-Event und ein Auditlog.
  - Danach wird `modules/documents/service.py` zur RELEASED_PDF-Erzeugung aufgerufen.
  - `_ensure_release_pdf_artifact` erzeugt aktuell ein `RELEASED_PDF`-Artefakt, aber im gelesenen Code kein eigenes Domain-Event, keinen eigenen Auditlog-Eintrag und keine explizite Causation.
  - `qm_platform/events/event_envelope.py` kann Correlation/Causation tragen, Documents-Eventing übergibt sie aktuell aber nicht explizit.
  - `qm_platform/logging/audit_logger.py` schreibt Auditlog-Zeilen ohne Correlation/Causation.

## Begriffe
- **Fachliche Freigabe / Approval**: Menschlicher Workflow-Schritt, in dem ein berechtigter Approver die Dokumentversion fachlich freigibt oder ablehnt.
- **Release**: Fachlicher Freigabezustand der Dokumentversion im Documents-Workflow. Release ist nicht automatisch identisch mit der Erzeugung eines PDF-Artefakts.
- **RELEASED_PDF**: Technisches, erzeugtes PDF-Artefakt einer freigegebenen Dokumentversion. Es kann Nachweisrelevanz haben, ist aber keine eigenständige menschliche Freigabehandlung.
- **Technischer PDF-Folgeprozess**: Automatischer oder service-naher Prozess, der aus einem fachlichen Workflow-Ereignis ein PDF-Artefakt erzeugt, schützt, kopiert oder bereitstellt.
- **Workflow-Actor**: Menschlicher Actor des fachlichen Workflow-Schritts, z. B. der Approver.
- **Technischer Actor / System Actor / Service Actor**: Nicht-menschliche technische Identität für einen echten technischen Folgeprozess. Sie darf den Workflow-Actor nicht ersetzen.
- **Nachweisereignis**: Policy-Begriff für ein auditnahes, getrennt darstellbares Ereignis in einer späteren Nachweiskette. Kein Event-Schema, keine API und kein Exportformat.

## Entscheidung
Empfohlene Ziel-Policy:

RELEASED_PDF ist im Documents-MVP nicht pauschal dieselbe fachliche Handlung wie Review, Approval oder Release/Freigabe. Die fachliche Approval-Entscheidung bleibt der menschliche Workflow-Schritt mit menschlichem Approver als Workflow-/AuditActor. Die RELEASED_PDF-Erzeugung ist ein technischer Artefakt- und Folgeprozess, der aus dieser fachlichen Entscheidung oder aus einem später freigegebenen Release-Command erklärbar sein muss.

Für eine vollständig belastbare Freigabe-Nachweiskette darf RELEASED_PDF nicht nur als unsichtbares Artefakt-Metadatum erscheinen. Der technische Folgeprozess muss im Zielbild getrennt vom menschlichen Approval darstellbar sein: als eigenes auditrelevantes Folgeereignis, als eigener Auditlog-/Nachweiseintrag oder als beides. Welche technische Ausprägung verbindlich wird, bleibt Supervisor-Entscheidung; diese ADR trifft keine Event-Schema-, Auditlog-Schema-, API- oder Exportformatentscheidung.

Wenn RELEASED_PDF im MVP-Nachweis erscheint, muss es als technischer Folgeprozess dargestellt werden. Der menschliche Approver darf dabei als fachlicher Auslöser erscheinen, aber nicht still als technischer Actor der PDF-Erzeugung. Ein technischer `system`-/Service Actor ist nur zulässig, wenn die Kette zum fachlichen Ausgangsereignis oder Command sichtbar bleibt.

Ohne belastbare Causation zum fachlichen Ausgangsereignis oder Command darf RELEASED_PDF nicht als voll `kettenbelastbar` gelten. Correlation/Causation erklärt technische Verkettung und Auslöser, ersetzt aber weder den menschlichen Workflow-Actor noch den technischen Actor.

Bestehende RELEASED_PDF-Bestände ohne eigenes Nachweisereignis bleiben für einen vollständig belastbaren MVP-Freigabeexport eingeschränkt. Sie können als technisches Artefakt-Metadatum oder Legacy-/Bestandsartefakt markiert werden, dürfen aber nicht rückwirkend als vollständig belegtes Folgeereignis behauptet werden.

## Nachweischarakter von RELEASED_PDF

| Darstellungsform | Policy-Bewertung | Bedingung | MVP-Auswirkung |
| --- | --- | --- | --- |
| Reines technisches Artefakt ohne Nachweiskette | zulässig nur als Bestands-/Artefaktmetadatum | Keine Behauptung einer vollständig belastbaren Freigabe-Nachweiskette. | `ketten-eingeschränkt` oder `ketten-legacy` für die technische Folge. |
| Auditrelevantes technisches Folgeereignis | Zielbild ja | Kausal auf Approval/Release-Command zurückführbar; Actor-Status getrennt bewertet. | Zielrichtung für vollständige Freigabe-Nachweiskette. |
| Eigener Auditlog-/Nachweiseintrag | offen/empfohlen für Nachweispaket, aber Supervisor-Entscheidung | Muss aus derselben Service-Nachweisentscheidung oder einem erklärbaren Folgeprozess stammen. | Ohne Entscheidung nicht implementieren; aktueller Bestand eingeschränkt. |
| Domain-Event plus Auditlog | Zielbild fachlich plausibel, aber technisch offen | AP-016-Kopplungsregel beachten; keine Feld-/Schemaentscheidung in AP-017. | Wahrscheinlich belastbarste Zielrichtung, aber separat freizugeben. |
| Gleichsetzung mit fachlicher Freigabe | nein | RELEASED_PDF ist kein Review, kein Approval und keine menschliche Freigabehandlung. | Unzulässig für belastbaren Audit-Export. |

## Verhältnis zu fachlicher Freigabe
- Approval/Freigabe ist der fachliche Workflow-Schritt.
- RELEASED_PDF ist der technische Artefakt-/Erzeugungsschritt nach der fachlichen Freigabe oder nach einem freigegebenen technischen Release-Command.
- Beide Ereignisse dürfen nicht still denselben Actor, dieselbe Nachweisqualität oder dieselbe Exportbedeutung erhalten.
- Der Approver kann Auslöser der Kette sein, aber nicht automatisch technischer Actor der PDF-Erzeugung.
- Ein technischer Folgeprozess darf die fachliche Approval-Spur nicht verdecken. Der Freigabe-Nachweis muss weiterhin zeigen, wer fachlich freigegeben hat.
- Ein vorhandenes RELEASED_PDF darf ohne fachliche Approval-/Release-Spur nicht als Beleg für eine menschliche Freigabe verstanden werden.

## Actor-Policy

| Actor-/Quellenfall | Zulässigkeit | Nachweisstatus | Policy |
| --- | --- | --- | --- |
| Menschlicher Approver aus freigegebenem UserContext/RequestContext | ja für Approval | `belastbar` nach Quellklassifikation | Actor der fachlichen Freigabe, nicht automatisch Actor der technischen PDF-Erzeugung. |
| Heutiger Approver-Parameter aus CLI/PyQt/Adapter | eingeschränkt | `eingeschränkt` bis Quelle klassifiziert ist | Kann fachliche Approval-Spur tragen, aber nicht technische Folgeprozess-Governance ersetzen. |
| `system` für RELEASED_PDF-Folgeprozess | ja/eingeschränkt | `belastbar` nur bei echter System-/Service-Aktion und erklärbarer Causation | Zulässig, wenn der Prozess technisch ist und kausal zum Ausgangsereignis bleibt. |
| Benannter Service Actor für RELEASED_PDF-Folgeprozess | offen/ja | abhängig von Governance | Supervisor muss Namensschema und Zulässigkeit entscheiden. |
| Menschlicher Workflow-Actor als technischer PDF-Actor | nein als stiller Default | höchstens Auslöser, nicht technischer Actor | Nur zulässig, wenn ein späteres Paket fachlich entscheidet, dass derselbe Mensch die technische Aktion explizit ausführt. |
| Owner-Fallback | nein als belastbarer Actor | `legacy`/nicht belastbar | Owner ist Verantwortlichkeits-/Objektmetadatum, kein Beleg für Ausführung der PDF-Erzeugung. |
| `unknown` | nein | `legacy`/nicht belastbar | Höchstens Alt-/Importmetadatum, kein AuditActor. |

## Correlation-/Causation-Policy
- RELEASED_PDF muss im Zielbild kausal auf ein fachliches Ausgangsereignis oder einen freigegebenen Command zurückführbar sein.
- Geeignete fachliche Auslöser sind insbesondere Approval/Freigabe oder ein später definierter Release-/PDF-Generation-Command.
- Ohne belastbare Causation darf RELEASED_PDF nicht als voll `kettenbelastbar` gelten.
- Correlation gruppiert die Freigabe-/Artefaktkette; Causation erklärt den konkreten Auslöser der PDF-Erzeugung.
- Ob Causation auf Approval-Event, Release-Event, Command oder Use-Case-ID zeigt, bleibt ausdrücklich offen.
- Bestehende Default-Correlation einzelner Events reicht nicht als vollständige Freigabe-Nachweiskette.

## Auditlog-/Event-Kopplung
- Zielbild:
  - RELEASED_PDF muss getrennt von Approval/Release darstellbar sein, wenn eine vollständig belastbare Freigabe-Nachweiskette behauptet wird.
  - Die Darstellung soll mit AP-016 kompatibel aus derselben Service-Nachweisentscheidung oder einem klar gekoppelten technischen Folgeprozess entstehen.
  - Event-Actor, Auditlog-Actor, technischer Actor und fachlicher Workflow-Actor müssen konsistent erklärbar sein.
- Ausdrücklich offen:
  - ob RELEASED_PDF ein eigenes Domain-Event bekommt,
  - ob RELEASED_PDF einen eigenen Auditlog-Eintrag bekommt,
  - ob Domain-Event plus Auditlog verbindlich wird,
  - ob ein technisches Artefakt-Nachweisobjekt statt Event/Auditlog eingeführt wird,
  - ob die Kopplung über Event-ID, Audit-ID, Command-ID, Use-Case-ID oder andere technische Referenz erfolgt.
- Unzulässig:
  - RELEASED_PDF nur heuristisch über Zeitstempel, Dateipfad oder Statuswechsel als voll belastbare Nachweiskette zu behaupten.
  - Approval-Auditlog und RELEASED_PDF-Artefakt still als denselben Nachweiseintrag zu behandeln.
  - technische PDF-Erzeugung als menschliche Freigabehandlung zu exportieren.

## MVP-Export-Auswirkung
- Fehlendes RELEASED_PDF-Nachweisereignis ist blockierend für eine vollständig belastbare technische Freigabe-Folgekette.
- Fehlendes RELEASED_PDF-Nachweisereignis blockiert nicht zwingend die eingeschränkte Darstellung der menschlichen Approval-Entscheidung, sofern deren Actor- und Event-/Auditlog-Status separat als eingeschränkt oder belastbar nach Quellklassifikation ausgewiesen wird.
- Technische Artefaktfolgeprozesse müssen gegenüber menschlichen Workflow-Ereignissen getrennt dargestellt werden:
  - menschlicher Workflow-Schritt: Actor, Rolle/Berechtigung, Target, Ergebnis, Grund,
  - technischer PDF-Folgeprozess: technischer Actor/System-/Service-Actor-Status, Artefaktbezug, Causation zum Auslöser, Kettenstatus,
  - Legacy-/Bestandsartefakt: sichtbare Einschränkung ohne rückwirkend behauptete Causation.
- Bestehende RELEASED_PDF-Bestände ohne Nachweisereignis dürfen nicht still aufgewertet werden. Sie brauchen später eine Supervisor-Entscheidung zur Kennzeichnung.

## Umgang mit aktuellem Zustand

| Fundtyp | Aktueller Zustand | Policy-Bewertung | Spätere Behandlung |
| --- | --- | --- | --- |
| Approval akzeptieren | Domain-Event und Auditlog vorhanden; Approver wird übergeben und geprüft. | Fachlicher Freigabeschritt wirkt tragfähig, Quelle und Kette bleiben einzuschränken. | Actor-Quelle und Event/Audit-Kopplung später absichern. |
| `_ensure_release_pdf_artifact` | Erzeugt `RELEASED_PDF` als Artefakt ohne eigenes Event/Audit im gelesenen Code. | Nicht vollständig kettenbelastbar als technische Freigabefolge. | Supervisor muss Nachweisform entscheiden. |
| `EventEnvelope.create` | Unterstützt Correlation/Causation, aber Documents-Eventing übergibt sie nicht explizit. | Default-Correlation ist keine Freigabe-/Release-Kette. | Keine Änderung in AP-017; spätere Kontextentscheidung nötig. |
| `AuditLogger.emit` | Auditlog hat `audit_id`, aber keine Correlation/Causation. | Event/Audit/Artefakt nur heuristisch verbindbar. | Kopplungsentscheidung aus AP-016 fortführen. |
| Bestehende RELEASED_PDF-Artefakte | Artefakt kann existieren, ohne Nachweisereignis. | Artefaktmetadatum, nicht automatisch Nachweisereignis. | Kennzeichnung als eingeschränkt/legacy entscheiden. |

## Nicht-Entscheidungen
- Keine konkrete API.
- Keine API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Migration.
- Keine Backend-Route.
- Keine Implementierung von UserContext, RequestContext, AuditActor, Eventkopplung oder Audit-Export.
- Keine Änderung an Documents-Services, EventEnvelope, AuditLogger, LogQueryService, GUI, CLI, Backend oder Tests.
- Keine Entscheidung, welche technische ID-Form `causation_id` konkret referenziert.
- Keine Entscheidung, ob bestehende RELEASED_PDF-Artefakte nachträglich migriert oder rekonstruiert werden.

## Konsequenzen
- Für Documents-Services:
  - Services bleiben die fachliche Grenze für Approval, Release und technische Folgeprozesse.
  - Spätere Pakete müssen pro Use Case entscheiden, wo die Service-Nachweisentscheidung und die technische Folgeprozess-Grenze liegen.
- Für Actor-Semantik:
  - Workflow-Actor und technischer PDF-Actor bleiben getrennt.
  - `system` oder Service Actor ist nur bei erklärbarer technischer Folge zulässig.
  - Owner-Fallback und `unknown` bleiben nicht belastbar.
- Für Kettenstatus:
  - RELEASED_PDF ohne Causation ist mindestens `ketten-eingeschränkt`.
  - Legacy-/Bestandsartefakte ohne rekonstruierbare Kette bleiben `ketten-legacy` oder gleichwertig zu markieren.
- Für Audit-Export / Nachweispaket:
  - Approval/Freigabe und RELEASED_PDF müssen getrennt darstellbar sein.
  - Ein Export darf die technische Artefakterzeugung nicht als menschliche Freigabehandlung ausgeben.
  - Die konkrete Exportdarstellung bleibt offen.
- Für Tests:
  - Keine Tests werden in AP-017 geändert.
  - Spätere Tests müssen fachliche Approval-Spur, technische PDF-Folge, Actor-Status und Kettenstatus getrennt prüfen.

## Risiken
- Technische Risiken:
  - Eine spätere Event-/Auditlog-Entscheidung kann Eventing, AuditLogger, Servicegrenzen und Tests berühren.
  - Ohne Causation bleibt RELEASED_PDF nur indirekt über Status und Artefaktbestand nachvollziehbar.
  - Zu frühe Feld- oder Schemaentscheidung könnte die AP-016-Kopplungsentscheidung vorwegnehmen.
- Fachliche Risiken:
  - RELEASED_PDF könnte fälschlich als eigentliche Freigabehandlung gelesen werden.
  - Ein technischer `system`-Actor könnte menschliche Approval-Verantwortung verdecken.
  - Ein menschlicher Approver könnte fälschlich als Actor der technischen PDF-Erzeugung erscheinen.
- Audit-/Nachweisrisiken:
  - Vollständige Freigabe-Nachweisketten wirken belastbarer, als sie sind, wenn RELEASED_PDF nur heuristisch gekoppelt wird.
  - Bestehende Artefakte ohne Nachweisereignis könnten rückwirkend überinterpretiert werden.
  - Exportdarstellung kann Actor-Qualität und Kettenqualität vermischen.

## Offene Supervisor-Entscheidungen
- Braucht RELEASED_PDF ein eigenes Domain-Event?
- Braucht RELEASED_PDF einen eigenen Auditlog-Eintrag?
- Soll für RELEASED_PDF im Zielbild Domain-Event plus Auditlog verbindlich werden?
- Bleibt technische PDF-Erzeugung Teil des Documents-Exports oder nur Artefakt-Metadatum mit Kettenstatus?
- Soll der technische Actor `system` heißen oder als benannter Service Actor geführt werden?
- Soll Causation auf Approval-Event, Release-Event, Command oder Use-Case-ID zeigen?
- Wie werden bestehende RELEASED_PDF-Bestände ohne Nachweisereignis markiert?
- Welche Freigabe-/Release-Fälle müssen vor einem ersten belastbaren MVP-Audit-Export zwingend eine RELEASED_PDF-Folge nachweisen?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`
  - `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md`
  - `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md`
  - `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`
  - `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`
  - `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`
  - `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`
  - `modules/documents/service.py`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/eventing.py`
  - `modules/documents/artifact_ops.py`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
  - `qm_platform/logging/log_query_service.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md`.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Documents-/Event-/Auditlog-Hotspots.
  - `rg` in `modules/documents` nach RELEASED_PDF-, SOURCE_PDF-, Event-, Audit-, Actor-, Correlation-/Causation- und Fallback-Begriffen.
  - `rg` in `qm_platform/logging` nach Audit-/Export-/Correlation-/Causation-Begriffen.
  - `rg` in `tests` nur zur Einordnung vorhandener RELEASED_PDF-/Approval-Testbezüge; keine Tests wurden ausgeführt oder geändert.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-017 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Nur `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob ein reines ADR-Paket `Documents-Signatur-vs-Audit-Actor-Matrix` oder ein enges Umsetzungsvorbereitungspaket für genau die RELEASED_PDF-Nachweisform freigegeben wird; keine Implementierung automatisch starten.
