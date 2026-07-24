# AP-023 Documents-MVP-Nachweisslice-Priorisierung

## Status
- Arbeitspaket: AP-023
- Typ: Analyse / Priorisierung
- Codeänderungen: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Auditlog-Schema-Änderung: nein
- Audit-Export-Implementierung: nein
- Exportformat-Entscheidung: nein
- RequestContext-/CommandContext-/ExecutionContext-Implementierung: nein
- Command-/Use-Case-ID-Implementierung: nein
- Migration: nein

## Ziel
Diese Analyse vergleicht mögliche erste Documents-MVP-Nachweisslices und empfiehlt genau einen kleinsten fachlich sinnvollen Kandidaten für ein späteres Umsetzungsvorbereitungspaket.

Diese Datei ist keine Implementierungsspezifikation. Sie entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Auditlog-Schema, kein Exportformat, keine Migration und keine konkrete RequestContext-/Command-/Use-Case-ID-Implementierung.

## Bewertungsmaßstab
- **Actor-Readiness**
  - `belastbar`: Actor ist service-nah explizit und fachlich geprüft; Quelle muss später noch UserContext-/RequestContext-fähig gemacht werden können.
  - `eingeschränkt`: Actor existiert, aber Quelle, Adapterherkunft, Fallback oder technische Rolle sind nicht belastbar genug.
  - `legacy`: Actor fehlt, stammt aus Fallback/Owner/`system`/`unknown` oder wäre nur aus Alt-/Hilfsdaten rekonstruierbar.
  - `unklar / Supervisor nötig`: fachliche Actor-Semantik ist noch nicht entschieden.
- **Ketten-Readiness**
  - `kettenbelastbar`: Use-Case-/Command-/Correlation-/Causation-Bezug ist belastbar vorhanden.
  - `ketten-eingeschränkt`: Event-ID, Default-Correlation, Auditlog oder Hilfsreferenzen existieren, aber keine durchgehende Kette.
  - `ketten-legacy`: keine rekonstruierbare Kette ohne nachträgliches Raten.
  - `unklar / Supervisor nötig`: Zielreferenz oder Pflichtgrad ist noch offen.
- **Event-/Auditlog-Readiness**
  - bewertet, ob Domain-Event, Auditlog oder beide vorhanden sind und ob ihre Verbindung fachlich konsistent oder nur heuristisch ist.
- **Umsetzungsrisiko für später**
  - bewertet ein späteres enges Umsetzungsvorbereitungspaket, nicht die Implementierung selbst.
- **Slice-Eignung**
  - bevorzugt klein, isoliert testbar, service-grenzennah, ohne technische Folgeprozesse und ohne offene Grundsatzentscheidung als Blocker.

## Zusammenfassung
- Kein Kandidat ist heute vollständig `kettenbelastbar`.
- Die aussichtsreichsten fachlichen Einstiegspunkte sind Review/Approval/Gültigkeitsverlängerung, weil sie explizite Service-Actor-Parameter und Domain-Event plus Auditlog besitzen.
- Approval und Gültigkeitsverlängerung tragen mehr Abhängigkeiten durch Freigabe-, RELEASED_PDF-, Signatur- oder approved-state-Kontext.
- Read Receipt, RELEASED_PDF, DOCX->PDF, Kommentar-Sync und Signatur-nahe Flows sind MVP-relevant, aber als erster Slice zu stark von offenen Grundsatzentscheidungen abhängig.
- Workflow-Start/Rollenvergabe/Editing-Abschluss ist fachlich wichtig, aber wegen optionaler Actor und Owner-/`system`-Fallbacks kein guter erster Nachweisslice.

Empfohlener erster Kandidat: **Review ablehnen** als engster Slice innerhalb des Kandidaten `Review akzeptieren / ablehnen`.

## Bewertungsmatrix

| Kandidat | Actor-Readiness | Ketten-Readiness | Event-/Auditlog-Readiness | späteres Risiko | Architekturabhängigkeiten | Slice-Eignung | Bewertung |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Review akzeptieren / ablehnen | `belastbar nach Quellklassifikation` für Reviewer-Parameter; Adapterquelle heute eingeschränkt | `ketten-eingeschränkt` | Domain-Events und Auditlogs vorhanden; fachlich plausibel, aber nur heuristisch verbindbar | niedrig bis mittel | UserContext, RequestContext/Kettenkontext, Command-/Use-Case-ID, Event-/Auditlog-Kopplung, ggf. Auditlog-Kettenfelder | gut; besonders `Review ablehnen` ist klein, service-nah, ohne Release-PDF und ohne Signaturpflicht im gelesenen Servicepfad | **empfohlen: Review ablehnen** |
| Approval akzeptieren / ablehnen | `belastbar nach Quellklassifikation` für Approver-Parameter; Four-Eyes-Prüfung bei Annahme | `ketten-eingeschränkt` | Domain-Events und Auditlogs vorhanden; nur heuristisch verbindbar | mittel bis hoch | UserContext, RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, RELEASED_PDF-Entscheidung, Signaturentscheidung | fachlich wichtig, aber Annahme löst Freigabe-/Release-/RELEASED_PDF-Kontext aus | zurückstellen |
| Gültigkeitsverlängerung / Jahresreview | `belastbar nach Quellklassifikation`; nicht-leerer Actor wird validiert | `ketten-eingeschränkt` | Domain-Event und Auditlog vorhanden; nur heuristisch verbindbar | mittel | UserContext, RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, Signaturentscheidung | klein und gut testbar, aber hängt an approved-state, Signaturpflicht und Jahresreview-Fachkontext | zurückstellen |
| Read Receipt / Kenntnisnahme | unklar/eingeschränkt; Direct Confirm setzt `user_id` als Actor, Tracked Read hat Events ohne Actor | `ketten-eingeschränkt` | Direct Confirm hat Domain-Event; Tracked Read hat Events ohne Actor; Auditlog unklar/fehlend | hoch bis blockierend | UserContext, RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, Migration/Legacy-Strategie | MVP-relevant, aber Actor-/Session-/Target-Fragen sind Grundsatzblocker | zurückstellen |
| RELEASED_PDF / technischer PDF-Folgeprozess | unklar; technischer Actor/System-/Service-Actor noch offen | `ketten-eingeschränkt` bis `ketten-legacy` | im gelesenen Code kein eigenes RELEASED_PDF-Event/Audit; Approval-Event nur indirekter Kontext | blockierend | RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, RELEASED_PDF-Entscheidung, System-/Service-Actor-Entscheidung | nicht als erster Slice geeignet, weil Nachweisform selbst offen ist | zurückstellen |
| DOCX->PDF-Sync / SOURCE_PDF | eingeschränkt/legacy; Actor-/Owner-/`system`-Fallback | `ketten-eingeschränkt` | Domain-Event und Auditlog vorhanden, aber ohne Causation und mit Fallback-Risiko | hoch | RequestContext/Kettenkontext, Command-/Use-Case-ID, Event-/Auditlog-Kopplung, System-/Service-Actor-Entscheidung, Migration/Legacy-Strategie | technischer Folgeprozess; zu viele offene Actor-/Causation-Fragen | zurückstellen |
| Kommentar-Erstellung / Kommentar-Status / Kommentar-Sync | eingeschränkt; Actor teils Record/Payload, nicht Envelope; DOCX-Autor ist Fremdmetadatum | `ketten-eingeschränkt` | Domain-Events vorhanden, aber Event-Actor/Auditlog-Kopplung unzureichend | hoch | UserContext, RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, Migration/Legacy-Strategie | fachlich relevant, aber Kommentarrecord/Event/Audit und Importautor-Semantik sind offen | zurückstellen |
| Signatur-naher Documents-Flow | eingeschränkt; Signatur-Actor ist nicht automatisch AuditActor | `ketten-eingeschränkt` | Signatur-Domain-Events und Signatur-Audit vorhanden; nicht kausal mit Documents-Workflow verbunden | hoch | RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, Signaturentscheidung | zu viele offene Signatur-/Causation-/Exportgrenzen für den ersten Slice | zurückstellen |
| Workflow-Start / Rollenvergabe / Editing-Abschluss | eingeschränkt/legacy; optionale Actor, Owner-/`system`-Fallbacks, Editing signaturnah | `ketten-eingeschränkt` | Domain-Events und Auditlogs vorhanden; nur heuristisch verbindbar | hoch | UserContext, RequestContext/Kettenkontext, Command-/Use-Case-ID, Auditlog-Kettenfelder, Event-/Auditlog-Kopplung, Signaturentscheidung, Migration/Legacy-Strategie | kein guter erster Slice, weil Fallback-Policy sofort berührt wird | zurückstellen |

## Empfohlener erster Nachweisslice
Empfohlen wird **Review ablehnen** als kleinster späterer Umsetzungsvorbereitungs-Slice.

Begründung:
- `Review ablehnen` hat einen verpflichtenden `actor_user_id` als Reviewer-Parameter.
- Der Service prüft, dass der Actor in der Reviewer-Zuordnung enthalten ist.
- Der Flow erzeugt ein Documents-Domain-Event und einen Documents-Auditlog-Eintrag.
- Der Ablehnungsgrund ist fachlich vorhanden und für einen Nachweis relevant.
- Der Flow führt zurück nach `IN_PROGRESS` und löst im gelesenen Servicepfad keine RELEASED_PDF-Erzeugung aus.
- Der Flow ist nicht direkt signaturpflichtig im gelesenen Servicepfad und vermeidet daher Signatur-Actor-/Signatur-Causation-Blocker.
- Der Slice ist service-grenzennah und isoliert testbar, ohne einen Use Case halb lokal und halb backendseitig zu betreiben.
- Bestehende App-Funktion wird durch ein reines späteres Umsetzungsvorbereitungspaket nicht gefährdet.

Bewertung des empfohlenen Slice:

| Kriterium | Bewertung |
| --- | --- |
| Actor-Readiness | `belastbar nach Quellklassifikation`; aktuell noch eingeschränkt durch CLI-/PyQt-Current-User-Herkunft |
| Ketten-Readiness | `ketten-eingeschränkt`; keine durchgereichte Use-Case-/Command-/Correlation-/Causation-Kette |
| Event-/Auditlog-Readiness | Domain-Event und Auditlog vorhanden; fachlich konsistent, aber nur heuristisch gekoppelt |
| späteres Umsetzungsrisiko | niedrig bis mittel für Vorbereitung; Implementierung selbst braucht separate Freigabe |
| Architekturabhängigkeiten | UserContext/RequestContext/Kettenkontext, Command-/Use-Case-ID, Event-/Auditlog-Kopplung, ggf. Auditlog-Kettenfelder |
| Slice-Eignung | kleinster fachlich sinnvoller Use Case; isoliert testbar; keine offene RELEASED_PDF-/Signatur-Grundsatzentscheidung als direkter Blocker |

## Warum nicht Review akzeptieren?
`Review akzeptieren` gehört zur gleichen Kandidatenfamilie und ist ebenfalls service-nah. Als erster enger Slice ist `Review ablehnen` trotzdem besser, weil `Review akzeptieren` in Richtung Approval fortschreitet und bei signaturpflichtigen Profilen Signaturkontext berühren kann. `Review ablehnen` bleibt fachlich auditrelevant, aber kleiner und vermeidet Signatur- und Release-Folgeabhängigkeiten.

## Zurückgestellte Kandidaten

| Zurückgestellt | Kurzgrund |
| --- | --- |
| Approval akzeptieren / ablehnen | Approval-Annahme berührt Freigabe, RELEASED_PDF und ggf. Signatur-/Release-Folgeprozesse; Ablehnung ist kleiner, aber nach Review-Ablehnung kein erster Mehrwert. |
| Gültigkeitsverlängerung / Jahresreview | Service-seitig sauberer Actor, aber approved-state, Signaturpflicht, Jahresreview-Fachsemantik und Verlängerungslimits erhöhen den Scope. |
| Read Receipt / Kenntnisnahme | MVP-kritisch, aber Direct Confirm vs. Tracked Read, Actor-vs-Target, `session_id` und fehlende Event-Actor/Auditlog-Spur sind Grundsatzblocker. |
| RELEASED_PDF / technischer PDF-Folgeprozess | Nachweisform selbst ist offen: eigenes Event, Auditlog, beides oder Artefaktmetadatum; deshalb nicht umsetzungsnah genug. |
| DOCX->PDF-Sync | Technischer Folgeprozess mit Owner-/`system`-Fallback und fehlender Causation; hohe Gefahr, Actor und technische Folge zu vermischen. |
| Kommentar-Erstellung / Kommentar-Status / Kommentar-Sync | Actor sitzt teils im Record/Payload statt im Envelope; Kommentarautor, Statusbearbeiter, Sync-Actor und DOCX-Autor sind noch nicht sauber gekoppelt. |
| Signatur-naher Documents-Flow | Signatur-Actor, Workflow-Actor, AuditActor, Signatur-Command und Causation sind bewusst getrennt und noch nicht technisch priorisiert. |
| Workflow-Start / Rollenvergabe / Editing-Abschluss | Optionaler Actor, Owner-/`system`-Fallbacks und signaturnaher Editing-Abschluss machen diesen Block zu breit für den ersten Slice. |

## Blockierende Entscheidungen
Für **keinen** Kandidaten ist eine sofortige Implementierung freigegeben oder ausreichend vorbereitet. Für ein späteres Umsetzungsvorbereitungspaket zu `Review ablehnen` sind jedoch keine offenen Grundsatzentscheidungen als harter Blocker erkennbar, solange das Paket ausdrücklich vorbereitend bleibt und keine Code-/API-/Schemaänderung vornimmt.

Blocker vor einer späteren Implementierung:
- Wie UserContext und Request-/Kettenkontext an der Service-Grenze konkret verfügbar werden.
- Ob Use-Case-ID als eigener Wert eingeführt wird oder Correlation-Basis bleibt.
- Ob Command-ID für Review-Ablehnung als eigener Auftrag eingeführt wird.
- Wie Auditlog künftig auditlog-seitig verfügbare Ketteninformationen erhält oder belastbar gekoppelt wird.
- Ob Event/Auditlog über Command-ID, Use-Case-ID, Event-ID oder andere Kettenreferenz gekoppelt werden.
- Welche bestehenden Tests Legacy-Verhalten sichern und welche Zielsemantik prüfen sollen.

## Supervisor-Entscheidung nötig
- Darf ein späteres Umsetzungsvorbereitungspaket für `Review ablehnen` die fehlende RequestContext-/Kettenkontext-Implementierung nur als Zielkontext beschreiben, ohne sie umzusetzen?
- Soll `Review ablehnen` als isolierter Slice gegenüber `Review akzeptieren` priorisiert werden, obwohl die Roadmap-Kandidatenfamilie beide Review-Richtungen nennt?
- Wird für den ersten Slice ein Auditlog-Kettenfeldmodell vorausgesetzt, oder genügt vorbereitend eine service-seitige Nachweisentscheidung mit geplanter späterer Kettenkopplung?
- Soll der spätere Slice Tests nur inventarisieren/planen oder bereits Zieltests als spätere Aufgabe spezifizieren?
- Welches Vokabular soll für eingeschränkte Bestandsketten verbindlich genutzt werden: `ketten-eingeschränkt`, `ketten-legacy` oder ein späteres Exportvokabular?

## Test-/Legacy-Einordnung
- Bestehende Documents-Tests sichern Workflow-Transitions, Event-Grundformen, Autorisierungsmatrizen, Varianten, Signaturketten, RELEASED_PDF-Artefakte und Read-Tracking-Basisverhalten.
- Tests prüfen teilweise `actor_user_id`, `event_id` und Payload-Felder, aber nicht durchgehend Correlation/Causation, auditlog-seitige Kettenfelder oder belastbare Event-/Auditlog-Kopplung.
- Tests mit Fake-Actors wie `owner-1`, `reviewer-1`, `approver-1`, `qmb-1`, `admin` oder actor-freien Aufrufen sind nicht automatisch Produktiv-Actorquellen.
- Für den empfohlenen Slice kann ein späteres Vorbereitungspaket die vorhandenen Review-Reject-Tests als Ausgangspunkt einordnen, ohne Tests zu ändern.

## Nicht-Ziele
- Keine Implementierung.
- Keine Codeänderung.
- Keine Refactorings.
- Keine API-Änderung.
- Keine API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Audit-Export-Implementierung.
- Keine Migration.
- Keine Backend-Route.
- Keine Auth-/UserContext-/AuditActor-Implementierung.
- Keine RequestContext-/CommandContext-/ExecutionContext-Implementierung.
- Keine Command-/Use-Case-ID-Implementierung.
- Keine neuen Exporte, Re-Exports oder Wrapper-APIs.
- Keine Reparatur bestehender Findings.
- Keine Änderung an Code, Tests, Projektkonfiguration oder bestehenden ADR-/Inventar-Dateien.

## Maximal ein sinnvoller nächster Schritt
Ein späteres reines Umsetzungsvorbereitungspaket für **Documents Review ablehnen Nachweisslice** freigeben oder zurückstellen. Dieses Folgepaket soll weiterhin keine Implementierung enthalten, sondern nur Zielkontext, betroffene Service-Grenze, Nachweisentscheidung, Kettenbedarf und spätere Test-/Gate-Planung für genau diesen Slice beschreiben.

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`
  - `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md`
  - `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`
  - `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`
  - `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md`
  - `docs/AP-012_DOCUMENTS_WORKFLOW_FALLBACK_POLICY_ADR.md`
  - `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`
  - `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`
  - `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`
  - `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`
  - `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md`
  - `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md`
  - `docs/AP-019_DOCUMENTS_SIGNATURE_CAUSATION_REFERENCE_ADR.md`
  - `docs/AP-020_AUDITLOG_CHAIN_FIELDS_STRATEGY_ADR.md`
  - `docs/AP-021_USE_CASE_COMMAND_ID_STRATEGY_ADR.md`
  - `docs/AP-022_REQUEST_CONTEXT_CHAIN_CONTEXT_TRANSPORT_STRATEGY_ADR.md`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/service.py`
  - `modules/documents/pdf_read_tracking_service.py`
  - `modules/documents/comment_service.py`
  - `modules/documents/comment_sync_service.py`
  - `modules/documents/signature_guard.py`
  - `modules/signature/signature_execute_ops.py`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
  - `interfaces/cli/commands/documents_commands.py`
  - relevante PyQt-Treffer über `rg`
  - `tests/modules/test_documents_event_contracts.py`
  - `tests/modules/test_documents_variants_matrix.py`
  - `tests/modules/test_documents_authorization_matrix.py`
  - `tests/modules/test_documents_pdf_read_tracking.py`
  - `tests/modules/test_documents_infrastructure.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-023_DOCUMENTS_MVP_EVIDENCE_SLICE_PRIORITIZATION.md`.
  - `Glob` zur Einordnung vorhandener Documents-Testdateien.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und gezielter Documents-/Signatur-/Event-/Audit-/Test-Hotspots.
  - `rg` in `modules/documents`, `modules/signature`, `tests`, `interfaces/cli/commands/documents_commands.py` und `interfaces/pyqt` nach Review, Approval, Gültigkeitsverlängerung, Read-Tracking, RELEASED_PDF, DOCX->PDF, Kommentaren, Signatur, Actor, Correlation und Causation.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/Auditlog-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-023 ein Analyse-/Priorisierungspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Nur `docs/AP-023_DOCUMENTS_MVP_EVIDENCE_SLICE_PRIORITIZATION.md` wurde neu angelegt oder geändert.
