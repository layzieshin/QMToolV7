# AP-006 Audit-Actor ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-003: `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` dokumentiert aktuelle Audit-Actor-Risiken, insbesondere lokale Current-User-Ableitung, Zieluser als Actor, `system`-/`unknown`-Fallbacks und ungeprüfte Actor-Strings.
- Bezug auf AP-004: `docs/AP-004_USER_CONTEXT_ADR.md` entscheidet, dass UserContext Identitätsbasis liefert, aber nicht automatisch den finalen Audit Actor bestimmt.
- Bezug auf AP-005: `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md` trennt Rollen/QMB/Befugnisse von Actor-Semantik; Rollen sind keine Actor-Klassen.
- Aktuelle Audit-Actor-Risiken:
  - `qm_platform/logging/audit_logger.py` schreibt Actor als freien String und validiert die Quelle nicht.
  - `qm_platform/events/event_envelope.py` kennt `actor_user_id`, `correlation_id` und `causation_id`, erzwingt aber keine Actor-Quelle.
  - User-Admin-Events verwenden teils den Zieluser als `actor_user_id`.
  - Incident-Use-Cases leiten den Actor implizit über `get_current_user()` aus dem Usermanagement-Service ab.
  - `LogBackupService` verwendet `actor="system"` als Default.
  - DOCX-Kommentarimport nutzt `"unknown"` als Autor-Fallback; das ist nicht automatisch ein Audit Actor.
- Geltende Architekturregeln:
  - Audit-Actor darf langfristig nicht implizit aus lokalem Current User, Zieluser, Prozesszustand oder GUI/CLI-Entscheidung geraten.
  - Services sind fachliche Grenze für Use Cases, Audit-relevante Entscheidungen und Invarianten.
  - GUI, CLI und Backend dürfen Actor-Kontext transportieren, aber nicht fachlich final bestimmen.
  - Diese ADR ist ein Dokumentations-/Entscheidungspaket; keine Implementierung, keine API-Änderung, keine Migration.

## Begriffe
- **Audit Actor**: Die im Audit-/Nachweiskontext protokollierte handelnde Instanz einer Aktion. Der Audit Actor muss aus einer belastbaren Quelle stammen und darf nicht still aus Zielobjekt, GUI-Zustand oder lokalem Prozesszustand geraten.
- **Ausführender User**: Die menschliche Identität, die eine Aktion ausgelöst oder bestätigt hat. In normalen interaktiven Use Cases ist dies der bevorzugte Audit Actor.
- **Zieluser**: Der Benutzer, der durch eine Aktion betroffen ist, z. B. angelegter Benutzer, geänderter Benutzer oder Empfänger einer Zuweisung. Zieluser ist nicht automatisch Audit Actor.
- **Authenticated user**: Technisch authentifizierte Identität aus Auth-/Session-/Token-Kontext. Sie kann Basis für den Actor sein, ist aber nicht automatisch der endgültige Audit Actor.
- **Effective user**: Fachlich wirksame Identität, in deren Namen ein Use Case ausgeführt wird. Normalerweise identisch mit dem ausführenden User; Delegation/Stellvertretung bleibt offen.
- **System actor**: Explizit benannter nicht-menschlicher Actor für systeminitiierte Vorgänge, Jobs oder Wartung. System actor ist nur zulässig, wenn eine Aktion tatsächlich systeminitiiert ist und keine menschliche Ausführung verschleiert.
- **Unknown actor**: Unbekannte oder nicht belastbare Actor-Quelle. `"unknown"` ist für belastbare Auditnachweise grundsätzlich nicht ausreichend und darf höchstens Legacy-/Import-Metadatum markieren.
- **Service account**: Technische Identität mit bewusst vergebenem Auftrag, z. B. Import-, Job- oder Integrationskonto. Service accounts sind keine Menschen, müssen aber benannt und auditierbar sein.
- **`correlation_id`**: Technische Klammer für zusammengehörige Requests, Commands, Events oder Auditzeilen.
- **`causation_id`**: Verweis auf den auslösenden Vorgang, Command oder Event innerhalb einer Kette.

## Entscheidung
Empfohlene Zielentscheidung:

Der Audit Actor ist die explizit bestimmte handelnde Instanz eines auditrelevanten Use Cases. Für interaktive Use Cases ist der ausführende User aus einem freigegebenen UserContext bzw. späteren Request-Kontext die bevorzugte Quelle. Der Actor darf nicht implizit aus `current_user.json`, lokalem Prozesszustand, GUI-/CLI-Sichtbarkeit, Rollenlogik oder dem Zieluser einer Aktion abgeleitet werden.

Services bilden die fachliche Grenze, an der auditrelevante Entscheidungen getroffen und Actor-Informationen für Events, Auditlog und spätere Nachweispakete festgelegt werden. GUI, CLI und Backend dürfen Actor-Kontext transportieren und anzeigen, aber nicht final fachlich bestimmen. Repositories/Storage speichern Actor-Felder, entscheiden aber keine Actor-Semantik.

System Actor ist zulässig für tatsächlich systeminitiierte Vorgänge, z. B. geplante Jobs, technische Wartung, automatische Lifecycle-Events oder eindeutig technische Backups. System Actor ist kein Ersatz für fehlenden UserContext bei interaktiven Aktionen.

`"unknown"` ist für auditrelevante Aktionen nicht als belastbarer Audit Actor zulässig. `"unknown"` darf nur als Legacy-/Import-Metadatum oder als explizit markierter unvollständiger Altbestand vorkommen, bis eine spätere Cleanup-/Migrationsentscheidung getroffen wird.

Correlation und Causation ergänzen den Audit-/Request-Kontext und sind für spätere Nachweisketten wichtig. Sie ersetzen keinen Actor und gehören nicht in den UserContext.

## Actor-Quellen-Matrix

| Quelle | zulässig: ja/nein/offen | Bedingung | Nachweisqualität | Risiko | spätere Behandlung |
| --- | --- | --- | --- | --- | --- |
| Expliziter UserContext | ja | UserContext stammt aus freigegebenem Auth-/Session-/Request-Kontext und wird an Servicegrenze übergeben. | hoch | UserContext darf Rollen/Audit nicht vermischen. | Zielquelle für interaktive Use Cases. |
| Backend-Request-Kontext | ja/offen | Backend transportiert validierten Auth-/Request-Kontext, interpretiert Actor fachlich nicht selbst. | hoch, wenn Auth/Session geklärt | Noch keine Backend-Feature-Routen/Implementierung. | In späterer Backend-Migration pro Use Case konkretisieren. |
| Lokales `current_user.json` | nein für Zielzustand; Legacy offen | Nur aktueller Desktop-/Legacy-Sessionzustand. | niedrig/mittel | Lokaler Prozesszustand ist nicht multiuser-belastbar. | Später je Use Case kapseln/ersetzen; kein Cleanup in AP-006. |
| `get_current_user()` | nein als implizite Service-Quelle | Als aktueller Bestand bekannt; nicht langfristige Actor-Quelle. | niedrig/mittel | Services können Actor still aus lokaler Session ziehen. | Später durch expliziten Kontext an Use-Case-Grenzen ersetzen. |
| Zieluser einer Aktion | nein als Standard | Zieluser kann als Ziel/Subject dokumentiert werden, aber nicht als Actor. | niedrig, wenn als Actor genutzt | Verfälscht Admin-/QMB-/Userverwaltungsnachweise. | Später in Service-Actor-Parameter-Matrix prüfen. |
| Fallback `"system"` | ja/offen | Nur für tatsächlich systeminitiierte technische Vorgänge. | mittel bis hoch bei klarer Systemquelle | Kann fehlenden UserContext verschleiern. | System-Actor-Policy und Namensschema festlegen. |
| Fallback `"unknown"` | nein für auditrelevante Aktionen | Nur Legacy-/Import-Metadatum oder unvollständiger Altbestand. | niedrig | Nicht auditbelastbar. | Markieren, nicht still reparieren; spätere Policy. |
| CLI/PyQt-Adapterzustand | nein als finale Quelle | Adapter darf Kontext transportieren, UX anzeigen und Eingaben sammeln. | niedrig/mittel | Adapter könnte fachliche Actor-Entscheidung übernehmen. | Services müssen Actor finalisieren. |
| Import-/DOCX-Autor | nein als Audit Actor | Darf als Quellmetadatum gespeichert werden. | niedrig für Audit, mittel für Herkunftsinfo | Autor ist nicht zwingend aktueller handelnder User. | Als Import-Metadatum getrennt halten. |
| Service account | offen/ja | Nur bewusst eingerichtete technische Identität mit Auftrag. | mittel/hoch bei Governance | Kann menschliche Verantwortung verschleiern. | Spätere Service-Account-Policy nötig. |

## System Actor und Unknown-Fallback
- Zulässige System-Actor-Fälle:
  - Automatische technische Jobs ohne direkten menschlichen Auslöser.
  - Runtime-/Lifecycle-Events, sofern sie keine fachliche Useraktion behaupten.
  - Wartungs- oder Backup-Vorgänge, wenn sie wirklich system- oder jobinitiiert sind.
  - Importläufe, wenn ein freigegebener Service account oder expliziter System Actor genutzt wird.
- Unzulässige System-Actor-Verwendungen:
  - Interaktive GUI-/CLI-/Backend-Aktionen mit vorhandenem ausführendem User.
  - Ersatz für fehlende Kontextübergabe in Services.
  - Verschleierung, ob Admin, QMB oder User eine fachliche Aktion ausgelöst hat.
- Umgang mit `"unknown"`:
  - `"unknown"` ist kein belastbarer Audit Actor für neue auditrelevante Aktionen.
  - `"unknown"` kann Legacy-/Import-Metadatum markieren, z. B. fehlenden DOCX-Kommentarautor.
  - `"unknown"` muss in späteren Nachweispaketen sichtbar als unvollständig/unklar gelten, falls es auditrelevant wird.
- Legacy-/Import-Sonderfälle:
  - DOCX-/PDF-/Fremdartefakt-Autoren sind Quellmetadaten, nicht automatisch Audit Actor.
  - Historische Daten dürfen markiert bleiben, bis ein eigenes Migrations-/Bereinigungspaket freigegeben ist.
- Offene Nachweisfragen:
  - Namensschema für System Actor und Service accounts.
  - Mindestnachweis für automatische Jobs.
  - Umgang mit Altbeständen in Audit-Exporten.

## Zieluser vs. ausführender User
- Zielregel:
  - Actor ist grundsätzlich der ausführende User oder ein expliziter System/Service Actor.
  - Zieluser gehört als Target, Subject, affected_user_id oder Payload-/Auditdetail in den Nachweis, nicht als Actor.
  - Bei Selbstregistrierung kann Zieluser und ausführender User identisch sein; diese Gleichheit muss fachlich bestimmt werden, nicht aus dem Objekt abgeleitet.
- Bekannte aktuelle Abweichungen:
  - `modules/usermanagement/user_admin_ops.py` loggt Useranlage mit `actor_user_id=user.user_id`; das kann Zieluser statt ausführender Admin sein.
  - `modules/usermanagement/user_admin_ops.py` loggt QMB-Flag-Änderung mit `actor_user_id=updated.user_id`; das ist der geänderte User.
  - `modules/incident_management/service.py` zieht User implizit über `get_current_user()`.
  - `modules/documents/eventing.py` erhält `actor_user_id` als Parameter und validiert die Quelle nicht.
  - `qm_platform/logging/audit_logger.py` validiert Actor-Quelle nicht.
- Spätere Behandlung:
  - Keine Bereinigung in AP-006.
  - Später Service-Actor-Parameter-Matrix erstellen, die je Use Case Actor, Target und Payload/Subject trennt.
  - Danach kleinste Implementierungsvorbereitung nur nach separater Freigabe.
- Benötigte Vorentscheidungen:
  - Wie Selbstregistrierung, Adminanlage und QMB-Flag-Änderung auditfachlich einzuordnen sind.
  - Ob Service accounts für technische Bootstrap-/Seed-Aktionen erlaubt werden.
  - Welche Felder spätere Nachweispakete für Target/Subject benötigen.

## Correlation und Causation
- Bedeutung:
  - `correlation_id` verbindet zusammengehörige Aufrufe, Events und Auditzeilen.
  - `causation_id` zeigt, welcher Vorgang oder welches Event einen Folgeeintrag ausgelöst hat.
- Abgrenzung zum Actor:
  - Correlation/Causation sind keine Identität und ersetzen keinen Actor.
  - Sie gehören in Request-/Event-/Audit-Kontext, nicht in den UserContext.
  - Sie erklären Ketten, nicht Verantwortlichkeit.
- Spätere Nutzung für Auditketten:
  - Nachweispakete können damit mehrere Ereignisse eines Use Cases bündeln.
  - Automatische Folgeevents können auf den auslösenden Command/Event-Kontext verweisen.
  - Backend- und Service-Grenzen können darüber nachvollziehbarer werden.
- Offene Punkte:
  - Ob jede auditrelevante Aktion zwingend `correlation_id` braucht.
  - Wann `causation_id` Pflicht wird.
  - Wie technische Logeinträge und fachliche Auditzeilen zusammengeführt werden.

## Umgang mit aktuellem Zustand

| AP-003-Fundtyp | Zielrichtung | spätere Behandlung | benötigte Vorentscheidung |
| --- | --- | --- | --- |
| AuditLogger mit freiem Actor-String | Actor-Quelle muss vor Logging service-seitig bestimmt sein. | Später Validierungs-/Kontextgrenze prüfen, keine Änderung in AP-006. | Actor-Feldmodell und Service-Grenze. |
| EventEnvelope `actor_user_id` | Geeignet als Transportfeld, aber Quelle muss belastbar werden. | Später Herkunft aus UserContext/RequestContext absichern. | UserContext-/RequestContext-Implementierungsentscheidung. |
| Useranlage loggt Zieluser als Actor | Zieluser und Actor trennen. | Später in Usermanagement-Actor-Matrix aufnehmen. | Selbstregistrierung vs. Adminanlage vs. Bootstrap. |
| QMB-Flag-Änderung loggt geänderten User als Actor | Ausführenden User als Actor, geänderten User als Target/Subject behandeln. | Später gezielt korrigieren, falls freigegeben. | Nachweisniveau für Rollen-/QMB-Änderungen. |
| Incident-Service zieht Actor aus Current User | Ziel: expliziter Kontext an Servicegrenze. | Später pro Incident-Use-Case vorbereiten. | UserContext- und Backend-Migrationsschnitt. |
| Documents-Events erhalten Actor als Parameter | Grundsätzlich brauchbar, aber Quelle nicht garantiert. | Später Service/API-Grenzen prüfen. | Actor-Parameter-Matrix für Documents. |
| `system`-Fallback bei Log-Backup | Nur zulässig, wenn Backup wirklich system-/jobinitiiert ist. | Später System-Actor-Namensschema festlegen. | System Actor Policy. |
| `unknown` bei DOCX-Kommentarautor | Als Import-/Quellmetadatum einordnen, nicht als Audit Actor. | Später Exportdarstellung klären. | Umgang mit unvollständigen Fremdmetadaten. |

## Abgrenzung
- Zu UserContext:
  - UserContext liefert Identitätsbasis und eventuell Auth-/Session-Bezüge.
  - UserContext ist nicht automatisch der finale Audit Actor.
  - Actor-Auswahl kann UserContext nutzen, muss aber service-/auditfachlich erfolgen.
- Zu Rollen/QMB:
  - Rollen/QMB/Befugnisse entscheiden Berechtigung, nicht Actor-Identität.
  - Admin/QMB/User sind keine Actor-Klassen.
  - Rollenwechsel oder QMB-Flag-Änderungen sind auditrelevante Targets/Subjects.
- Zu Session/Token/Auth:
  - Diese ADR entscheidet kein Session-/Tokenmodell.
  - Authentifizierung ist Voraussetzung, aber nicht vollständige Audit-Actor-Semantik.
- Zu Backend/Multiuser-Migration:
  - Backend transportiert Actor-/Request-Kontext und darf Actor fachlich nicht final bestimmen.
  - Backend-migrierte Use Cases dürfen Actor nicht aus lokaler Desktop-Session ableiten.
  - Keine Backend-Route oder Migration wird durch diese ADR freigegeben.
- Zu elektronischer Signatur:
  - Elektronische Signatur, Re-Auth, Signaturniveau und rechtliches Nachweisniveau bleiben außerhalb dieser ADR.
  - Audit Actor kann Grundlage für Signaturkontext sein, ersetzt diesen aber nicht.

## Nicht-Ziele
- Keine Audit-Actor-Implementierung.
- Keine UserContext-Implementierung.
- Keine Rollenmodell-Implementierung.
- Keine Auth-, Session- oder Token-Implementierung.
- Keine API-Änderung, kein DTO, kein Export, kein Re-Export.
- Keine Backend-Feature-Route.
- Keine Migration.
- Keine elektronische Signatur oder rechtliche Signaturbewertung.
- Keine Reparatur von `actor_user_id`, `system`, `unknown`, `get_current_user()` oder AuditLogger.
- Keine vollständige Audit-Export-Spezifikation.

## Konsequenzen
- Für spätere Audit-Exports/Nachweispakete:
  - Actor, Target/Subject, System Actor, Unknown-Metadaten, Correlation und Causation müssen getrennt ausweisbar sein.
  - Nachweispakete dürfen Zieluser nicht als ausführenden Actor darstellen.
  - Unklare Alt-/Importdaten müssen sichtbar markiert werden.
- Für Service-Autorisierung:
  - Services bestimmen nicht nur Berechtigung, sondern müssen auch auditrelevante Actor-/Target-Semantik liefern.
  - Rollenentscheidung und Actor-Identität bleiben getrennt.
- Für GUI/CLI:
  - GUI/CLI transportieren Kontext und zeigen Auditdaten an.
  - GUI/CLI bestimmen den finalen Actor nicht fachlich.
  - Anzeige von Audit-Actor-Spalten ist keine Actor-Bestimmung.
- Für Backend:
  - Backend transportiert validierten Request-/User-/Actor-Kontext nach freigegebener Auth-Entscheidung.
  - Backend darf `system` oder `unknown` nicht als Ersatz für fehlenden UserContext einsetzen.
- Für Tests:
  - Tests mit Fake-Usern, Actor-Strings oder System-Fallbacks müssen später nach Testebene eingeordnet werden.
  - Legacy-/Importtests nicht automatisch bereinigen.
- Für spätere Implementierungspakete:
  - Erst Service-Actor-Parameter-Matrix erstellen.
  - Danach kleinstes Implementierungsvorbereitungspaket je Use Case, nur nach separater Freigabe.

## Risiken
- Technische Risiken:
  - Freie Actor-Strings können weiterhin inkonsistente Nachweise erzeugen.
  - EventEnvelope und AuditLogger haben aktuell unterschiedliche Actor-Formen (`actor_user_id` vs. `actor`).
  - Correlation/Causation sind vorhanden, aber nicht durchgängig als Nachweiskette erzwungen.
- Fachliche Risiken:
  - Zieluser als Actor kann Admin-/QMB-Aktionen falsch darstellen.
  - System Actor kann menschliche Verantwortung verschleiern.
  - Importautoren können fälschlich als handelnde QM-User interpretiert werden.
- Migrationsrisiken:
  - Explizite Actor-Übergabe kann viele Servicegrenzen betreffen.
  - Backend-migrierte Use Cases dürfen nicht weiter lokale Current-User-Quellen nutzen.
  - Altbestände mit `"unknown"` oder fehlenden Actor-Feldern brauchen klare Exportdarstellung.
- Audit-/Nachweisrisiken:
  - Ohne belastbare Actor-Quelle sind Audit-Exports nur eingeschränkt verwertbar.
  - Unklare System-/Service-Actor-Namen erschweren Verantwortung.
  - Fehlende Causation kann automatische Folgeevents schwer nachvollziehbar machen.

## Offene Supervisor-Entscheidungen
- Welches Mindest-Nachweisniveau braucht ein Audit Actor für MVP-Audit-Exports?
- Welche System-Actor-Namen und Service accounts sind zulässig?
- Wie werden Bootstrap, Seed Admin, Backups und automatische Lifecycle-Events auditfachlich eingeordnet?
- Wie werden Selbstregistrierung, Useranlage, Passwortänderung und QMB-Flag-Änderung zwischen Actor und Target getrennt?
- Darf `"unknown"` in Nachweispaketen erscheinen, und wenn ja mit welcher Kennzeichnung?
- Wann werden `correlation_id` und `causation_id` für auditrelevante Aktionen verpflichtend?
- Welche Alt-/Importdaten gelten als Legacy-Metadaten statt Audit-Actor?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
  - `docs/AP-004_USER_CONTEXT_ADR.md`
  - `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `qm_platform/logging/audit_logger.py`
  - `qm_platform/events/event_envelope.py`
  - `qm_platform/logging/log_backup_service.py`
  - `modules/usermanagement/user_admin_ops.py`
  - `modules/incident_management/service.py`
  - `modules/incident_management/incident_ops.py`
  - `modules/incident_management/assessment_ops.py`
  - `modules/documents/eventing.py`
  - `modules/documents/comment_extractors/docx_comment_reader.py`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Prüfung, ob `docs/AP-006_AUDIT_ACTOR_ADR.md` bereits existiert.
  - Keine zusätzlichen Code-Suchläufe nötig; AP-003/AP-004/AP-005 und gezielte ReadFile-Hotspots waren ausreichend.
- Keine Testsuite ausgeführt, weil AP-006 ein ADR-/Dokumentationspaket ist.
- Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-006_AUDIT_ACTOR_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll als nächstes entscheiden, welches Mindest-Nachweisniveau ein Audit Actor für MVP-Audit-Exports erfüllen muss; keine Implementierung automatisch starten.
