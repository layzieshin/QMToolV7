# AP-019 Documents-Signature-Causation-Reference ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Audit-Export-Implementierung: nein
- Exportformat-Entscheidung: nein
- Signatur-Implementierung: nein
- Migration: nein

## Kontext
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert `causation_id` als Verweis auf den auslösenden Vorgang, Command oder Event. Causation erklärt Ketten, ersetzt aber keinen Actor.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` trennt Actor-Nachweisstatus von technischen Kettenfeldern.
- Bezug auf AP-011: `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md` identifiziert Signaturereignisse mit `signer_user` als Documents-nah, aber nicht automatisch als Documents-AuditActor.
- Bezug auf AP-013: `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md` findet keine Documents-nahe explizite Causation; Signaturereignisse sind nicht kausal mit Documents-Workflow-Events verbunden.
- Bezug auf AP-014: `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md` fordert Causation für Signatur-nahe Documents-Flows, lässt aber die konkrete Zielreferenz offen.
- Bezug auf AP-015: `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md` bewertet Documents-nahe Signaturereignisse als `ketten-eingeschränkt`, solange sie nicht kausal mit Documents-Transitions verbunden sind.
- Bezug auf AP-016: `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md` verlangt konsistente Kopplung von Domain-Events und Auditlog ohne widersprüchliche Actor-Wahrheiten.
- Bezug auf AP-017: `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md` trennt fachliche Freigabe, RELEASED_PDF und technische Folgeprozesse.
- Bezug auf AP-018: `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md` trennt Signatur-Actor, Workflow-Actor, AuditActor, sichtbaren Unterzeichner, Zertifikatsinhaber und technischen Service Actor.
- Aktueller Hotspot:
  - `modules/documents/workflow_use_cases.py` erzwingt signaturpflichtige Workflow-Transitions über `sign_request`, publiziert danach eigene Documents-Events und schreibt Auditlog.
  - `modules/documents/signature_guard.py` ruft `signature_api.sign_with_fixed_position(sign_request)` auf und persistiert `SIGNED_PDF`, entscheidet aber keine Causation-Semantik.
  - `modules/signature/signature_execute_ops.py` publiziert `domain.signature.sign.requested.v1`, `domain.signature.sign.succeeded.v1`, `domain.signature.sign.failed.v1` und ggf. `domain.signature.sign.dry_run.v1` ohne explizite Causation.
  - `qm_platform/events/event_envelope.py` unterstützt `causation_id`, die geprüften Documents-/Signatur-Aufrufer setzen sie aber nicht explizit.
  - `qm_platform/logging/audit_logger.py` schreibt Auditlog ohne Correlation/Causation.

## Begriffe
- **Documents-Workflow-Transition**: Fachlicher Documents-Schritt wie Editing-Abschluss, Review-Annahme, Approval/Freigabe, Gültigkeitsverlängerung oder Release-Folge.
- **Signatur-Command**: Policy-Begriff für den fachlichen/technischen Auftrag, eine Signatur im Kontext eines Documents-Use-Cases auszuführen. Kein DTO, keine API-Signatur und kein Event-Schema.
- **Signatur-Service-Operation**: Technische Ausführung im Signaturmodul, z. B. visuelle Signatur, kryptografische Signatur, Dry-Run, PDF-Validierung, Label-Aufbringung oder Dateiausgabe.
- **Fachliche Causation**: Rückführbarkeit einer Signaturkette auf die auslösende Documents-Workflow-Transition oder einen freigegebenen Use-Case-Kontext.
- **Technische Causation**: Rückführbarkeit einzelner Signatur-Service-Operationen auf den unmittelbaren technischen Auftrag oder vorherigen technischen Schritt.
- **Use-Case-ID**: Mögliche spätere technische Klammer für einen service-seitigen Use-Case-Aufruf. Diese ADR entscheidet kein ID-Format.
- **Kettenbelastbarkeit**: Bewertung, ob Causation/Correlation einen Nachweis ohne reine Heuristik erklären können.

## Entscheidung
Empfohlene Ziel-Policy:

Für Documents-nahe Signaturketten soll `causation_id` den unmittelbaren Auslöser des jeweiligen Signatur- oder Signaturfolgeereignisses erklären. Auf der Signatur-Event-Ebene ist der bevorzugte direkte Auslöser ein Signatur-Command oder ein gleichwertiger service-seitig bestimmter Use-Case-/Command-Kontext, nicht still das menschliche Approval-, Review- oder Release-Event selbst.

Für den Documents-MVP genügt ein Signatur-Command als direkter Auslöser nur dann, wenn dieser Command seinerseits fachlich auf die auslösende Documents-Workflow-Transition zurückführbar ist. Die Nachweiskette muss also zwei Ebenen erklären können: den direkten Signaturauslöser und den fachlichen Documents-Kontext. Ohne diese fachliche Rückführbarkeit bleibt die Signaturkette `ketten-eingeschränkt`.

Approval-Event, Review-Event, Release-Event, Signatur-Command, Use-Case-ID und technische Signatur-Service-Operation sind unterschiedliche Ebenen. Sie dürfen nicht still vermischt werden. Ein Signaturereignis darf nicht dadurch `kettenbelastbar` wirken, dass irgendeine fachlich plausible Transition zeitlich in der Nähe liegt.

Causation ersetzt weder Signatur-Actor noch Workflow-Actor noch AuditActor. Auch eine korrekte Causation macht `signer_user`, sichtbaren Unterzeichner, Zertifikatsinhaber, `system` oder Service Actor nicht automatisch zum Documents-AuditActor.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Auditlog-Schema, kein Exportformat und keine Implementierung.

## Causation-Ziel für Signaturketten

| Mögliches Causation-Ziel | Policy-Bewertung | Geeigneter Einsatz | Risiko |
| --- | --- | --- | --- |
| Approval-Event | fachlich relevant, aber nicht pauschal direkter technischer Auslöser | Freigabe-/Signaturkette, wenn Signatur als direkte Folge der Approval-Transition verstanden wird. | Vermischt fachliche Entscheidung mit technischer Signaturausführung. |
| Review-Event | fachlich relevant für Review-Signatur | Review-Annahme mit signaturpflichtiger Transition in Richtung Approval. | Signatur könnte als Review-Actor-Ersatz gelesen werden. |
| Release-Event | offen | Falls später ein eigenes Release- oder RELEASED_PDF-Nachweisereignis eingeführt wird. | Release ist nicht automatisch Signatur; AP-017 beachten. |
| Signatur-Command | bevorzugter direkter Auslöser für Signaturereignisse | `domain.signature.sign.*` und technische Signaturfolgeereignisse. | Nur ausreichend, wenn der Command fachlich auf Documents-Workflow zurückführbar ist. |
| Use-Case-ID | offen/geeignet als Klammer | Mehrere Events, Auditlogs und Folgeprozesse in einem service-seitigen Use Case. | Darf nicht Actor oder fachliche Transition ersetzen. |
| Technische Signatur-Service-Operation | geeignet für Teilketten | Subschritte wie PDF-Prüfung, Label-Aufbringung, Crypto-Sign, Artefaktaktualisierung. | Ohne fachlichen Parent nur technische, nicht fachliche Nachweiskette. |
| Kein explizites Ziel / nur Zeit-Datei-Heuristik | nein für belastbare Nachweiskette | Höchstens Legacy-/Bestandseinordnung. | Nicht `kettenbelastbar`. |

## Zielpolicy für Documents-MVP
- Signaturereignisse müssen kausal an Workflow-Transitions gebunden sein, wenn:
  - die Signatur Voraussetzung oder Bestandteil von Editing-Abschluss, Review-Annahme, Approval/Freigabe oder Gültigkeitsverlängerung ist,
  - ein `SIGNED_PDF`, RELEASED_PDF oder ein anderer Nachweis aus der Signaturfolge im Documents-Nachweis erscheinen soll,
  - Domain-Event, Signatur-Event und Auditlog gemeinsam als Nachweiskette dargestellt werden sollen,
  - ein technischer `system`-/Service-Actor an der Signaturfolge beteiligt ist.
- Ein Signatur-Command genügt als direkter Auslöser, wenn:
  - der Command als Signaturauftrag erkennbar ist,
  - der Command selbst auf die fachliche Documents-Transition oder einen freigegebenen Use-Case-Kontext zurückführbar ist,
  - Actor-Semantik getrennt bleibt,
  - der Export nicht behauptet, die Signatur sei selbst die fachliche Workflow-Entscheidung.
- Zusätzliche fachliche Causation zum Documents-Workflow bleibt nötig, wenn:
  - der Signatur-Command isoliert aus dem Signaturmodul stammt,
  - nur `signer_user`, Dateipfad, Ziel-PDF oder Zeitstempel bekannt ist,
  - Signaturereignisse mit Review/Approval/Release gemeinsam bewertet werden,
  - die Signatur als Teil des Documents-MVP-Nachweises und nicht nur als separater technischer Signatur-Nachweis erscheinen soll.

## Technische Folgeprozesse
- Signaturservice, PDF-Signatur, Label-Aufbringung, Zertifikatsprüfung, Hashing, Dry-Run, Ausgabe-PDF und Artefaktaktualisierung können eigene technische Teilketten bilden.
- Technische Teilketten dürfen einen Signatur-Command oder eine vorherige Signatur-Service-Operation als unmittelbare Causation nutzen.
- Für einen Documents-MVP-Nachweis müssen technische Teilketten zusätzlich an die fachliche Documents-Transition oder eine freigegebene Use-Case-Klammer rückführbar bleiben.
- `system` oder ein benannter Service Actor ist nur zulässig, wenn:
  - der Vorgang tatsächlich technisch/service-initiiert ist,
  - keine menschliche Workflow-Verantwortung verdeckt wird,
  - die Causation zum fachlichen Auslöser nachvollziehbar bleibt,
  - Signatur-Actor und AuditActor getrennt bewertet werden.
- Technische Causation erklärt, warum die Signatur-Service-Operation lief. Sie erklärt nicht, wer fachlich Review, Approval oder Release ausgeführt hat.
- Zertifikatsprüfung, sichtbare Labels und Signaturbild sind Signaturmetadaten oder Signatur-Nachweisinformationen; sie ersetzen weder Causation noch Actor.

## Event-/Auditlog-Kopplung
- Zielregel:
  - Signaturereignisse, Documents-Events und Auditlog sollen für einen gemeinsamen Documents-Nachweis dieselbe fachliche Kette erklären können.
  - Eine gemeinsame Correlation kann die Use-Case-Klammer bilden; Causation erklärt die Richtung zwischen Workflow-Transition, Signatur-Command und technischen Signaturfolgen.
  - Auditlog darf nicht nur über Zeit/Ziel/Action heuristisch mit Signatur- und Documents-Events verbunden werden, wenn `kettenbelastbar` behauptet wird.
- Getrennte Teilketten sind zulässig, wenn:
  - ein separater Signatur-Nachweis geführt wird,
  - die Signatur-Service-Operation keinen Documents-Workflow-Nachweis behauptet,
  - technische Signaturereignisse nur interne Signaturdiagnostik darstellen,
  - der Export die Trennung sichtbar macht.
- Getrennte Teilketten sind nicht ausreichend, wenn:
  - ein Documents-MVP-Nachweis Review/Approval/Release und Signatur gemeinsam belastbar erklären soll,
  - ein `SIGNED_PDF` als Ergebnis einer Workflow-Transition bewertet wird,
  - ein technischer Signaturservice menschliche Workflow-Verantwortung berühren könnte.
- Offen bleibt:
  - ob Auditlog eigene Causation-Felder erhält,
  - ob Signaturereignisse auf Documents-Events verweisen,
  - ob Documents-Events auf Signaturereignisse verweisen,
  - ob eine Use-Case-ID oder Command-ID die primäre Klammer wird,
  - welche konkrete technische ID in `causation_id` steht.

## Export-Auswirkung
- `kettenbelastbar` für eine Documents-nahe Signaturkette ist erst möglich, wenn:
  - der direkte Signaturauslöser klar ist,
  - der Signaturauslöser fachlich auf die Documents-Workflow-Transition oder Use-Case-Klammer zurückführbar ist,
  - Signatur-Actor, Workflow-Actor, AuditActor und Service Actor getrennt bewertet werden,
  - Event- und Auditlog-Kopplung nicht nur heuristisch erfolgt.
- `ketten-eingeschränkt` gilt, wenn:
  - Signaturereignisse eigene Default-Correlation haben, aber keine Causation zur Workflow-Transition,
  - Signatur-Command vorhanden wäre, aber kein fachlicher Parent erkennbar ist,
  - Documents-Event und Signatur-Event nur über Zeit, Datei, Ziel oder Status zusammengeführt werden,
  - Auditlog keine Kettenreferenz trägt.
- `ketten-legacy` gilt, wenn:
  - bestehende Signaturereignisse ohne rekonstruierbare Causation rückwirkend eingeordnet werden,
  - nur freie Strings, Dateipfade, sichtbare Labels oder Altdaten vorhanden sind,
  - technische Teilketten nicht mehr fachlich auf Documents-Workflow zurückgeführt werden können.
- Fehlende Causation ist blockierend für einen belastbaren gemeinsamen Documents-MVP-Nachweis aus Workflow und Signatur.
- Fehlende Causation blockiert nicht zwingend einen separaten eingeschränkten Signatur-Nachweis, sofern dieser nicht als belastbarer Documents-Workflow-Nachweis ausgegeben wird.
- Signatur-Nachweis und Documents-Nachweis dürfen getrennt bleiben, müssen dann aber mit getrenntem Kettenstatus und getrenntem Actor-Status bewertet werden.

## Umgang mit aktuellem Zustand

| Fundtyp | Aktueller Zustand | Policy-Bewertung | Spätere Behandlung |
| --- | --- | --- | --- |
| Documents-Workflow-Events | Review/Approval/Editing/Gültigkeit publizieren Documents-Events ohne explizite Causation. | Für Signaturketten `ketten-eingeschränkt`, solange Signaturfolge nicht rückführbar ist. | Kein Cleanup in AP-019. |
| Signaturmodul-Events | `domain.signature.sign.*.v1` publiziert mit `actor_user_id=request.signer_user`, aber ohne Causation. | Signatur-Nachweis möglich, aber nicht Documents-kettenbelastbar. | Causation-Ziel später technisch festlegen. |
| Signatur-Auditlog | `signature.signed` / `signature.dry_run` nutzt `actor=request.signer_user or "system"` ohne Kettenfelder. | Auditlog-/Event-Verbindung eingeschränkt. | AP-016-Kopplungsentscheidung bleibt offen. |
| `SIGNED_PDF`-Artefakt | Persistiert aus Signatur-Transition, Metadatum enthält Transition und Inputpfad. | Artefaktmetadatum ersetzt keine Causation. | Später als Nachweisquelle nur mit Kettenstatus bewerten. |
| Signatur-Service-Operationen | Visual/Crypto/Both/Dry-Run sind technische Ausführungen. | Technische Teilkette, nicht automatisch Documents-Workflow-Kette. | Bei MVP-Nachweis an Signatur-Command und fachlichen Parent koppeln. |
| EventEnvelope | Unterstützt `causation_id`, aber Aufrufer setzen sie nicht. | Plattformfähigkeit vorhanden, Zielsemantik nicht umgesetzt. | Keine Schema-/API-Entscheidung in AP-019. |

## Nicht-Entscheidungen
- Keine konkrete API.
- Keine API-Signatur.
- Kein DTO.
- Kein Event-Schema.
- Kein Auditlog-Schema.
- Kein Exportformat.
- Keine Migration.
- Keine Backend-Route.
- Keine Signatur-Implementierung.
- Keine Implementierung von UserContext, RequestContext, AuditActor, Signaturservice, Eventkopplung oder Audit-Export.
- Keine Entscheidung über elektronische Signatur, Re-Auth, Zertifikatsrecht oder rechtliches Signaturniveau.
- Keine Entscheidung, ob Signaturketten Teil des Documents-Exports oder eines separaten Signatur-Exports sind.
- Keine konkrete Entscheidung, ob `causation_id` technisch auf Event-ID, Command-ID, Use-Case-ID oder Audit-ID zeigt.
- Keine Änderung an Documents-Services, Signaturmodul, EventEnvelope, AuditLogger, LogQueryService, GUI, CLI, Backend oder Tests.

## Konsequenzen
- Für Documents-Services:
  - Services bleiben fachliche Grenze, an der die Workflow-Transition und ihr Signaturbedarf bestimmt werden.
  - Spätere Pakete müssen die fachliche Parent-Beziehung der Signaturkette explizit modellieren, ohne hier eine API festzulegen.
- Für Signaturmodul:
  - Signaturereignisse dürfen weiterhin als Signatur-Nachweisartefakte verstanden werden, aber nicht automatisch als Documents-Workflow-Kette.
  - Technische Signatur-Service-Operationen brauchen für gemeinsame Documents-Nachweise einen fachlichen Parent.
- Für Auditlog:
  - Auditlog bleibt ohne Kettenfelder aktuell nur heuristisch verbindbar.
  - Ob und wie Auditlog Causation trägt, bleibt separate Supervisor-Entscheidung.
- Für Export/Nachweispaket:
  - Signatur-Nachweis und Documents-Nachweis müssen getrennt oder gemeinsam mit sichtbarem Kettenstatus bewertet werden.
  - Fehlende Causation darf nicht durch Actor-Gleichheit, sichtbaren Unterzeichner, Dateipfad oder Zeitnähe ersetzt werden.
- Für Legacy:
  - Bestehende Signaturereignisse ohne klare Causation bleiben `ketten-eingeschränkt` oder `ketten-legacy`.
  - Keine rückwirkende Rekonstruktion wird durch diese ADR angenommen.

## Risiken
- Technische Risiken:
  - Eine spätere konkrete Referenzwahl kann Eventing, Auditlog, Signaturservice und Documents-Servicegrenzen berühren.
  - Zu frühe Festlegung auf Event-ID, Command-ID oder Use-Case-ID könnte AP-016-Kopplung vorwegnehmen.
  - Ohne Kontextquelle entstehen weiter isolierte Default-Correlations.
- Fachliche Risiken:
  - Approval/Review/Release, Signatur-Command und technische Signatur-Service-Operation könnten vermischt werden.
  - Causation könnte irrtümlich als Verantwortlichkeit gelesen werden.
  - `system` oder Service Actor könnte menschliche Workflow-Verantwortung verdecken.
  - Signatur-Actor und AuditActor könnten trotz AP-018 wieder zusammenfallen.
- Audit-/Nachweisrisiken:
  - Exporte könnten Signaturereignisse ohne fachlichen Parent zu belastbar darstellen.
  - Separate Signatur- und Documents-Nachweise könnten widersprüchlich wirken, wenn die Kette nicht erklärt ist.
  - Legacy-Signaturen ohne rekonstruierbare Causation können überinterpretiert werden.

## Offene Supervisor-Entscheidungen
- Soll `causation_id` in Signaturketten technisch auf Approval, Review, Release, Signatur-Command oder Use-Case-ID zeigen?
- Wird der Signatur-Command als primärer direkter Auslöser eingeführt oder bleibt er nur Policy-Begriff?
- Sind Signaturketten Teil des Documents-Exports oder eines separaten Signatur-Exports mit Verknüpfung?
- Wird der Signaturservice als `system` oder als benannter Service Actor geführt?
- Brauchen technische Signaturfolgeprozesse eigene Causation-Teilketten?
- Wie werden Legacy-Signaturereignisse ohne klare Causation markiert?
- Muss ein gemeinsamer Documents-MVP-Nachweis zwingend dieselbe Correlation zwischen Workflow, Signatur und Auditlog teilen?
- Bekommt Auditlog eigene Kettenfelder oder bleibt Kopplung export-/nachweispaketlogisch?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-011_DOCUMENTS_EVENT_ACTOR_MATRIX.md`
  - `docs/AP-013_DOCUMENTS_EVENT_CORRELATION_CAUSATION_MATRIX.md`
  - `docs/AP-014_DOCUMENTS_CORRELATION_CAUSATION_POLICY_ADR.md`
  - `docs/AP-015_DOCUMENTS_AUDIT_EXPORT_READINESS_MATRIX.md`
  - `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`
  - `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md`
  - `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/signature_guard.py`
  - `modules/signature/signature_execute_ops.py`
  - `modules/signature/contracts.py`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-019_DOCUMENTS_SIGNATURE_CAUSATION_REFERENCE_ADR.md`.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Documents-/Signatur-/Event-/Auditlog-Hotspots.
  - `rg` in `modules/documents` nach SignRequest-, `signer_user`-, Signatur-, Domain-Event-, Audit-, Correlation-/Causation-, `SIGNED_PDF`-, `SOURCE_PDF`-, `RELEASED_PDF`- und Workflow-Begriffen.
  - `rg` in `modules/signature` nach SignRequest-, `signer_user`-, Signatur-, Domain-Event-, Audit-, Correlation-/Causation-, Visual-/Crypto-/Dry-Run- und Label-Begriffen.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-019 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Keine Signatur-Implementierung durchgeführt.
- Keine bestehenden Findings repariert.
- Keine bestehenden ADR-/Inventar-Dateien geändert.
- Nur `docs/AP-019_DOCUMENTS_SIGNATURE_CAUSATION_REFERENCE_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein enges Umsetzungsvorbereitungspaket für genau einen signaturpflichtigen Documents-Workflow-Slice oder ein reines ADR-Paket zur Auditlog-Kettenfeld-Strategie freigegeben wird; keine Implementierung automatisch starten.
