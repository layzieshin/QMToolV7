# AP-021 Use-Case-/Command-ID-Strategie ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Auditlog-Schema-Änderung: nein
- Audit-Export-Implementierung: nein
- Exportformat-Entscheidung: nein
- Command-/Use-Case-ID-Implementierung: nein
- Migration: nein

## Kontext
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert Correlation/Causation als Kettenbegriffe, die keinen Actor ersetzen.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` trennt Actor-Nachweisstatus von Ketten-/Kontextstatus.
- Bezug auf AP-013: `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` zeigt, dass vorhandene Documents-nahe Events zwar `event_id` und Default-`correlation_id` tragen, aber keine explizite Causation, Use-Case-ID oder Command-ID.
- Bezug auf AP-014: `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md` lässt offen, ob Causation auf Event-ID, Command-ID oder Use-Case-ID zeigt.
- Bezug auf AP-015: `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md` bewertet Documents-Flows ohne belastbare Kettenreferenz als `ketten-eingeschränkt` oder `ketten-legacy`.
- Bezug auf AP-016: `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md` verlangt konsistente Erklärbarkeit von Domain-Event und Auditlog aus derselben service-seitigen Nachweisentscheidung.
- Bezug auf AP-017: `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md` trennt fachliche Freigabe und technische PDF-Folgeprozesse und lässt die technische Zielreferenz offen.
- Bezug auf AP-018: `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md` trennt Signatur-Actor von AuditActor; Causation muss diese Trennung stützen, nicht ersetzen.
- Bezug auf AP-019: `docs/AP-019_DOCUMENTS_SIGNATURE_CAUSATION_REFERENCE_ADR.md` bevorzugt Signatur-Command bzw. service-seitigen Use-Case-/Command-Kontext als direkten Signaturauslöser.
- Bezug auf AP-020: `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md` entscheidet, dass Auditlog im Zielbild auditlog-seitig verfügbare Ketteninformationen braucht, ohne konkrete Felder festzulegen.
- Aktueller Hotspot:
  - `qm_platform/events/event_envelope.py` erzeugt `event_id` und Default-`correlation_id`; `causation_id` bleibt ohne Übergabe leer.
  - `qm_platform/logging/audit_logger.py` erzeugt `audit_id`, aber keine Kettenreferenzen.
  - `modules/documents/workflow_use_cases.py` stempelt `last_event_id`, verbindet aber Auditlog und Event nicht belastbar.
  - `modules/documents/pdf_read_tracking_service.py` nutzt `session_id` als fachliche Read-Tracking-Klammer, nicht als Event-/Audit-Correlation.
  - `modules/signature/signature_execute_ops.py` nutzt `SignRequest` als Signaturauftrag, aber ohne explizite Command-ID.

## Begriffsabgrenzung
- **Use-Case-ID**: Technische Klammer eines service-seitigen fachlichen Use-Case-Aufrufs oder einer service-seitigen Nachweisentscheidung. Sie gruppiert zusammengehörige Commands, Events, Auditlogs und Folgeprozesse. Sie ist kein Actor, keine Rolle, kein UserContext und keine Autorisierungsentscheidung.
- **Command-ID**: Technische Identität eines konkreten Auftrags oder einer konkreten Aktion innerhalb eines Use Cases, z. B. Workflow-Transition ausführen, Signatur ausführen, PDF-Folgeprozess anstoßen oder Read-Session finalisieren. Sie eignet sich als unmittelbarer Auslöser für Causation.
- **Event-ID**: Identität eines erzeugten Domain-Events. Sie eignet sich als Referenz, wenn ein Folgeprozess tatsächlich durch ein bereits erzeugtes Event ausgelöst oder als Reaktion auf dieses Event ausgeführt wird.
- **Auditlog-ID / `audit_id`**: Identität einer Auditlog-Zeile. Sie identifiziert den Auditlog-Eintrag, ist aber nicht automatisch fachlicher Auslöser.
- **Correlation-ID**: Klammer einer technischen Kette oder eines Use-Case-Zusammenhangs. Sie kann einer Use-Case-ID entsprechen oder aus ihr abgeleitet werden; das bleibt technisch offen.
- **Causation-ID**: Referenz auf den unmittelbaren Auslöser innerhalb einer Kette. Sie beschreibt Richtung und Auslöser, nicht Verantwortung.

Diese Ebenen dürfen nicht still vermischt werden. Use-Case-ID gruppiert, Command-ID beauftragt, Event-ID belegt ein Ereignis, Auditlog-ID identifiziert eine Auditzeile, Correlation-ID klammert und Causation-ID erklärt Auslöserrichtung.

## Entscheidung
Empfohlene Ziel-Policy:

Im Zielbild soll die Use-Case-ID die bevorzugte service-seitige Klammer für auditrelevante Use Cases und Nachweisketten sein. Sie ordnet Domain-Events, Auditlog-Einträge, technische Folgeprozesse, Signaturteilketten, Read-Tracking-Teilketten und Artefaktfolgen einem fachlich zusammengehörigen Service-Aufruf oder Nachweisvorgang zu.

Die Command-ID soll der bevorzugte unmittelbare Causation-Auslöser sein, wenn ein konkreter Auftrag oder eine konkrete Transition die nächste Aktion verursacht. Das betrifft insbesondere Workflow-Transitions, Signaturaufträge, technische PDF-Folgeprozesse, Kommentar-Sync und Read-Tracking-Completion. Command-ID ist fachlich sauberer als Event-ID, wenn der auslösende Auftrag vor dem Event existiert oder sowohl Event als auch Auditlog aus derselben service-seitigen Nachweisentscheidung entstehen.

Event-ID genügt als Causation-Ziel, wenn ein Folgeprozess tatsächlich reaktiv auf ein bereits erzeugtes Domain-Event läuft oder wenn ein technischer Listener/Projektor einen Zustand aus einem Event fortschreibt. Event-ID ist nicht automatisch ausreichend, wenn Auditlog und Domain-Event Geschwister derselben Nachweisentscheidung sind.

Auditlog-ID soll im Zielbild nur ausnahmsweise Causation-Ziel sein. Zulässig ist sie höchstens für auditlog-interne Folgeeinträge, Korrektur-/Ergänzungsnachweise oder explizit auditlog-getriebene Prozesse. Für fachliche Documents-/Signatur-/Read-/Release-Ketten ist Auditlog-ID nicht der bevorzugte Auslöser; dort sind Command-ID, Use-Case-ID oder Event-ID fachlich sauberer.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Auditlog-Schema, kein Exportformat und keine Implementierung.

## Referenzstrategie

| Kettenfrage | Bevorzugte Zielrichtung | Bedingung | Nicht still verwenden |
| --- | --- | --- | --- |
| Gesamter fachlicher Use Case | Use-Case-ID als Klammer bzw. Correlation-Grundlage | Mehrere Events, Auditlogs oder Folgeprozesse gehören zu einem service-seitigen Aufruf. | Event-ID als Gesamtklammer. |
| Unmittelbarer Auftrag | Command-ID als Causation-Ziel | Ein konkreter Auftrag löst Event, Auditlog oder technische Folge aus. | Auditlog-ID als fachlicher Auftrag. |
| Eventgetriebener Folgeprozess | Event-ID als Causation-Ziel | Der Folgeprozess reagiert wirklich auf ein bereits erzeugtes Domain-Event. | Event-ID, wenn Event und Auditlog nur Geschwister derselben Entscheidung sind. |
| Auditlog-interne Folge | Auditlog-ID offen/ausnahmsweise | Nur bei Korrektur, Ergänzung oder Auditlog-Folgeeintrag. | Auditlog-ID für Workflow-, Signatur- oder Release-Fachauslöser. |
| Mehrere technische Teilketten | Gemeinsame Use-Case-ID plus lokale Command-/Event-Causation | Teilketten bleiben getrennt, aber fachlich rückführbar. | Eine einzige Event-ID für alle Ebenen. |
| Legacy ohne IDs | sichtbarer Legacy-/Kettenstatus | Keine rückwirkende Rekonstruktion behaupten. | Nachträglich erfundene Use-Case-/Command-ID. |

## Causation-Ziel im Zielbild
- Bevorzugt auf **Command-ID**, wenn:
  - ein fachlicher Auftrag oder eine Workflow-Transition der unmittelbare Auslöser ist,
  - Event und Auditlog aus derselben service-seitigen Entscheidung entstehen,
  - technische Folgeprozesse vor oder neben Domain-Events laufen,
  - Signatur- oder PDF-Folgeprozesse als Auftrag ausgeführt werden.
- Bevorzugt auf **Event-ID**, wenn:
  - ein Prozess wirklich eventgetrieben ist,
  - ein Projektor, Registry-Update, Readmodel oder technischer Listener aus einem Domain-Event folgt,
  - ein technischer Folgeprozess nachweislich erst durch ein publiziertes Event ausgelöst wird.
- Bevorzugt auf **Use-Case-ID**, wenn:
  - kein einzelner Command die Richtung sauber beschreibt,
  - mehrere Commands zu einer übergeordneten Nachweisentscheidung gehören,
  - eine Kette zunächst nur gruppiert, aber nicht bis auf Teilcommand-Ebene entschieden werden soll.
- **Auditlog-ID** als Causation-Ziel bleibt Supervisor-Entscheidung und ist nur für auditlog-interne Folgefälle plausibel.

## Documents-MVP-Auswirkung

| Documents-MVP-Fall | Zielstrategie | Kettenbewertung |
| --- | --- | --- |
| Workflow-Transitions | Use-Case-ID klammert den Aufruf; Command-ID beschreibt Transition als Auslöser; Domain-Event und Auditlog teilen dieselbe Nachweisentscheidung. | Ohne Use-Case-/Command-Kontext bleibt Event/Audit-Kopplung `ketten-eingeschränkt`. |
| Review/Approval | Command-ID für Review-/Approval-Entscheidung bevorzugt; Event-ID nur für spätere eventgetriebene Folgen. | Actor-Status des Reviewers/Approvers bleibt separat. |
| Release/Freigabe | Use-Case-ID klammert Approval, Release-Kontext und technische Folgen; Command-ID oder Event-ID für konkrete Release-Folge offen. | Ohne klare Folge-Causation keine volle Freigabe-Folgekette. |
| RELEASED_PDF / technische PDF-Folgeprozesse | Causation auf Release-/PDF-Generation-Command bevorzugt; Event-ID nur wenn eventgetrieben; Use-Case-ID als Klammer. | Ohne Nachweisereignis oder Command/Event-Bezug `ketten-eingeschränkt` bis `ketten-legacy`. |
| Read-Tracking / Read Receipt | `session_id` bleibt fachliche Read-Session-Klammer; Use-Case-/Command-ID nötig, wenn Audit-/Event-Kette belastbar sein soll. | `session_id` allein macht keine Audit-/Event-Kette. |
| Kommentar-Sync | Sync-Command oder Import-/Use-Case-ID bevorzugt; Event-ID nur bei eventgetriebenem Sync. | DOCX-Autor, Sync-Actor und AuditActor bleiben getrennt. |
| Signatur-nahe Documents-Flows | Use-Case-ID klammert Workflow und Signatur; Signatur-Command ist bevorzugter direkter Auslöser; Event-ID für technische Folge nur bei echter Eventreaktion. | Ohne fachlichen Parent bleibt Signatur/Documents-Kette `ketten-eingeschränkt`. |

## Auditlog-/Event-Kopplung
- Zielregel:
  - Domain-Events und Auditlog sollen für auditrelevante Use Cases über gemeinsame Use-Case-/Command-ID oder gleichwertigen Kontext erklärbar sein.
  - Event-ID-Verweise reichen aus, wenn der Auditlog-Eintrag ein konkretes bereits erzeugtes Event begleitet oder ein Folgeprozess reaktiv daraus entsteht.
  - Event-ID-Verweise reichen nicht aus, wenn Event und Auditlog Geschwister derselben service-seitigen Entscheidung sind und eine übergeordnete Use-Case-/Command-Klammer fehlt.
- Getrennte Teilketten sind zulässig, wenn:
  - sie über Use-Case-ID oder gleichwertigen Parent fachlich rückführbar bleiben,
  - der Nachweis getrennte Kettenstatus sichtbar macht,
  - Signatur-, Documents-, Read- und technische Service-Actors nicht vermischt werden.
- Offen bleibt:
  - ob Auditlog Use-Case-ID, Command-ID, Event-ID oder Correlation/Causation direkt trägt,
  - ob Domain-Events dieselben IDs direkt tragen,
  - ob technische Logs beteiligt werden,
  - ob ein späterer RequestContext diese IDs transportiert.

## Nachweisstatus
- `kettenbelastbar` ist erst möglich, wenn:
  - eine Use-Case-ID oder gleichwertige Correlation die fachliche Kette gruppiert,
  - Command-ID, Event-ID oder gleichwertige Causation den unmittelbaren Auslöser erklärt,
  - Auditlog und Domain-Event nicht nur über Zeit/Action/Target heuristisch verbunden werden,
  - Actor-Status und Kettenstatus getrennt bewertet werden.
- `ketten-eingeschränkt` gilt, wenn:
  - nur Event-ID oder Default-Correlation je Einzelereignis vorhanden ist,
  - Auditlog keine belastbare Kettenreferenz trägt,
  - `session_id`, Dateipfad, Zielobjekt oder Status als Hilfsklammer genutzt werden, aber keine technische Use-Case-/Command-Kette existiert,
  - Signatur- oder PDF-Folgeprozesse ohne fachlichen Parent erscheinen.
- `ketten-legacy` gilt, wenn:
  - Altbestand keine Use-Case-ID, Command-ID oder rekonstruierbare Event-/Audit-Kopplung besitzt,
  - Ketten nur nachträglich geraten würden,
  - freie Strings, Owner-/`system`-Fallbacks oder vorhandene Log-Exports keine belastbare Kette ermöglichen.

Actor-Status bleibt getrennt:
- Ein belastbarer Actor macht eine fehlende Use-Case-/Command-ID nicht automatisch `kettenbelastbar`.
- Eine saubere Use-Case-/Command-Kette macht einen unklaren Actor nicht automatisch `belastbar`.
- IDs erklären technische Nachvollziehbarkeit, nicht menschliche Verantwortlichkeit.

## Umgang mit aktuellem Zustand

| Fundtyp | Aktueller Zustand | Policy-Bewertung | Spätere Behandlung |
| --- | --- | --- | --- |
| `EventEnvelope.event_id` | Vorhanden je Event. | Geeignet für eventgetriebene Folgen, aber keine Gesamtklammer. | Keine Änderung in AP-021. |
| Default-`correlation_id` | Wird bei fehlender Übergabe je Event erzeugt. | Einzel-Correlation, keine belastbare Use-Case-Kette. | Später Kontextquelle klären. |
| `AuditLogger.audit_id` | Vorhanden je Auditlog-Zeile. | Identität der Auditzeile, nicht bevorzugte Causation für Fachketten. | Keine Auditlog-Schemaentscheidung. |
| Documents `last_event_id` | Speichert letzten Eventverweis am Dokumentzustand. | Nützlich als Readmodel-/Zustandsreferenz, keine vollständige Nachweiskette. | Nicht als Correlation/Causation missverstehen. |
| Read-Tracking `session_id` | Fachliche Read-Session-Klammer. | Hilfreich, aber kein Actor- oder Event-/Audit-Causation-Ersatz. | Kettenstatus getrennt bewerten. |
| Signatur `SignRequest` | Signaturauftrag ohne explizite Command-ID. | Policy-nahes Command-Konzept vorhanden, aber nicht als ID umgesetzt. | Keine Implementierung in AP-021. |

## Nicht-Entscheidungen
- Keine konkrete API.
- Keine API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Migration.
- Keine Backend-Route.
- Keine Implementierung von UserContext, RequestContext, AuditActor, Eventkopplung, Command-ID, Use-Case-ID oder Audit-Export.
- Keine Entscheidung über konkrete ID-Formate, Generatoren, Persistenzorte, Transportcontainer oder Feldnamen.
- Keine Entscheidung, ob bestehende Events oder Auditlogs migriert, rekonstruiert oder umgeschrieben werden.
- Keine Änderung an EventEnvelope, AuditLogger, LogQueryService, Documents-Services, Signaturmodul, GUI, CLI, Backend oder Tests.

## Konsequenzen
- Für Services:
  - Services bleiben fachliche Grenze, an der Use-Case-Klammer, Commands, Actor, Target, Event und Auditlog später konsistent entstehen müssen.
  - Spätere Umsetzungsvorbereitung muss je Use Case festlegen, ob Use-Case-ID, Command-ID oder Event-ID die Causation trägt.
- Für Events:
  - Event-ID bleibt wichtig, aber nicht pauschal die bevorzugte Causation für alle fachlichen Folgen.
  - Event-ID eignet sich besonders für wirklich eventgetriebene Folgeprozesse.
- Für Auditlog:
  - Auditlog-ID bleibt Identität des Auditlog-Eintrags.
  - Auditlog-ID soll nicht still als fachlicher Auslöser für Workflow-, Signatur-, Release- oder Read-Ketten genutzt werden.
- Für Export/Nachweispaket:
  - Kettenstatus muss sichtbar machen, ob eine Kette über Use-Case-/Command-/Event-Bezug belastbar, eingeschränkt oder legacy ist.
  - Bestehende Log-/Eventdaten dürfen nicht rückwirkend aufgewertet werden.

## Risiken
- Technische Risiken:
  - Eine spätere konkrete ID-Strategie kann Servicegrenzen, Eventing, AuditLogger, Tests und Exporte berühren.
  - Zu frühe Festlegung auf nur Event-ID könnte Commands und Service-Nachweisentscheidungen unzureichend abbilden.
  - Zu breite Use-Case-ID könnte Auslöserrichtung verschleiern, wenn Causation fehlt.
- Fachliche Risiken:
  - Command-ID könnte mit Autorisierung oder Actor verwechselt werden.
  - Event-ID könnte als alleiniger Nachweis gelesen werden, obwohl Auditlog oder Actor-Kontext fehlt.
  - Auditlog-ID könnte fälschlich als fachlicher Auslöser verwendet werden.
- Audit-/Nachweisrisiken:
  - Legacy-Bestände ohne IDs können überinterpretiert werden.
  - Getrennte Documents-/Signatur-/Read-Teilketten können widersprüchlich wirken, wenn Parent-Kontext fehlt.
  - Kettenstatus und Actor-Status können im Export vermischt werden.

## Offene Supervisor-Entscheidungen
- Soll `causation_id` technisch bevorzugt auf Event-ID, Command-ID oder Use-Case-ID zeigen?
- Wird eine Use-Case-ID als eigene Zielreferenz eingeführt oder entspricht sie einer durchgereichten Correlation-ID?
- Wird eine Command-ID als eigenes Konzept eingeführt oder bleibt sie Policy-Begriff?
- Darf Auditlog-ID als Causation-Ziel verwendet werden, und wenn ja nur für auditlog-interne Folgefälle?
- Brauchen Documents und Signatur gemeinsame Use-Case-/Command-Ketten oder getrennte Teilketten mit Parent-Bezug?
- Brauchen technische Folgeprozesse eigene Command-IDs oder nur Causation auf fachliche Commands?
- Wie werden Legacy-Events und Legacy-Auditlogs ohne Use-Case-/Command-ID markiert?
- Welche IDs muss ein späterer RequestContext transportieren, falls ein solcher freigegeben wird?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`
  - `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`
  - `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`
  - `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`
  - `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md`
  - `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md`
  - `docs/AP-019_DOCUMENTS_SIGNATURE_CAUSATION_REFERENCE_ADR.md`
  - `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
  - `modules/documents/eventing.py`
  - `modules/documents/workflow_use_cases.py`
  - `modules/signature/signature_execute_ops.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-021_USE_CASE_COMMAND_ID_STRATEGY_ADR.md`.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Event-/Audit-/Documents-/Signatur-Hotspots.
  - `rg` in `qm_platform/events` nach EventEnvelope-, `event_id`-, Correlation-/Causation-, Command-/Use-Case- und Actor-Begriffen.
  - `rg` in `qm_platform/logging` nach Auditlog-, `audit_id`-, Correlation-/Causation-, Command-/Use-Case- und Export-Begriffen.
  - `rg` in `modules/documents` nach Event-/Audit-/Use-Case-/Command-/Session-/Artefakt-Hotspots.
  - `rg` in `modules/signature` nach SignRequest-, Signatur-Event-/Audit-, Command-/Use-Case- und Actor-Hotspots.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/Auditlog-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-021 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Keine Command-/Use-Case-ID-Implementierung durchgeführt.
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-021_USE_CASE_COMMAND_ID_STRATEGY_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein reines ADR-Paket zur RequestContext-/Kettenkontext-Transportstrategie oder ein enges Umsetzungsvorbereitungspaket für genau einen Documents-Workflow-Nachweis-Slice freigegeben wird; keine Implementierung automatisch starten.
