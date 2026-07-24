# AP-018 Documents-Signatur-vs-Audit-Actor ADR

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
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert AuditActor als explizit bestimmte handelnde Instanz eines auditrelevanten Use Cases. Correlation/Causation ersetzen keinen Actor.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` verlangt sichtbare Actor-Qualität für MVP-Audit-Exports.
- Bezug auf AP-009/AP-011: Documents-Analysen markieren SignRequest-Signer, Signaturmodul-Events und Documents-Workflow-Actor als getrennt zu bewertende Signatur-/Audit-Actor-Lücke.
- Bezug auf AP-010: Read-Receipt-Actor ist ein eigener Actor-Begriff und nicht automatisch Signatur-Actor.
- Bezug auf AP-012: Signatur-Actor / `signer_user` darf Workflow-AuditActor nicht automatisch ersetzen; Owner-/`system`-Fallbacks bleiben eingeschränkt oder legacy.
- Bezug auf AP-013/AP-014: Signaturereignisse sind aktuell nicht kausal mit Documents-Workflow-Events verbunden. Causation ist für Signatur-nahe Documents-Flows Zielanforderung, ersetzt aber keinen Actor.
- Bezug auf AP-015: Documents-nahe Signaturereignisse sind exportrelevant eingeschränkt, weil Signatur-Actor, Documents-AuditActor und Kettenbezug getrennt und ungeklärt sind.
- Bezug auf AP-016: Domain-Event und Auditlog dürfen keine unterschiedlichen Actor-Wahrheiten erzeugen; Signatur-nahe Documents-Flows brauchen konsistente, kausal erklärbare Kopplung.
- Bezug auf AP-017: Freigabe/Approval, RELEASED_PDF und technische Folgeprozesse müssen getrennt darstellbar bleiben; Signaturereignisse dürfen diese Trennung nicht verwischen.
- Aktuelle Hotspots:
  - `modules/documents/workflow_use_cases.py` nutzt `actor_user_id` für Review, Approval, Editing und Gültigkeitsverlängerung als fachliche Workflow-Handlung.
  - `modules/documents/signature_guard.py` erzwingt bei signaturpflichtigen Transitionen einen `sign_request` und persistiert daraus ein `SIGNED_PDF`-Artefakt.
  - `modules/signature/signature_execute_ops.py` publiziert `domain.signature.sign.*.v1` und nutzt `request.signer_user` als Event-Actor.
  - `modules/signature/signature_execute_ops.py` schreibt Signatur-Auditlog mit `actor=request.signer_user or "system"`.
  - `modules/signature/contracts.py` definiert `SignRequest.signer_user`, sichtbares Layout (`name_text`, `date_text`) und Signaturmodus, aber keine Documents-AuditActor-Semantik.
  - `qm_platform/events/event_envelope.py` unterstützt Correlation/Causation, die gelesenen Signatur-/Documents-Aufrufer setzen sie aber nicht explizit.
  - `qm_platform/logging/audit_logger.py` schreibt Auditlog ohne Correlation/Causation.

## Begriffe
- **Documents-Workflow-User**: Menschlicher User, der einen Documents-Workflow-Schritt fachlich ausführt, z. B. Editing abschließen, Review akzeptieren oder Approval/Freigabe akzeptieren.
- **AuditActor**: Die im Audit-/Nachweiskontext protokollierte handelnde Instanz eines auditrelevanten Use Cases nach AP-006.
- **Signatur-Actor**: Identität, die den Signaturvorgang ausführt oder in `SignRequest.signer_user` geführt wird. Sie ist nicht automatisch AuditActor eines Documents-Workflow-Schritts.
- **Signaturidentität / Zertifikatsinhaber**: Identität aus Signaturdaten, Zertifikat, sichtbarem Namen oder Signaturbild. Sie kann Nachweisinformation sein, ist aber nicht automatisch ausführender Workflow-User oder AuditActor.
- **Sichtbarer Unterzeichner**: Text oder Bild im PDF, z. B. `name_text`, Datum oder Unterschriftenbild. Sichtbarkeit im Dokument beweist nicht allein die auditfachliche Ausführung.
- **Technischer Signaturvorgang**: Technische Erzeugung eines signierten PDFs, visuelle Signatur, kryptografische Signatur, Dry-Run oder Signaturservice-Ausführung.
- **Technischer Signaturservice / Service Actor**: Nicht-menschliche technische Identität für einen technischen Signaturfolgeprozess. Sie darf menschliche Workflow-Verantwortung nicht ersetzen.
- **Signatur-Nachweis**: Nachweis über den Signaturvorgang selbst. Er ist nicht automatisch identisch mit dem Documents-Workflow-Nachweis.

## Entscheidung
Empfohlene Ziel-Policy:

Signatur-Actor ist nicht automatisch AuditActor. Der AuditActor eines Documents-Workflow-Use-Cases wird an der Documents-Service-Grenze fachlich bestimmt. Signaturdaten, Zertifikatsdaten, sichtbare Unterzeichnerfelder, `SignRequest.signer_user`, Signaturbild, Signaturvorlagen oder technische Signaturservices dürfen nicht still als AuditActor des Documents-Workflow-Schritts übernommen werden.

Signatur-Actor und AuditActor können identisch sein, wenn derselbe menschliche User aus einem freigegebenen UserContext/Request-Kontext den Documents-Workflow-Schritt ausführt und zugleich den Signaturvorgang auslöst oder bestätigt. Diese Identität muss ausdrücklich aus der service-seitigen Nachweisentscheidung und der Signatur-Kontextquelle erklärbar sein; sie darf nicht allein aus `signer_user`, sichtbarem Namen, Zertifikatsinhaber, Owner, GUI-/CLI-Zustand oder freiem String abgeleitet werden.

Signatur-Actor und AuditActor müssen getrennt dargestellt werden, wenn der Signaturvorgang technisch, service-nah, stellvertretend, asynchron, durch einen Service Actor, mit anderem Zertifikatsinhaber, mit anderem sichtbaren Unterzeichner oder ohne belastbare Causation zum Documents-Workflow-Schritt erfolgt. In diesen Fällen ist der Signatur-Actor Nachweisinformation des Signaturvorgangs, aber nicht automatisch Workflow-/AuditActor.

Review, Approval/Freigabe, Gültigkeitsverlängerung und Editing-Abschluss bleiben fachliche Documents-Workflow-Handlungen. Die Signatur kann ein eigener fachlicher oder technischer Nachweisschritt innerhalb derselben Kette sein. Es gibt keine stille Gleichsetzung von Approval-Actor, Review-Actor, Signatur-Actor, Zertifikatsinhaber, sichtbarem Unterzeichner und AuditActor.

Diese ADR entscheidet keine konkrete API-Signatur, kein DTO, kein Event-Schema, kein Auditlog-Schema, kein Exportformat und keine Implementierung.

## Verhältnis Signatur-Actor zu AuditActor

| Fall | Policy-Bewertung | Nachweisstatus | Begründung |
| --- | --- | --- | --- |
| Workflow-User und Signatur-Actor stammen aus demselben freigegebenen UserContext/Request-Kontext und derselben Service-Nachweisentscheidung | können identisch sein | `belastbar` nach Quellen- und Kettenklassifikation | Identität ist fachlich bestimmt, nicht aus Signaturdaten geraten. |
| `SignRequest.signer_user` entspricht zufällig dem Workflow-Actor-String | nicht automatisch identisch | `eingeschränkt` bis Quelle belegt ist | String-Gleichheit ersetzt keine Actor-Quelle. |
| Sichtbarer Unterzeichnername entspricht dem Workflow-User | nicht automatisch identisch | `eingeschränkt`/Metadatum | PDF-Label ist Darstellung, keine Actor-Bestimmung. |
| Zertifikatsinhaber entspricht dem Workflow-User | offen/eingeschränkt | abhängig von Signatur-/Zertifikats-Governance | Zertifikat kann Signaturidentität belegen, aber nicht automatisch Documents-AuditActor. |
| Signaturservice oder `system` signiert technisch | getrennt darstellen | `belastbar` nur bei Governance und Causation, sonst `eingeschränkt` | Technischer Actor erklärt Signaturausführung, nicht fachliche Workflow-Entscheidung. |
| Owner, Zieluser, GUI-/CLI-Zustand, `unknown` oder ungeprüfter String liefert Signatur- oder AuditActor | nicht belastbar | `legacy`/nicht belastbar | Keine zulässige Zielquelle für AuditActor. |

## Verhältnis Signatur zu Documents-Workflow
- Review, Approval/Freigabe, Editing-Abschluss und Gültigkeitsverlängerung sind fachliche Workflow-Handlungen.
- Signatur ist ein eigener Nachweisschritt, der fachlich erforderlich sein kann, aber nicht automatisch die Workflow-Handlung selbst ist.
- Eine signaturpflichtige Transition kann aus mindestens zwei Nachweisaspekten bestehen:
  - fachliche Workflow-Entscheidung mit Workflow-/AuditActor,
  - Signaturvorgang mit Signatur-Actor, Signaturidentität, Signaturmodus und technischem Ergebnis.
- Beide Aspekte dürfen denselben Menschen betreffen, müssen aber getrennt erklärbar bleiben.
- Signaturereignisse dürfen Documents-Workflow-Events nicht still überstimmen.
- Documents-Workflow-Audit darf Signaturdaten nicht still als Actor-Wahrheit übernehmen.
- Ein erfolgreich signiertes PDF beweist nicht allein, wer fachlich Review/Approval ausgeführt hat.

## Actor-Quellen

| Quelle | Zulässigkeit für AuditActor | Zulässigkeit für Signatur-Actor | Policy |
| --- | --- | --- | --- |
| Freigegebener UserContext/Request-Kontext an der Service-Grenze | ja | ja, wenn Signaturvorgang durch denselben User ausgeführt wird | Zielquelle für menschliche Documents-Workflow-Use-Cases. |
| `SignRequest.signer_user` | nicht allein | ja/eingeschränkt | Signaturidentität aus Signaturaufruf; für AuditActor nur mit freigegebener Kontextquelle. |
| Zertifikatsinhaber | nicht allein | ja/offen | Signatur-/Zertifikatsidentität; Governance und Nachweisniveau separat entscheiden. |
| Sichtbarer Unterzeichner / PDF-Label / Signaturbild | nein | Metadatum | Darstellung im Artefakt, keine verlässliche Actor-Quelle. |
| Technischer Signaturservice / Service Actor | ja/eingeschränkt für technischen Folgeprozess | ja/eingeschränkt | Nur mit benannter Governance und Causation zum fachlichen Auslöser. |
| `system` | eingeschränkt | eingeschränkt | Nur für echte technische Signaturfolgeprozesse, nicht als Ersatz für fehlenden UserContext. |
| Owner / Zieluser / Reviewer-/Approver-Zuordnung als Objektableitung | nein | nein als automatische Quelle | Target, Assignment oder Berechtigungsinfo, aber kein Actor-Beweis. |
| GUI-/CLI-Zustand, lokale Current-User-Quelle | nein für Zielzustand | eingeschränkt/legacy im Bestand | Adapter darf Kontext transportieren, nicht Actor final bestimmen. |
| `unknown` oder freie ungeprüfte Strings | nein | nein für belastbare Signatur | Höchstens Legacy-/Fehler-/Importmetadatum. |

## Event-/Auditlog-Konsistenz
- Zielregel:
  - Documents-Events, Signatur-Events und Auditlog-Einträge dürfen keine widersprüchlichen Actor-Wahrheiten erzeugen.
  - Wenn ein Signaturereignis einen Documents-Workflow-Schritt unterstützt oder erklärt, muss die Kette kausal nachvollziehbar bleiben.
  - Fehlende Causation zwischen `domain.signature.sign.*` und `domain.documents.*` schränkt die Kettenbelastbarkeit ein.
- Konsequenzen für Signaturereignisse:
  - Signatur-Domain-Events können Signatur-Actor, Signaturmodus und Signaturergebnis beschreiben.
  - Documents-Domain-Events beschreiben Workflow-Entscheidungen und fachlichen Zustand.
  - Auditlog-Einträge müssen Actor-Qualität und Kettenstatus getrennt bewertbar halten.
- Unzulässig:
  - Signatur-Event hat `signer_user`, Documents-Auditlog hat anderen Actor, und der Export stellt beides ohne Erklärung als denselben Actor dar.
  - Auditlog nutzt `system`, Signatur-Event nutzt `signer_user`, und die technische Kette wird als voll belastbar behauptet.
  - Sichtbare Signaturdaten werden als Beweis für Documents-Workflow-Ausführung verwendet, ohne freigegebenen Kontext.
- Kettenstatus:
  - Ohne Causation zu Approval, Review, Editing, Gültigkeitsverlängerung, Signatur-Command oder Use-Case-ID bleibt der Signatur-/Documents-Zusammenhang `ketten-eingeschränkt`.
  - Welche technische Referenz Causation konkret nutzt, bleibt offen.

## MVP-Export-Auswirkung
- Signatur-Actor und AuditActor müssen im Nachweis getrennt bewertet werden:
  - Actor-Qualität des Documents-Workflow-Schritts: `belastbar`, `eingeschränkt` oder `legacy`.
  - Signatur-Actor-/Signaturidentitätsqualität: separat als Signatur-Nachweisstatus zu bewerten.
  - Kettenstatus zwischen Documents-Workflow und Signatur: `kettenbelastbar`, `ketten-eingeschränkt` oder `ketten-legacy`.
- Signaturflüsse können belastbar exportierbar werden, wenn:
  - Workflow-/AuditActor aus freigegebenem UserContext/Request-Kontext stammt,
  - Signatur-Actor oder Signaturidentität nachvollziehbar und getrennt klassifiziert ist,
  - Signaturereignis, Auditlog und Documents-Workflow-Event kausal erklärbar verbunden sind,
  - technische Service-/System-Actor nicht menschliche Verantwortung verdecken.
- Signaturflüsse bleiben eingeschränkt, wenn:
  - `signer_user` nur aus Adapter-/Legacy-Kontext stammt,
  - Signaturereignisse und Documents-Events nur heuristisch über Zeit, Datei oder Ziel verbindbar sind,
  - Auditlog keine Correlation/Causation trägt,
  - Signatur-Actor und Workflow-Actor nur über gleiche Strings gleichgesetzt werden.
- Signaturflüsse sind legacy/nicht belastbar, wenn:
  - `unknown`, Owner-Fallback, Zieluser-Ableitung oder ungeprüfte freie Strings als Actor genutzt werden,
  - technische `system`-Signatur menschliche Workflow-Ausführung ersetzt,
  - bestehende Signaturereignisse ohne rekonstruierbare Kette rückwirkend als belastbar behauptet würden.
- Ob Signaturereignisse Teil des Documents-Nachweises oder eines separaten Signatur-Nachweises mit kausaler Verknüpfung bleiben, ist ausdrücklich offen.

## Umgang mit aktuellem Zustand

| Fundtyp | Aktueller Zustand | Policy-Bewertung | Spätere Behandlung |
| --- | --- | --- | --- |
| Documents-Review/Approval mit Signaturpflicht | Workflow-Actor wird als `actor_user_id` geprüft; Signatur wird über `sign_request` erzwungen. | Fachlicher Actor und Signatur-Actor müssen getrennt bewertet werden. | Keine Änderung in AP-018; spätere Umsetzungsvorbereitung braucht Kontext- und Kettenentscheidung. |
| `modules/documents/signature_guard.py` | Führt Signatur über `signature_api.sign_with_fixed_position(sign_request)` aus und persistiert `SIGNED_PDF`. | Signaturfolgeprozess, aber keine Actor-/Causation-Policy in diesem Hotspot. | Causation und Actor-Trennung später entscheiden. |
| `modules/signature/signature_execute_ops.py` Events | `domain.signature.sign.*.v1` nutzt `actor_user_id=request.signer_user`. | Signatur-Actor vorhanden, aber nicht automatisch Documents-AuditActor. | Für Documents-Nachweis nur mit Kausalbezug und Quellenstatus verwenden. |
| `modules/signature/signature_execute_ops.py` Auditlog | Audit-Actor ist `request.signer_user or "system"`. | Eingeschränkt; `system` nur für echte technische Vorgänge zulässig. | System-/Service-Actor-Policy und Kettenkopplung später klären. |
| Signaturvorlagen/-Assets | Owner und Signaturasset können signaturnah relevant sein. | Owner/Asset-Inhaber ist nicht automatisch Documents-AuditActor. | Als Signaturmetadatum getrennt darstellen. |
| Sichtbare PDF-Labels | `name_text`/Datum können aus Layout oder `signer_user` entstehen. | Darstellung, keine belastbare Actor-Quelle. | Nicht als AuditActor übernehmen. |
| EventEnvelope / AuditLogger | EventEnvelope kann Correlation/Causation tragen; AuditLogger nicht. | Aktuelle Kopplung eingeschränkt. | AP-016/AP-014-Folgeentscheidung nötig. |

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
- Keine Entscheidung, ob Signaturereignisse im Documents-Export oder in einem separaten Signatur-Export erscheinen.
- Keine Entscheidung, ob Signatur-Event, Auditlog oder beides für MVP technisch verbindlich wird.
- Keine Entscheidung, ob Causation auf Approval, Release, Signatur-Command oder Use-Case-ID zeigt.
- Keine Änderung an Documents-Services, Signaturmodul, EventEnvelope, AuditLogger, LogQueryService, GUI, CLI, Backend oder Tests.

## Konsequenzen
- Für Documents-Services:
  - Services bleiben fachliche Grenze für Workflow-Actor, AuditActor und Nachweisentscheidung.
  - Signaturpflichtige Transitionen brauchen später eine klare Trennung zwischen Workflow-Entscheidung und Signaturvorgang.
- Für Signaturmodul:
  - Signaturmodul-Events und Signatur-Auditlog beschreiben Signaturvorgänge, nicht automatisch Documents-Workflow-Entscheidungen.
  - `signer_user` bleibt Signaturidentität, bis eine freigegebene Service-Entscheidung ihn als Workflow-/AuditActor bestätigt.
- Für Audit-Export / Nachweispaket:
  - Actor-Qualität, Signaturidentität, sichtbarer Unterzeichner, Kettenstatus und Workflowstatus müssen getrennt bewertbar bleiben.
  - Export darf Signaturdaten nicht als voll belastbaren AuditActor darstellen, wenn die Quelle oder Kette eingeschränkt ist.
- Für Legacy:
  - Bestehende Signaturereignisse ohne klare Actor-/Kettenqualität dürfen nicht rückwirkend aufgewertet werden.
  - `system`, Owner, sichtbare Labels und freie Strings müssen sichtbar eingeschränkt oder legacy bleiben.
- Für Tests:
  - Keine Tests werden in AP-018 geändert.
  - Spätere Tests müssen Workflow-Actor, Signatur-Actor, sichtbaren Unterzeichner und Kettenstatus getrennt prüfen.

## Risiken
- Technische Risiken:
  - Signaturmodul und Documents-Modul erzeugen getrennte Events ohne explizite Causation.
  - AuditLogger kann Signatur- und Documents-Auditlog aktuell nicht über Correlation/Causation verbinden.
  - Spätere Kopplung kann Eventing, Auditlog, Signaturservice und Documents-Servicegrenzen berühren.
- Fachliche Risiken:
  - `signer_user` kann fälschlich als Workflow-/AuditActor gelesen werden.
  - Sichtbare Unterzeichnerfelder oder Zertifikatsdaten können als menschliche Workflow-Freigabe missverstanden werden.
  - Technische Signaturservices können menschliche Verantwortung verdecken.
  - Owner oder Zieluser kann mit Signaturinhaber oder AuditActor vermischt werden.
- Audit-/Nachweisrisiken:
  - Documents-Nachweispakete könnten Signaturereignisse ohne Kausalbezug zu belastbar darstellen.
  - Signatur-Export und Documents-Export können widersprüchliche Actor-Aussagen enthalten.
  - Legacy-Signaturen ohne rekonstruierbare Kette können überinterpretiert werden.

## Offene Supervisor-Entscheidungen
- Sollen Signaturereignisse im Documents-Export oder in einem separaten Signatur-Export erscheinen?
- Braucht ein signaturpflichtiger Documents-MVP-Workflow ein Signatur-Domain-Event, ein Signatur-Auditlog oder beides im Nachweis?
- Soll ein technischer Signaturservice als `system` oder als benannter Service Actor geführt werden?
- Soll Causation auf Approval, Review, Release, Signatur-Command oder Use-Case-ID zeigen?
- Wie werden bestehende Signaturereignisse ohne klare Actor-/Kettenqualität markiert?
- Wie werden Zertifikatsinhaber, sichtbarer Unterzeichner, SignRequest-Signer und ausführender Workflow-User getrennt dargestellt?
- Müssen Workflow-Actor und Signatur-Actor in signaturpflichtigen Transitionen identisch sein, oder reicht eine kausale Trennung?
- Welche Signatur-/Re-Auth-/Zertifikatsanforderungen gelten für ein späteres rechtliches Nachweisniveau?

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
  - `docs/AP-016_DOCUMENTS_AUDITLOG_EVENT_COUPLING_ADR.md`
  - `docs/AP-017_DOCUMENTS_RELEASE_PDF_EVIDENCE_EVENT_ADR.md`
  - `modules/documents/workflow_use_cases.py`
  - `modules/documents/service.py`
  - `modules/documents/signature_guard.py`
  - `modules/signature/contracts.py`
  - `modules/signature/signature_execute_ops.py`
  - `modules/signature/service.py`
  - `modules/signature/template_use_cases.py`
  - `modules/signature/signature_policy_ops.py`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/audit_logger.py`
  - `qm_platform/logging/log_query_service.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md`.
  - `ReadFile` der freigegebenen ADR-/Inventar-/Roadmap-/Regeldateien und der erlaubten Documents-/Signatur-/Event-/Auditlog-Hotspots.
  - `rg` in `modules/documents` nach SignRequest-, `signer_user`-, Signatur-, Actor-, Event-, Audit-, Correlation-/Causation- und Fallback-Begriffen.
  - `rg` in `modules/signature` nach SignRequest-, `signer_user`-, Signatur-, Actor-, Event-, Audit-, Zertifikats-/sichtbarem Feld-, Correlation-/Causation- und Fallback-Begriffen.
- Pflichtgate:
  - Existenzprüfung der Zieldatei vor Erstellung per `Glob` -> Datei existierte nicht.
  - Review der neuen Datei auf verbotene Umsetzungsentscheidungen -> keine Implementierung, keine API-/Event-Schema-/DTO-/Exportformat-/Migrationsentscheidung enthalten.
- Keine Testsuite ausgeführt, weil AP-018 ein ADR-/Dokumentationspaket ist und Tests ausdrücklich ausgeschlossen sind.
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
- Nur `docs/AP-018_DOCUMENTS_SIGNATURE_VS_AUDIT_ACTOR_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes ein reines ADR-Paket zur Signatur-/Causation-Referenz (`Approval`, `Release`, `Signatur-Command` oder `Use-Case-ID`) oder ein enges Umsetzungsvorbereitungspaket für genau einen signaturpflichtigen Documents-Workflow-Slice freigegeben wird; keine Implementierung automatisch starten.
