# AP-020 Auditlog-Kettenfeld-Strategie ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Auditlog-Schema-Änderung: nein
- Audit-Export-Implementierung: nein
- Exportformat-Entscheidung: nein
- Signatur-Implementierung: nein
- Migration: nein

## Kontext
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` trennt AuditActor, Correlation und Causation. Correlation/Causation erklären Ketten, ersetzen aber keinen Actor.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` verlangt sichtbare Actor-Qualität und empfiehlt Ketteninformationen, ohne sie mit Actor-Status gleichzusetzen.
- Bezug auf AP-013: `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` zeigt, dass `qm_platform/logging/audit_logger.py` aktuell `audit_id`, aber keine `correlation_id`, `causation_id` oder Event-Referenz schreibt.
- Bezug auf AP-014: `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md` definiert Kettenstatus als getrennt von Actor-Status und lässt offen, ob Auditlog eigene Kettenfelder erhält.
- Bezug auf AP-015: `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md` bewertet Documents-Auditlog ohne Kettenbezug als `ketten-eingeschränkt`, weil Domain-Event und Auditlog nur heuristisch verbindbar sind.
- Bezug auf AP-016: `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md` entscheidet, dass Auditlog und Domain-Events getrennte Nachweisartefakte bleiben, aber aus derselben service-seitigen Nachweisentscheidung konsistent erklärbar sein müssen.
- Bezug auf AP-017: `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md` fordert für RELEASED_PDF und technische PDF-Folgeprozesse getrennte, kausal erklärbare Nachweise.
- Bezug auf AP-018: `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md` trennt Signatur-Actor und AuditActor und markiert fehlende Causation zwischen Signatur- und Documents-Kette als Einschränkung.
- Bezug auf AP-019: `docs/AP-019_DOCUMENTS_SIGNATURE_CAUSATION_REFERENCE_ADR.md` bevorzugt Signatur-Command bzw. Use-Case-/Command-Kontext als direkten Signaturauslöser, verlangt aber fachliche Rückführbarkeit zum Documents-Workflow.
- Aktueller Hotspot:
  - `qm_platform/logging/audit_logger.py` schreibt Auditlog-Zeilen mit `audit_id`, `action`, `actor`, `target`, `result`, `reason` und `timestamp_utc`.
  - `qm_platform/events/event_envelope.py` kennt `event_id`, `correlation_id`, `causation_id` und `actor_user_id`.
  - `qm_platform/logging/log_query_service.py` liest und exportiert vorhandene Auditlog-Felder; es erzeugt keine Ketten und entscheidet keine Nachweissemantik.
  - Documents- und Signatur-Use-Cases erzeugen teils Domain-Events und Auditlog im gleichen Ablauf, aber ohne belastbare technische Kopplung.

## Begriffe
- **Auditlog-Eintrag**: Audit-Nachweisartefakt mit Handlung, Actor, Target, Ergebnis, Grund und Zeit. Er ist nicht automatisch ein Domain-Event.
- **Domain-Event**: Eventsystem-Artefakt mit `event_id`, Eventname, Modul, Payload, Actor und möglicher Correlation/Causation. Es ist nicht automatisch vollständiger Auditnachweis.
- **Auditlog-ID / `audit_id`**: eindeutige Identität einer Auditlog-Zeile. Sie ist keine Correlation, keine Causation und kein Actor.
- **Correlation-ID**: technische Klammer für zusammengehörige Commands, Domain-Events, Auditlogs, technische Logs und Folgeprozesse.
- **Causation-ID**: Verweis auf den unmittelbaren Auslöser eines Folgeeintrags oder Folgeprozesses.
- **Command-ID**: mögliche spätere Referenz auf einen fachlichen oder technischen Auftrag. Kein DTO, keine API und kein Schema in dieser ADR.
- **Use-Case-ID**: mögliche spätere Klammer für eine service-seitige Nachweisentscheidung oder einen Use-Case-Aufruf. Kein Formatentscheid in dieser ADR.
- **Event-ID**: Identität eines Domain-Events. Sie kann Kopplungsreferenz sein, ersetzt aber nicht Correlation oder Causation.
- **Kettenstatus**: Bewertung, ob ein Nachweis technisch/fachlich als Kette erklärbar ist, z. B. `kettenbelastbar`, `ketten-eingeschränkt` oder `ketten-legacy`.

## Entscheidung
Empfohlene Ziel-Policy:

Auditlog-Einträge benötigen im Zielbild eigene, auditlog-seitig verfügbare Ketteninformationen, sobald sie Teil eines belastbaren MVP-Nachweises oder einer mehrstufigen Nachweiskette sein sollen. Ein Auditlog darf für `kettenbelastbar` nicht ausschließlich exportseitig über Zeitstempel, Action, Target, Dateipfad, Actor-String oder Statusänderung mit Domain-Events verbunden werden.

Diese Ketteninformationen sollen mindestens die fachliche Zugehörigkeit zu einer Correlation und die Auslöserbeziehung einer Causation ausdrücken können. Ob diese Informationen als neue Auditlog-Felder, als unveränderlicher Begleitkontext, als Referenz auf einen späteren Use-Case-/Command-Kontext oder durch eine andere technische Form gespeichert werden, bleibt ausdrücklich offen. Diese ADR trifft keine Auditlog-Schema-Entscheidung.

Auditlog und Domain-Events bleiben getrennte Nachweisartefakte. Die führende fachliche Wahrheit ist die service-seitige Nachweisentscheidung, aus der Actor, Target, Ergebnis, Domain-Event, Auditlog und Kettenstatus konsistent erklärbar entstehen sollen. Weder Domain-Event noch Auditlog überstimmen still das jeweils andere Artefakt.

Bestehende Auditlog-Einträge ohne Kettenbezug bleiben nicht automatisch unbrauchbar, dürfen aber für mehrstufige Documents-/Signatur-/Read-/Release-Nachweise nicht als `kettenbelastbar` gelten. Sie sind grundsätzlich `ketten-eingeschränkt` oder, wenn keine belastbare Rekonstruktion möglich ist, `ketten-legacy`.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Auditlog-Schema, kein Exportformat und keine Implementierung.

## Auditlog-Kettenbedarf

| Auditlog-Fall | Eigene Ketteninformationen nötig | Policy-Bewertung |
| --- | --- | --- |
| Einzelne nicht-auditkritische technische Aktion ohne behauptete Nachweiskette | offen/nein | Kann getrennt als technischer Log-/Runtime-Kontext bleiben, sofern kein belastbarer Fachnachweis behauptet wird. |
| Interaktive auditrelevante Fachhandlung mit Domain-Event | ja | Auditlog und Domain-Event müssen aus derselben Nachweisentscheidung erklärbar sein. |
| Technischer Folgeprozess zu menschlicher Fachhandlung | ja | Causation muss den fachlichen Auslöser oder freigegebenen Command erklären; Actor bleibt getrennt. |
| Signatur-nahe Documents-Flows | ja | Signatur-Auditlog, Signatur-Event und Documents-Workflow dürfen nicht nur heuristisch verbunden werden. |
| Read-Receipt-/Read-Tracking-Ketten | ja | Receipt, Session, Event und Auditlog brauchen getrennte Actor-/Target-/Kettenbewertung. |
| Legacy-Auditlog ohne rekonstruierbare Kette | nein für Rekonstruktion, ja für Zielzustand | Nicht rückwirkend aufwerten; sichtbar als `ketten-legacy` oder eingeschränkt markieren. |

Auditlog-Kettenstatus bleibt getrennt vom Actor-Nachweisstatus. Ein Auditlog mit belastbarem Actor kann trotzdem `ketten-eingeschränkt` sein, wenn der Kettenbezug fehlt. Ein Auditlog mit sauberer Correlation macht einen freien oder falschen Actor nicht belastbar.

## Referenzstrategie

| Referenz | Rolle im Zielbild | Nicht-Zweck | Offene Entscheidung |
| --- | --- | --- | --- |
| Correlation-ID | Gemeinsame Klammer für Auditlog, Domain-Event, technische Folgeprozesse und ggf. Signatur-/Read-Teilketten. | Kein Actor, keine Action, kein Target. | Ob Auditlog sie direkt trägt oder über Use-Case-/Command-Kontext erhält. |
| Causation-ID | Unmittelbarer Auslöser eines Auditlog-Eintrags oder Folgeprozesses. | Keine Verantwortlichkeit und kein Ersatz für AuditActor. | Ob sie auf Event-ID, Command-ID, Use-Case-ID oder andere Referenz zeigt. |
| Domain-Event-ID | Identität eines Domain-Events; geeignet als Kopplungspunkt, wenn Auditlog ein konkretes Event begleitet oder ihm folgt. | Keine Klammer für ganze Use-Case-Kette. | Ob Auditlog direkt auf Event-ID verweist. |
| Command-ID | Geeignet als direkter Auslöser für Commands und technische Folgeprozesse. | Keine Domain-Event-ID und kein Auditlog-ID-Ersatz. | Ob Commands als eigene referenzierbare Nachweisobjekte eingeführt werden. |
| Use-Case-ID | Geeignet als service-seitige Klammer einer Nachweisentscheidung. | Keine Causation-Richtung allein. | Ob eine solche ID Zielarchitektur wird. |
| Auditlog-ID | Identität einer Auditlog-Zeile; geeignet für Auditlog-zu-Auditlog-Folgebezug. | Keine Correlation und nicht automatisch Causation. | Ob andere Artefakte auf Auditlog-ID verweisen dürfen. |

Keine dieser Ebenen darf still vermischt werden. Eine `event_id` kann eine Causation-Referenz sein, aber sie ist nicht automatisch die Correlation. Eine `audit_id` identifiziert eine Auditlog-Zeile, macht aber keine fachliche Kette. Eine Use-Case-ID kann gruppieren, erklärt aber ohne Causation nicht die Auslöserrichtung.

## Kopplung zu Domain-Events
- Zielregel:
  - Auditlog und Domain-Event sollen für auditrelevante Use Cases aus derselben service-seitigen Nachweisentscheidung erklärbar entstehen.
  - Die Kopplung soll nicht allein über Zeit, Zieltext, Action-Name, Dateipfad oder Actor-String geraten werden.
  - Actor-Status, Kettenstatus und Artefaktstatus bleiben getrennt.
- Zulässige Zielrichtungen ohne technische Festlegung:
  - Auditlog und Domain-Event teilen dieselbe Correlation.
  - Auditlog verweist direkt oder indirekt auf den auslösenden Domain-Event-Kontext.
  - Domain-Event und Auditlog verweisen beide auf einen gemeinsamen Command- oder Use-Case-Kontext.
  - Technische Folgeprozesse bilden eigene Teilketten, bleiben aber fachlich rückführbar.
- Ausdrücklich offen:
  - ob Auditlog direkt auf Domain-Event-ID verweist,
  - ob Domain-Events auf Auditlog-ID verweisen,
  - ob beide ausschließlich über gemeinsame Chain-Felder verbunden werden,
  - ob Command-ID oder Use-Case-ID die primäre Kopplung bildet,
  - ob jedes auditrelevante Event zwingend ein Auditlog-Paar braucht.
- Getrennte Teilketten sind zulässig, wenn:
  - sie als getrennt ausgewiesen werden,
  - keine gemeinsame `kettenbelastbare` Nachweiskette behauptet wird,
  - fachliche und technische Actors nicht vermischt werden,
  - der Export bzw. spätere Nachweisstatus die Einschränkung sichtbar macht.

## Documents-MVP-Auswirkung

| Documents-MVP-Fall | Auditlog-Kettenbedarf | Zielbewertung |
| --- | --- | --- |
| Workflow-Transitions: Rollen, Start, Editing, Abort | Auditlog braucht Correlation und ggf. Causation zum Workflow-Command oder Domain-Event, wenn der Verlauf als Nachweis dient. | Ohne Kettenbezug `ketten-eingeschränkt` oder bei Fallbacks `ketten-legacy`. |
| Review/Approval | Auditlog soll dieselbe fachliche Entscheidung wie das Review-/Approval-Event erklären. | Für belastbaren Nachweis braucht es mehr als Zeit-/Target-Heuristik. |
| Release/Freigabe | Approval-Auditlog, Release-Kontext und technische Folgen müssen getrennt, aber rückführbar bleiben. | Ohne technische Kette bleibt Freigabe-Folgenachweis eingeschränkt. |
| RELEASED_PDF / technische PDF-Folgeprozesse | Eigener Auditlog-/Nachweiskontext oder belastbare Kopplung zu Event/Command nötig, falls als Nachweisfolge ausgewiesen. | Ohne Causation nicht `kettenbelastbar`. |
| Read-Tracking / Read Receipt | Auditlog-Kettenbedarf besteht, sobald Session, Completion und Receipt gemeinsam bewertet werden. | `session_id` allein ersetzt keine Auditlog-Kette und keinen Actor. |
| Kommentar-Sync | Auditlog oder Nachweiskette muss Sync-Actor, DOCX-Autor und Kommentarstatus trennen können. | Ohne Kette eingeschränkt/legacy. |
| Signatur-nahe Documents-Flows | Signatur-Auditlog, Signatur-Event und Documents-Workflow brauchen gemeinsame oder rückführbare Ketteninformation. | Ohne Kettenbezug nicht gemeinsam `kettenbelastbar`. |

## Nachweisstatus
- `kettenbelastbar` für Auditlog-Einträge ist erst möglich, wenn:
  - der Auditlog-Eintrag einer Correlation oder gleichwertigen Use-Case-Klammer zugeordnet ist,
  - Causation oder eine gleichwertige Auslöserreferenz relevante Folgeprozesse erklärt,
  - die Verbindung zu Domain-Events, Commands oder technischen Folgeprozessen nicht nur heuristisch ist,
  - Actor-Status und Kettenstatus getrennt bewertet werden.
- `ketten-eingeschränkt` gilt, wenn:
  - Auditlog ohne eigene Ketteninformation nur über Zeit, Action, Target oder Actor mit Events verbunden wird,
  - Domain-Events Default-Correlation haben, Auditlog aber keinen belastbaren Bezug dazu trägt,
  - technische Folgeprozesse oder Signatur-/Read-Teilketten keinen klaren Auditlog-Auslöserbezug haben,
  - ein Eintrag zwar fachlich plausibel, aber technisch nicht eindeutig gekoppelt ist.
- `ketten-legacy` gilt, wenn:
  - bestehende Auditlogs ohne Kettenfelder nicht rekonstruierbar sind,
  - freie Actor-Strings, Owner-/`system`-Fallbacks oder alte Exporte keine zuverlässige Kette ermöglichen,
  - Altdaten nur als Bestands- oder Importkontext ausgewiesen werden können.

Actor-Status und Kettenstatus bleiben getrennt:
- `belastbar/eingeschränkt/legacy` bewertet Actor-Quelle und Actor-Qualität.
- `kettenbelastbar/ketten-eingeschränkt/ketten-legacy` bewertet die technische und fachliche Verkettung.
- Ein guter Actor heilt keine fehlende Causation.
- Eine gute Correlation heilt keinen falschen oder unklaren Actor.

## Umgang mit aktuellem Zustand

| Fundtyp | Aktueller Zustand | Policy-Bewertung | Spätere Behandlung |
| --- | --- | --- | --- |
| `AuditLogger.emit` | Schreibt `audit_id`, Action, Actor, Target, Result, Reason und Zeit, aber keine Ketteninformation. | Für mehrstufige Nachweise `ketten-eingeschränkt`. | Keine Änderung in AP-020; spätere Strategie/Umsetzungsvorbereitung nötig. |
| `EventEnvelope.create` | Unterstützt `event_id`, `correlation_id`, `causation_id`; Default-Correlation bei fehlender Übergabe. | Event-Fähigkeit vorhanden, aber nicht automatisch Auditlog-Kette. | Keine Event-Schema-Entscheidung in AP-020. |
| `LogQueryService` | Exportiert vorhandene Auditfelder und entscheidet keine Semantik. | Bestehende Log-Exporte sind keine belastbaren Documents-MVP-Nachweispakete. | Keine Exportformatentscheidung in AP-020. |
| Documents-Workflow-Audit | Auditlog wird neben Events geschrieben, aber ohne Event-/Kettenreferenz. | Meist nur heuristisch verbindbar. | Ziel: aus derselben Nachweisentscheidung mit Kettenkontext erklärbar. |
| Signatur-Auditlog | Signatur-Audit nutzt `signer_user or "system"` ohne Kettenfelder. | Signatur- und Documents-Nachweis nur eingeschränkt verbindbar. | AP-018/AP-019 beachten; keine Reparatur. |
| Log-Backup-Audit | Plattformnaher Auditlog mit `actor="system"`-Default. | Kein Documents-Workflow, aber System-Actor-/Kettenstatus-relevant. | Separat als Plattform-/Runtime-Kontext klassifizieren. |

## Nicht-Entscheidungen
- Keine konkrete API.
- Keine API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Migration.
- Keine Backend-Route.
- Keine Auditlog-, Event-, UserContext-, RequestContext-, AuditActor-, Signatur- oder Audit-Export-Implementierung.
- Keine Entscheidung, ob `correlation_id`/`causation_id` als konkrete Auditlog-Felder, Begleitkontext oder anders gespeichert werden.
- Keine Entscheidung, ob Auditlog auf Domain-Event-ID, Command-ID, Use-Case-ID oder Auditlog-ID verweist.
- Keine Entscheidung, ob bestehende Auditlog-Zeilen migriert, rekonstruiert oder exporttechnisch umgeschrieben werden.
- Keine Änderung an `AuditLogger`, `EventEnvelope`, `LogQueryService`, Documents-Services, Signaturmodul, GUI, CLI, Backend oder Tests.

## Konsequenzen
- Für Services:
  - Services bleiben die fachliche Grenze für Nachweisentscheidung, Actor, Target, Ergebnis und Kettenkontext.
  - Spätere Pakete müssen je Use Case bestimmen, welche Nachweisartefakte entstehen und wie sie ohne Heuristik gekoppelt werden.
- Für Auditlog:
  - Auditlog bleibt eigenes Nachweisartefakt und braucht Zielbild-Ketteninformationen für belastbare mehrstufige Nachweise.
  - Bestehende Auditlog-Zeilen ohne Kettenbezug bleiben eingeschränkt oder legacy.
- Für Domain-Events:
  - Domain-Events bleiben Integration-/Zustandsartefakte und werden nicht automatisch Auditlog.
  - Eine Event-ID kann hilfreich sein, ist aber nicht allein die gesamte Auditlog-Kopplungsstrategie.
- Für Export/Nachweispaket:
  - Nachweispakete müssen Actor-Status, Kettenstatus, Event-/Auditlog-Kopplung und technische Folgeprozesse getrennt bewerten.
  - Ein Export darf bestehende Log-Zeilen ohne Kettenbezug nicht als vollständig belastbare Nachweiskette behaupten.
- Für Legacy:
  - Rückwirkende Rekonstruktion bestehender Auditlog-Ketten wird nicht angenommen.
  - Legacy-Auditlogs ohne Kettenfelder müssen später sichtbar eingeordnet werden.

## Risiken
- Technische Risiken:
  - Eine spätere konkrete Feld-/Schemaentscheidung kann `AuditLogger`, `LogQueryService`, Services, Tests und Exporte berühren.
  - Zu frühe Festlegung auf Event-ID, Command-ID oder Use-Case-ID kann die Servicegrenzen verengen.
  - Ohne gemeinsame Kontextquelle bleiben Auditlog und Domain-Events parallel, aber nicht belastbar gekoppelt.
- Fachliche Risiken:
  - Auditlog könnte als alleinige Wahrheit gelesen werden, obwohl Domain-Events oder technische Folgeprozesse fehlen.
  - Domain-Event könnte als vollständiger Auditnachweis gelesen werden, obwohl Actor-/Target-/Reason-Kontext fehlt.
  - Causation könnte als Verantwortung missverstanden werden.
  - System-/Service-Actor könnten menschliche Verantwortung verdecken.
- Audit-/Nachweisrisiken:
  - Bestehende Log-Exports können belastbarer wirken, als sie sind.
  - Documents-, Signatur- und technische Auditlogs können widersprüchliche Ketten darstellen, wenn keine gemeinsame Strategie folgt.
  - Legacy-Auditlogs ohne Kettenfelder können überinterpretiert werden.

## Offene Supervisor-Entscheidungen
- Braucht Auditlog direkt eigene `correlation_id`/`causation_id`-Felder oder einen anderen auditlog-seitig verfügbaren Kettenkontext?
- Soll Auditlog auf Domain-Event-ID verweisen?
- Sollen Domain-Events auf Auditlog-ID verweisen?
- Soll Command-ID oder Use-Case-ID die primäre Kopplung zwischen Auditlog und Domain-Events bilden?
- Müssen Auditlog und Domain-Event für alle auditrelevanten Use Cases paarweise entstehen, oder sind getrennte Teilketten zulässig?
- Wie werden bestehende Auditlog-Zeilen ohne Kettenfelder markiert: `ketten-eingeschränkt`, `ketten-legacy` oder anderes Vokabular?
- Brauchen technische Folgeprozesse eigene Auditlog-Ketten oder nur Domain-Event-/Artefaktketten?
- Wie werden Signatur-Auditlog und Documents-Auditlog voneinander abgegrenzt und ggf. verknüpft?
- Ob und wann bestehende Auditlogs migriert, markiert oder bewusst legacy belassen werden, bleibt offen.

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
  - `qm_platform/logging/audit_logger.py`
  - `qm_platform/logging/log_query_service.py`
  - `qm_platform/logging/log_backup_service.py`
  - `qm_platform/events/event_envelope.py`
  - `modules/documents/eventing.py`
  - `modules/documents/workflow_use_cases.py`
  - `modules/signature/signature_execute_ops.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md`.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Auditlog-/Event-/Documents-/Signatur-Hotspots.
  - `rg` in `qm_platform/logging` nach AuditLogger-, `audit_id`-, Export-, Correlation-/Causation- und Actor-Begriffen.
  - `rg` in `qm_platform/events` nach EventEnvelope-, `event_id`-, Correlation-/Causation- und Actor-Begriffen.
  - `rg` in `modules/documents` nach Audit-, Domain-Event-, Correlation-/Causation-, RELEASED_PDF-, Read-, Kommentar- und Signatur-Hotspots.
  - `rg` in `modules/signature` nach Signatur-Audit-, Signatur-Event-, SignRequest-, Actor- und Correlation-/Causation-Hotspots.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/Auditlog-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-020 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Keine Signatur-Implementierung durchgeführt.
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein reines ADR-Paket zur Use-Case-/Command-ID-Strategie oder ein enges Umsetzungsvorbereitungspaket für genau einen Documents-Workflow-Nachweis-Slice freigegeben wird; keine Implementierung automatisch starten.
