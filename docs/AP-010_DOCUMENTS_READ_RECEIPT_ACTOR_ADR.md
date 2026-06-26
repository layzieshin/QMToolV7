# AP-010 Documents-Read-Receipt-Actor ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Event-Schema-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-009: `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md` identifiziert Read-Tracking-/Receipt-Events ohne belastbaren Event-Actor als kritischen Documents-Gap. Besonders relevant sind `PdfReadTrackingService.start` und `finalize`, deren Events keinen `actor_user_id` tragen, obwohl Session und Receipt einen `user_id` speichern.
- Bezug auf AP-006A: `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` legt fest, dass MVP-Audit-Exports Actor-Quellen mindestens als `belastbar`, `eingeschränkt` oder `legacy` unterscheiden müssen. Zieluser, lokale Current-User-Quellen, GUI-/CLI-Zustand, `"unknown"` und ungeprüfte freie Actor-Strings sind nicht als belastbarer Audit Actor geeignet.
- MVP-Relevanz: Lesebestätigung / Kenntnisnahme ist Teil der MVP-Priorisierung und hat Nachweischarakter, sobald sie belegen soll, dass ein bestimmter User eine freigegebene Dokumentversion zur Kenntnis genommen hat.
- Geltende Architekturregeln:
  - Services bleiben fachliche Grenze für auditrelevante Documents-Use-Cases.
  - Für interaktive Lesebestätigung ist die Zielquelle der ausdrücklich bestimmte ausführende User aus freigegebenem UserContext/Request-Kontext.
  - Audit Actor darf nicht aus Zieluser, Owner-Fallback, GUI/CLI-Zustand, lokalem Current User oder `unknown` als belastbarer Nachweis entstehen.
  - GUI, CLI und Backend dürfen Kontext transportieren und Status anzeigen, aber nicht final fachlich bestimmen.
  - Diese ADR ist ein Dokumentations-/Entscheidungspaket; keine Implementierung, keine API-Änderung, keine Event-Schema-Änderung und keine Migration.

## Begriffe
- **Read Receipt**: Persistierter Nachweis, dass eine konkrete Dokumentversion für einen konkreten User als gelesen / zur Kenntnis genommen erfasst wurde.
- **Kenntnisnahme**: Fachlicher Vorgang, bei dem ein User bestätigt oder durch freigegebenen Read-Tracking-Mechanismus nachweist, dass er eine freigegebene Dokumentversion wahrgenommen hat.
- **Ausführender User**: Menschliche Identität, die die Kenntnisnahme interaktiv ausführt oder bestätigt. Im Zielbild stammt sie aus freigegebenem UserContext/Request-Kontext.
- **Zieluser**: User, für den ein Lesestatus oder Schulungs-/Kenntnisnahmestatus geführt wird. Zieluser kann bei Selbstbestätigung mit dem ausführenden User identisch sein, darf aber nicht rein aus dem Zielobjekt als Actor abgeleitet werden.
- **Dokument-Owner**: Fachlich verantwortliche Person oder Rolle am Dokument. Owner ist nicht automatisch Actor der Kenntnisnahme eines anderen Users.
- **System Actor**: Explizit benannter nicht-menschlicher Actor für tatsächlich systeminitiierte Vorgänge. System Actor ist kein Ersatz für fehlenden UserContext bei interaktiver Kenntnisnahme.
- **Signatur-Actor**: Identität, die für einen Signaturvorgang verwendet wird. Signatur-Actor kann in einzelnen Flows mit dem ausführenden User übereinstimmen, ist aber nicht automatisch Read-Receipt-Actor.
- **Audit Actor**: Die im Audit-/Nachweiskontext protokollierte handelnde Instanz einer auditrelevanten Aktion nach AP-006.

## Entscheidung
Empfohlene Zielentscheidung:

Für interaktive Lesebestätigung / Kenntnisnahme ist der Actor der ausdrücklich bestimmte ausführende User, der den Read-Receipt-Vorgang ausführt oder bestätigt. Im Zielbild muss diese Identität aus einem freigegebenen UserContext oder Request-Kontext an der Documents-Service-Grenze stammen. Der gespeicherte `user_id` eines Read Receipts kann fachlich der Zieluser des Nachweises sein; er ist nur dann zugleich belastbarer Actor, wenn die Aktion als Selbst-Kenntnisnahme aus einem freigegebenen Kontext eindeutig bestimmt wurde.

Read-Tracking und Read-Receipt sind auditrelevant, sobald sie Nachweischarakter haben, z. B. als Voraussetzung für Schulung, Quiz, Freigabe eines Kenntnisnahmestands oder Audit-Export / Nachweispaket. Reine Anzeige von Lesestatus, UI-Buttons, Fortschrittsanzeigen oder Abfragen eines vorhandenen Receipts sind keine eigenen Actor-Ereignisse.

Owner, Zieluser, lokaler Current User, GUI-/CLI-Zustand und `unknown` sind für Read Receipts nicht als belastbare Actor-Quelle zulässig. `system` ist nur für echte systeminitiierte Markierungen oder technische Folgeprozesse eingeschränkt zulässig und muss als System Actor mit Nachweisstatus sichtbar bleiben. Stellvertretende Kenntnisnahme durch Admin/QMB ist keine Standardentscheidung dieser ADR; sie braucht eine explizite Supervisor-Entscheidung, weil sie Actor, Target und Berechtigung fachlich trennt.

Diese ADR entscheidet keine konkrete API-Signatur, kein Event-Schema, kein DTO, keine Exportstruktur und keine Implementierung.

## Actor-Quellen-Matrix

| Actor-Quelle | zulässig für Read Receipt: ja/nein/eingeschränkt | Nachweisstatus | Bedingung | Risiko | spätere Behandlung |
| --- | --- | --- | --- | --- | --- |
| Expliziter UserContext | ja | belastbar | Freigegebene Auth-/Session-/UserContext-Entscheidung; an Servicegrenze übergeben; User ist ausführende Identität. | UserContext darf Rollen- oder Signatursemantik nicht vermischen. | Zielquelle für interaktive Read-Receipt-Use-Cases. |
| Freigegebener Request-Kontext | ja | belastbar | Request-Kontext transportiert validierten Auth-/UserContext und wird service-seitig fachlich ausgewertet. | Backend/Transport könnte sonst fachlich interpretieren. | Für spätere Backend-/Multiuser-Slices konkretisieren. |
| Lokale `current_user.json` | nein für Zielzustand; höchstens Übergang | eingeschränkt/legacy | Nur bestehender Desktop-/Legacy-Sessionzustand; nicht für backend-migrierte Use Cases. | Lokale Datei ist keine belastbare Multiuser-/Request-Quelle. | In Exports markieren oder später je Use Case ersetzen. |
| `get_current_user()` | nein als implizite Service-Quelle | eingeschränkt/legacy | Bestand darf eingeordnet werden; nicht als neue Read-Receipt-Actor-Quelle verwenden. | Actor entsteht aus Prozesszustand statt aus Use-Case-Kontext. | Später durch explizite Kontextübergabe vorbereiten. |
| Owner-Fallback | nein | legacy/nicht belastbar, falls als Actor genutzt | Owner kann fachliches Target/Relation sein, aber nicht automatisch ausführender User. | Verfälscht Kenntnisnahme eines anderen Users. | In Documents-Fallback-Policy separat behandeln. |
| Zieluser | eingeschränkt | belastbar nur bei eindeutig bestimmter Selbst-Kenntnisnahme; sonst nicht belastbar/legacy | Zieluser darf Actor sein, wenn freigegebener Kontext beweist, dass dieser User selbst ausgeführt hat. | Reine Ableitung aus `receipt.user_id` oder Zielstatus verschleiert stellvertretende/automatische Aktionen. | Actor/Target in späterer Read-Receipt-Matrix trennen. |
| `system` | eingeschränkt | belastbar nur bei echter Systemaktion, sonst eingeschränkt/legacy | Nur für systeminitiierte Markierungen, Imports, technische Jobs oder Folgeprozesse mit expliziter Policy. | Kann fehlenden UserContext bei interaktiver Kenntnisnahme verdecken. | System-Actor-Policy und Exportkennzeichnung festlegen. |
| `unknown` | nein | legacy/nicht belastbar | Höchstens Altbestand, Importmetadatum oder unvollständige historische Quelle. | Kein identifizierbarer Actor. | Sichtbar markieren; nicht still reparieren. |
| GUI-/CLI-Adapterzustand | nein | nicht belastbar als finale Quelle | Adapter darf Kontext anzeigen/transportieren und UX-Gates nutzen. | Adapter würde fachliche Actor-Entscheidung übernehmen. | Service-Grenze und Kontextquelle später absichern. |
| SignRequest-/Signatur-Actor | nein als automatische Quelle | eingeschränkt/offen | Nur relevant, wenn ein separater Signaturvorgang stattfindet; nicht aus Signatur auf Receipt schließen. | Vermischt elektronische Signatur mit Kenntnisnahme. | Separate Signatur-vs-Audit-Actor-Matrix. |
| Import-/DOCX-/Kommentar-Autor | nein | legacy/metadaten | Externe Autoren sind Herkunftsmetadaten, nicht Read-Receipt-Actor. | Fremdautor könnte als QM-User missverstanden werden. | In Nachweispaketen getrennt ausweisen. |

## Auditrelevanz
- Auditrelevant sind:
  - erfolgreiche Lesebestätigung / Kenntnisnahme mit Nachweischarakter,
  - Read-Tracking-Abschluss, wenn daraus ein Read Receipt entsteht,
  - unvollständige Read-Session, falls sie fachlich als Nachweiskette, Schulungsvoraussetzung oder Compliance-Ereignis ausgewertet wird,
  - stellvertretende, automatische oder importierte Markierungen, wenn sie später produktiv erlaubt werden.
- Nicht als Actor-Ereignis zu werten sind:
  - reine Anzeige von Lesestatus,
  - Abfrage eines vorhandenen Receipts,
  - UI-Auswahl eines Dokuments,
  - Navigation im PDF ohne Nachweiswirkung,
  - Training-Inbox-/Matrix-Anzeige, solange sie nur vorhandene Statuswerte liest.
- Legacy-/Importfälle:
  - Importierte Altdaten dürfen als `legacy` oder eingeschränkt markiert werden.
  - Sie dürfen nicht automatisch als belastbare Selbst-Kenntnisnahme gelten.
  - Fehlende oder externe Autoren sind Metadaten, keine Read-Receipt-Actor.

## Abgrenzung
- Zu Signatur:
  - Read-Receipt-Actor ist nicht automatisch Signatur-Actor.
  - Elektronische Signatur, Re-Auth, Signaturniveau und rechtliche Signaturbewertung bleiben außerhalb dieser ADR.
  - Ein späterer Flow darf beide Identitäten nur dann gleichsetzen, wenn der Use Case dies explizit und nachvollziehbar bestimmt.
- Zu Workflow-Owner:
  - Workflow-Owner oder Dokument-Owner ist nicht automatisch Actor der Kenntnisnahme.
  - Owner kann Berechtigung oder Verantwortlichkeit erklären, aber nicht die ausgeführte Lesebestätigung eines Users ersetzen.
- Zu Rollen/QMB:
  - Admin/QMB/User, `is_qmb` und Modulrollen entscheiden Berechtigung oder Stellvertretungsfähigkeit, nicht Actor-Identität.
  - QMB/Admin-Rechte können eine stellvertretende Handlung erlauben; der Actor bleibt dann der stellvertretend handelnde Admin/QMB, nicht der Zieluser.
- Zu UserContext:
  - UserContext liefert die Identitätsbasis für den ausführenden User.
  - UserContext ist nicht selbst das Nachweisniveau und nicht die Rollenentscheidung.
- Zu RequestContext:
  - RequestContext liefert technische Herkunft, Correlation/Causation, Clienttyp und ggf. Session-/Request-Bezug.
  - RequestContext ersetzt keinen Actor, macht aber die Actor-Quelle nachvollziehbarer.
- Zu Audit-Export / Nachweispaket:
  - Export/Nachweispaket muss Actor, Target/Zieluser, Actor-Quelle und Nachweisstatus getrennt sichtbar machen.
  - Ein Receipt ohne belastbare Actor-Quelle darf nicht als voll belastbare Kenntnisnahme erscheinen.

## Umgang mit aktuellem Zustand

| AP-009-Fundtyp | aktueller Zustand | Zielrichtung | spätere Behandlung | benötigte Vorentscheidung |
| --- | --- | --- | --- | --- |
| Read-Tracking-/Receipt-Events ohne Actor | `PdfReadTrackingService.start` und `finalize` publizieren `read.session.*` ohne `actor_user_id`; Receipt enthält `session.user_id`. | Für Nachweis-Events Actor/Target semantisch trennen; ausführenden User aus freigegebenem Kontext bestimmen. | Read-Receipt-Service-Actor-Implementierungsvorbereitung. | Ist `session.user_id` bei Selbst-Kenntnisnahme zugleich Actor, und wie wird Stellvertretung abgebildet? |
| Direkter Confirm-Flow mit `actor_user_id=user_id` | `confirm_released_document_read` publiziert `domain.documents.read.confirmed.v1` mit `actor_user_id=user_id`. | Nur belastbar, wenn `user_id` aus freigegebenem Kontext als ausführender User stammt. | Quelle/Status klassifizieren; keine Änderung in AP-010. | Übergangsstatus des bestehenden Direct-Confirm-Flows. |
| Documents-Fallbacks auf Owner/`system` | Workflow-/Artefakt-Fallbacks existieren in anderen Documents-Flows. | Nicht auf Read Receipt übertragen; Owner/System nur nach eigener Policy. | Documents-Event-Actor-Matrix. | Systemmarkierungen und Owner-Fallback-Policy. |
| Freie oder optionale Actor-Strings | Audit-/Event-Actor-Qualität hängt teils von Aufrufern ab. | Für Read Receipts keine freie Actor-Quelle als belastbar akzeptieren. | Exportstatus `belastbar/eingeschränkt/legacy` sichtbar machen. | Actor-Quellenvokabular und Feldmodell. |
| Kommentar-/DOCX-Sync-Events ohne belastbaren Event-Actor | Kommentar-/Sync-Autoren können Payload-/Metadaten sein. | Nicht als Read-Receipt-Actor werten. | Separate Documents-Event-Actor-Matrix. | Import-/Kommentar-Autor im Nachweispaket. |
| DOCX->PDF-Erzeugung mit Fallback-Actor | Technische Artefakterzeugung kann interaktiv oder systemnah sein. | Nicht mit Kenntnisnahme vermischen; ggf. über Causation an fachlichen Auslöser koppeln. | Documents-Event-Actor-Matrix. | System-/Service-Actor für technische Folgeevents. |
| Tests mit Fake-Usern und Statuswerten | Tests nutzen `user`, `admin`, `u1` und direkte Progress-/Receipt-Werte. | Testdaten nicht als Produktiv-Actor-Quelle werten. | Tests-/Smoke-Gate-Konzept für Lesebestätigung. | Welche Tests produktnahe Audit-Anforderungen prüfen sollen. |

## Nicht-Ziele
- Keine Documents-Implementierung.
- Keine Read-Receipt-Implementierung.
- Keine Audit-Implementierung.
- Keine UserContext-, Auth-, Rollen- oder RequestContext-Implementierung.
- Keine API-Änderung, kein DTO, kein Contract, kein Re-Export und keine Wrapper-API.
- Keine Event-Schema-Änderung.
- Keine Backend-Feature-Route.
- Keine Migration.
- Keine Dependency-Änderung.
- Keine Bereinigung bestehender AP-002- bis AP-009-Findings.
- Keine Entscheidung über elektronische Signatur oder rechtliches Signaturniveau.
- Keine vollständige Audit-Export-Spezifikation.
- Keine Entscheidung, dass Admin/QMB stellvertretende Kenntnisnahme produktiv nutzen darf.

## Konsequenzen
- Für Documents-Service-Grenzen:
  - Read-Receipt-Use-Cases brauchen langfristig eine explizite Actor-/Target-Semantik an der Servicegrenze.
  - Services bleiben Ort der fachlichen Entscheidung, ob ein Vorgang Nachweischarakter hat.
- Für Audit-Export / Nachweispaket:
  - Actor, Zieluser, Quelle und Nachweisstatus müssen getrennt sichtbar sein.
  - Read Receipts ohne belastbare Actor-Quelle dürfen nur eingeschränkt oder legacy ausgewiesen werden.
  - Correlation/Causation bleiben empfohlen, besonders für Read-Session-Start, Dwell-Tracking und Completion.
- Für GUI/CLI:
  - GUI/CLI dürfen Lesestatus anzeigen, PDF-Viewer öffnen und Kontext transportieren.
  - GUI-/CLI-Zustand ist keine finale Actor-Quelle.
- Für Backend:
  - Backend darf Read-Receipt-Actor nicht fachlich bestimmen.
  - Backend-migrierte Read-Receipt-Use-Cases brauchen freigegebenen UserContext/Request-Kontext zur Servicegrenze.
- Für Tests:
  - Spätere Tests sollten Selbst-Kenntnisnahme, Anzeige ohne Actor-Ereignis, unvollständige Session, Legacy/Import und ggf. Stellvertretung getrennt prüfen.
  - Bestehende Tests werden durch AP-010 nicht geändert.
- Für spätere Implementierungspakete:
  - Maximal drei Folgepakete werden vorbereitet, aber nicht gestartet:
    - Read-Receipt-Service-Actor-Implementierungsvorbereitung.
    - Documents-Event-Actor-Matrix.
    - Tests-/Smoke-Gate-Konzept für Lesebestätigung.

## Risiken
- Technische Risiken:
  - Aktuelle Read-Tracking-Events tragen keinen Event-Actor.
  - Es gibt parallele Read-Pfade: direkter Confirm-Flow und getrackter PDF-Read-Flow.
  - Actor-/Target-Trennung ist in bestehenden Contracts/Events nicht vollständig sichtbar.
  - Correlation/Causation für die Read-Session-Kette ist nicht fachlich verbindlich.
- Fachliche Risiken:
  - Zieluser kann fälschlich als ausführender Actor gelesen werden.
  - Stellvertretende Kenntnisnahme durch Admin/QMB kann Verantwortlichkeiten verfälschen, wenn sie nicht ausdrücklich geregelt ist.
  - Automatische Systemmarkierungen können menschliche Verantwortung verdecken.
  - Reine Statusanzeige kann irrtümlich als auditrelevante Handlung interpretiert werden.
- Migrationsrisiken:
  - Bestehende Desktop-/Training-Flows beziehen den User aus lokaler Session und Adapterzustand.
  - Altbestände mit Read-Status können nicht rückwirkend ohne Markierung belastbar gemacht werden.
  - Backend-Migration darf keinen halb lokalen Read-Receipt-Kontext behalten.
- Audit-/Nachweisrisiken:
  - Nachweispakete könnten Read Receipts belastbarer darstellen, als deren Actor-Quelle erlaubt.
  - Fehlende Actor-Quelle in Events erschwert die Kette vom Öffnen bis zur abgeschlossenen Kenntnisnahme.
  - Unklare System-/Legacy-Markierungen können Auditfragen auslösen.

## Offene Supervisor-Entscheidungen
- Ist stellvertretende Kenntnisnahme durch Admin/QMB fachlich zulässig, und falls ja mit welchem Actor/Target-/Berechtigungsmodell?
- Dürfen automatische System-Markierungen für Kenntnisnahme produktiv vorkommen, oder nur für technische/Legacy-Fälle?
- Wie werden importierte oder historische Lesestände im Nachweispaket konkret gekennzeichnet?
- Ab wann sind `correlation_id` und `causation_id` für Read-Receipt-Nachweisketten Pflicht?
- Welcher Übergangsstatus gilt für bestehende Direct-Confirm-Receipts und getrackte PDF-Receipts?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
  - `docs/AP-004_USER_CONTEXT_ADR.md`
  - `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md`
  - `docs/AP-007_MVP_AUDIT_ACTOR_GAP_MATRIX.md`
  - `docs/AP-008_SERVICE_ACTOR_PARAMETER_MATRIX.md`
  - `docs/AP-009_DOCUMENTS_SERVICE_ACTOR_DEEP_DIVE.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `modules/documents/pdf_read_tracking_service.py`
  - `modules/documents/service.py`
  - `modules/documents/api.py`
  - `modules/documents/contracts.py`
  - `interfaces/pyqt/widgets/pdf_viewer_dialog.py`
  - `interfaces/pyqt/contributions/documents_pool_view.py`
  - `tests/modules/test_documents_pdf_read_tracking.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Existenzprüfung von `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md`.
  - `rg` nach `read_receipt`, `ReadReceipt`, `read.session`, `open_released_document_for_training`, `record_page_dwell`, `finalize`, `get_read_receipt`, `actor_user_id` und `actor_role`.
  - `rg` in `modules/documents/api.py` nach `DocumentsReadApi`, `start_tracked_pdf_read`, `confirm_released_document_read`, `get_read_receipt`, `finalize_tracked_pdf_read` und `open_released_document_for_training`.
  - `rg` in `interfaces/*` nach Read-Receipt-/PDF-Viewer-Aufrufen.
  - `rg` in `tests/*` nach Read-Receipt-/Read-Confirmed-Fällen.
- Keine Testsuite ausgeführt, weil AP-010 ein ADR-/Dokumentationspaket ist und die Vorgabe Tests ausdrücklich ausschließt.
- Keine Linter oder Typechecker ausgeführt, weil AP-010 ein ADR-/Dokumentationspaket ist und keine erfundenen Tools ausgeführt werden sollen.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Event-Schema-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-010_DOCUMENTS_READ_RECEIPT_ACTOR_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll als nächstes ein reines Analysepaket `Documents-Event-Actor-Matrix` freigeben oder zurückstellen; keine Implementierung automatisch starten.
