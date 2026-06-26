# AP-006A MVP-Audit-Actor-Nachweisniveau ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-003: `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` inventarisiert die aktuellen Actor-Quellen und Risiken, unter anderem lokale Current-User-Datei, `get_current_user()`, Zieluser als Actor, `system` und `unknown`.
- Bezug auf AP-004: `docs/AP-004_USER_CONTEXT_ADR.md` legt fest, dass UserContext Identitätsbasis liefert, aber nicht automatisch finaler Audit Actor ist.
- Bezug auf AP-005: `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md` trennt Rollen-/QMB-Semantik von Actor-Identität.
- Bezug auf AP-006: `docs/AP-006_AUDIT_ACTOR_ADR.md` definiert Audit Actor als explizit bestimmte handelnde Instanz und trennt ausführenden User, Zieluser, System Actor, `unknown`, Correlation und Causation.
- MVP-Audit-Export-/Nachweispaket-Risiko:
  - Ohne belastbare Actor-Quelle können Audit-Exports Dokumenten-, Schulungs-, CAPA- oder Nachweispaket-Ereignisse nicht ausreichend erklären.
  - Zieluser als Actor kann Admin-/QMB-/Userverwaltungsaktionen falsch darstellen.
  - `unknown` und unmarkierte Legacy-/Import-Metadaten können die Nachweisqualität verwässern.
  - `system` ist nur dann belastbar, wenn die Aktion tatsächlich systeminitiiert und nachvollziehbar ist.
- Geltende Architekturregeln:
  - Audit Actor darf nicht implizit aus lokalem Current User, Zieluser, GUI/CLI-Zustand oder `"unknown"` entstehen.
  - Für interaktive Use Cases ist die Zielquelle der ausdrücklich bestimmte ausführende User aus freigegebenem UserContext/Request-Kontext.
  - Services bleiben fachliche Grenze für auditrelevante Use Cases.
  - Diese ADR ist ein Dokumentations-/Entscheidungspaket; keine Implementierung, keine API-Änderung, keine Migration.

## Entscheidung
Empfohlene Zielentscheidung für das MVP-Mindest-Nachweisniveau:

Für auditrelevante MVP-Use-Cases gilt als Mindestniveau: Der Actor muss identifizierbar, quellenmäßig nachvollziehbar und als ausführender menschlicher User oder als ausdrücklich zulässiger System-/Service Actor klassifiziert sein. Zieluser, Rollen, GUI-/CLI-Zustand, lokale Current-User-Datei, `"unknown"` oder unvalidierte freie Actor-Strings genügen nicht als belastbarer Actor für MVP-Audit-Exports.

MVP-Audit-Exports und Nachweispakete müssen Actor-Qualität sichtbar machen. Jeder auditrelevante Eintrag soll mindestens zwischen `belastbar`, `eingeschränkt` und `legacy` unterscheidbar sein. Einträge mit Zieluser-as-Actor, implizitem `get_current_user()`, lokalem `current_user.json`, `system` ohne klare Systemaktion oder `unknown` dürfen nicht still als voll belastbar erscheinen.

Für neue oder backend-migrierte MVP-Use-Cases ist die Zielquelle ein explizit übergebener UserContext/Request-Kontext an der Servicegrenze. Bestehende Desktop-/Legacy-Funde werden in dieser ADR nicht bereinigt; sie müssen vor einem belastbaren MVP-Audit-Export klassifiziert und entweder markiert, eingeschränkt ausgewiesen oder in separaten späteren Paketen bereinigt werden.

Diese ADR definiert keine DTOs, API-Signaturen, Exportformate oder Implementierung. Sie legt nur das fachliche Mindestniveau für spätere Audit-Export- und Nachweispaket-Planung fest.

## Nachweisniveau-Matrix

| Actor-Quelle | zulässig für MVP: ja/nein/eingeschränkt | Bedingung | Nachweisstatus | Risiko | spätere Behandlung |
| --- | --- | --- | --- | --- | --- |
| Expliziter UserContext | ja | UserContext stammt aus freigegebener Auth-/Session-/Request-Entscheidung und wird an Servicegrenze genutzt. | belastbar | Rollen-/Audit-Semantik darf nicht vermischt werden. | Zielquelle für interaktive MVP-Use-Cases. |
| Request-Kontext nach freigegebener Auth-Entscheidung | ja | Backend/Transport validiert technisch und Services bestimmen auditfachlich. | belastbar | Noch nicht implementiert; keine Backend-Routen freigegeben. | Pro backend-migriertem Use Case konkretisieren. |
| Lokale `current_user.json` | eingeschränkt | Nur bestehender Desktop-/Legacy-Sessionzustand, nicht für backend-migrierte Use Cases. | eingeschränkt/legacy | Lokale Datei ist multiuser- und request-kontextschwach. | Vor Audit-Export markieren oder pro Use Case ersetzen. |
| `get_current_user()` | eingeschränkt | Nur Bestand; nicht als neue implizite Service-Actor-Quelle nutzen. | eingeschränkt | Quelle kann lokale Sessiondatei sein. | In Service-Actor-Matrix erfassen. |
| Zieluser | nein | Zieluser darf Target/Subject sein, nicht Actor-Ersatz. | nicht belastbar, falls als Actor genutzt | Verfälscht ausführende Verantwortung. | Vor belastbarem Export markieren/bereinigen. |
| `"system"` | eingeschränkt/ja | Nur bei tatsächlich systeminitiierter Aktion mit begründbarer technischer Quelle. | belastbar oder eingeschränkt je Kontext | Kann fehlenden UserContext verdecken. | System-Actor-Namensschema und Job-Policy festlegen. |
| `"unknown"` | nein | Höchstens Legacy-/Import-Metadatum. | legacy/nicht belastbar | Kein identifizierbarer Actor. | Sichtbar markieren; nicht still reparieren. |
| DOCX-/Import-Autor | nein als Audit Actor | Darf als Quellmetadatum ausgewiesen werden. | legacy/metadaten | Autor ist nicht zwingend ausführender QM-User. | In Export getrennt als Import-Metadatum führen. |
| Technische Service-/Job-Quelle | eingeschränkt/ja | Nur bewusst benannter Service account/System Actor mit Auftrag. | belastbar bei Governance, sonst eingeschränkt | Unklare Verantwortung. | Service-Account-Policy nachziehen. |
| GUI-/CLI-Adapterzustand | nein | Adapter darf nur transportieren/anzeigen. | nicht belastbar als finale Quelle | Adapter könnte fachliche Actor-Entscheidung übernehmen. | Services müssen Actor-Kontext finalisieren. |

## Mindestfelder für spätere Audit-Exports

| Feld/Konzept | Pflicht für MVP: ja/nein/offen | Zweck | Abgrenzung | offene Punkte |
| --- | --- | --- | --- | --- |
| `actor_id` | ja | Stabile Identifikation des Actors. | Nicht zwingend Username; kann System-/Service-Actor-ID sein. | Format/Quelle später festlegen. |
| `actor_display` | ja | Lesbare Darstellung im Nachweispaket. | Nicht Primärschlüssel und nicht alleinige Identität. | Umgang mit Namensänderungen offen. |
| `actor_type` (`human`/`system`/`service`/`unknown`) | ja | Nachweisqualität und Einordnung sichtbar machen. | Rolle/QMB ist kein Actor Type. | `unknown` nur legacy/nicht belastbar. |
| `actor_source` | ja | Quelle nachvollziehbar machen, z. B. UserContext, RequestContext, LegacySession, SystemJob. | Keine API-Signaturentscheidung. | Benennungskatalog offen. |
| `event_time` | ja | Zeitlicher Nachweis. | Zeitquelle gehört in Event-/Auditkontext, nicht UserContext. | Einheitliche UTC-/Signatur-Regel offen. |
| Action / Use Case | ja | Fachliche Handlung erkennbar machen. | Kein Rollenentscheid. | Namensschema offen. |
| Target entity | ja | Betroffenes Objekt, z. B. Dokument, Incident, User, Schulung. | Target ist nicht Actor. | Mindestfelder je Modul offen. |
| `correlation_id` | offen, empfohlen | Verknüpft zusammengehörige Nachweise. | Ersetzt keinen Actor. | Pflichtgrad für MVP entscheiden. |
| `causation_id` | offen, empfohlen für Folgeevents | Macht Ketten aus Commands/Events nachvollziehbar. | Ersetzt keinen Actor. | Wann Pflicht wird, offen. |
| Source client/system | ja | Herkunft wie CLI, PyQt, Backend, Job oder Import sichtbar machen. | Client ist nicht Actor. | Klassifikationswerte offen. |
| Nachweisstatus | ja | `belastbar`, `eingeschränkt`, `legacy` explizit ausweisen. | Bewertet Actor-/Quellenqualität, nicht fachliche Richtigkeit allein. | Exakte Exportkennzeichnung offen. |
| Rollen-/Berechtigungsstatus | nein/offen | Kann erklärend relevant sein. | Gehört nicht zur Actor-Identität; Rollen-ADR beachten. | Nur falls für Nachweis nötig. |
| Import-/Fremdautor | nein als Actor, offen als Metadatum | Herkunft externer Artefakte sichtbar machen. | Kein Audit Actor. | Darstellung in Nachweispaketen offen. |

## Umgang mit bekannten Funden

| Fundtyp | aktueller Zustand | MVP-Bewertung | spätere Behandlung | benötigte Vorentscheidung |
| --- | --- | --- | --- | --- |
| Useranlage loggt Zieluser als Actor | `actor_user_id=user.user_id` kann Zieluser sein. | nicht belastbar für Adminanlage; bei Selbstregistrierung unklar/eingeschränkt | Vor MVP-Audit-Export klassifizieren und später trennen. | Selbstregistrierung vs. Adminanlage vs. Bootstrap. |
| QMB-Flag-Änderung loggt geänderten User als Actor | `actor_user_id=updated.user_id`. | nicht belastbar als ausführender Actor | Geänderten User als Target/Subject, ausführenden User als Actor planen. | Nachweisniveau für Rollen-/QMB-Änderungen. |
| Incident-Service zieht Actor implizit aus Current User | Service ruft `get_current_user()`. | eingeschränkt/legacy bis expliziter Kontext vorhanden ist | Für MVP-CAPA/Audit-Export markieren oder später Service-Kontext vorbereiten. | UserContext-/RequestContext-Migrationsschnitt. |
| Documents-Events erhalten Actor als Parameter | Parameter kann belastbar sein, Quelle aber nicht garantiert. | eingeschränkt bis Quelle klassifiziert ist | Actor-Parameter-Matrix für Documents erstellen. | Servicegrenze und Actor-Quelle je Workflow-Aktion. |
| Audit Logger validiert Actor-Quelle nicht | Freier Actor-String wird geschrieben. | eingeschränkt; Export muss Quelle/Status separat bewerten | Später Kontext-/Validierungsgrenze planen. | Actor-Feldmodell und Exportstatus. |
| `"system"` in Log-Backup | Default `actor="system"`. | eingeschränkt; belastbar nur bei echter systeminitiierter Aktion | System-Actor-Policy und Namensschema festlegen. | Was gilt als Systemjob vs. Useraktion? |
| `"unknown"` in DOCX-Kommentarimport | Fallback für fehlenden DOCX-Autor. | Legacy-/Import-Metadatum, kein Audit Actor | In Export als Fremdmetadatum markieren. | Umgang mit unvollständigen Fremdartefakten. |

## MVP-Use-Case-Bezug

| MVP-Bereich | relevante Actor-Anforderung | bekannte Risiken | spätere Behandlung |
| --- | --- | --- | --- |
| Dokumentenlenkung | Freigabe, Prüfung, Ablehnung, Archivierung und Rollenänderungen brauchen belastbaren ausführenden Actor. | Actor wird teils als Parameter übergeben; Quelle muss klassifiziert werden. | Documents-Actor-Parameter-Matrix vor belastbarem Export. |
| Lesebestätigung / Kenntnisnahme | Bestätigung muss eindeutig einem ausführenden User zuordenbar sein. | Lokale Session-/Current-User-Quelle wäre für Multiuser unzureichend. | Expliziter UserContext/Request-Kontext für migrierte Use Cases. |
| Schulung, Kompetenz & Befugnisse | Schulungsabschluss, Kompetenznachweis und Befugnisvergabe brauchen Actor und ggf. Target/Subject-Trennung. | Befugnis-/Kompetenzmodell noch offen. | Nach Rollen-/Kompetenzplanung Actor-Anforderungen konkretisieren. |
| Aufgaben- und Fristenmanagement | Aufgabenanlage, Zuweisung, Abschluss und Eskalation brauchen ausführenden Actor und Zielverantwortlichen getrennt. | Aufgabenmodul ist noch nicht detailliert geplant. | Bei MVP-Schnitt zuerst Actor/Target-Semantik definieren. |
| Fehler / Abweichungen / CAPA light | Meldung, Bewertung, Maßnahme, Wirksamkeitsprüfung brauchen belastbaren Actor. | Incident-Service nutzt implizites `get_current_user()`. | Vor Audit-Export mindestens als eingeschränkt markieren; später Service-Kontext vorbereiten. |
| Audit-Export / Nachweispaket | Export muss Actor-Qualität, Quellenstatus, Target und Ketten sichtbar machen. | Freie Actor-Strings, `unknown`, Zieluser-as-Actor und fehlende Correlation/Causation. | Export darf unklare Actor nicht als voll belastbar darstellen. |

Phase-2-Module werden durch diese ADR nicht vorgezogen.

## Nicht-Ziele
- Keine Audit-Implementierung.
- Keine Audit-Export-Implementierung.
- Keine UserContext-Implementierung.
- Keine Auth-, Session- oder Token-Implementierung.
- Keine Rollenmodell-Implementierung.
- Keine API-Änderung, kein DTO, kein Export, kein Re-Export.
- Keine Backend-Feature-Route.
- Keine Migration.
- Keine elektronische Signatur oder rechtliche Signaturbewertung.
- Keine Bereinigung von `current_user.json`, `get_current_user()`, Zieluser-as-Actor, `system`, `unknown` oder AuditLogger.
- Keine vollständige Nachweispaket-Spezifikation.

## Konsequenzen
- Für Audit-Export / Nachweispaket:
  - Actor-Quelle und Nachweisstatus müssen sichtbar werden.
  - Zieluser/Target und Actor müssen getrennt ausgewiesen werden.
  - `unknown` und Import-Autoren dürfen nicht als belastbare Actor erscheinen.
  - `system` muss als System Actor begründet und klassifiziert werden.
- Für Services:
  - Services müssen langfristig die Actor-Semantik an der Use-Case-Grenze liefern oder validieren.
  - Service-Autorisierung und Actor-Nachweis bleiben getrennt, aber beide sind service-nah.
- Für GUI/CLI:
  - GUI/CLI dürfen Actor-Kontext transportieren und anzeigen.
  - GUI/CLI-Zustand ist keine finale Actor-Quelle.
- Für Backend:
  - Backend-migrierte Use Cases benötigen Request-/UserContext als belastbare Quelle.
  - Backend darf keine fachliche Actor-Entscheidung treffen.
- Für Tests:
  - Tests mit Fake-Usern, Actor-Strings oder `system`/`unknown` müssen später nach Produktivnähe eingeordnet werden.
  - Legacy-/Importfälle bleiben markiert, nicht bereinigt.
- Für spätere Implementierungspakete:
  - Erst Audit-Actor-Fundklassifikation für MVP-Use-Cases erstellen.
  - Danach Service-Actor-Parameter-Matrix.
  - Danach kleinstes Implementierungsvorbereitungspaket je Use Case, nur nach separater Freigabe.

## Risiken
- Technische Risiken:
  - Aktuelle Audit- und Eventstrukturen tragen Actor unterschiedlich (`actor` vs. `actor_user_id`).
  - Actor-Quelle ist nicht maschinell validiert.
  - Correlation/Causation sind nicht durchgängig erzwungen.
- Fachliche Risiken:
  - Zieluser als Actor kann Verantwortlichkeiten verfälschen.
  - System Actor ohne Governance kann menschliche Verantwortung verdecken.
  - Import-Autoren können irrtümlich als QM-Akteure gelesen werden.
- Migrationsrisiken:
  - Bestand mit lokaler Session kann nur eingeschränkt exportfähig sein.
  - Backend-Migration darf keine halb lokalen Actor-Quellen behalten.
  - Nachweisstatus für Alt-/Legacy-Einträge muss sichtbar und konsistent sein.
- Audit-/Nachweisrisiken:
  - Ohne Mindestfelder und Nachweisstatus wirken Exporte belastbarer, als sie sind.
  - `unknown` und unklare Systemaktionen können Audit-Fragen auslösen.
  - Fehlende Actor-/Target-Trennung erschwert Nachweispakete.

## Offene Supervisor-Entscheidungen
- Welcher genaue Nachweisstatus-Text soll in späteren Exports verwendet werden: `belastbar/eingeschränkt/legacy` oder andere Begriffe?
- Sind `correlation_id` und `causation_id` für alle MVP-Audit-Export-Einträge Pflicht oder nur empfohlen?
- Welche System Actor und Service accounts sind für MVP zulässig?
- Wie werden Bootstrap, Seed Admin, Backups und automatische Lifecycle-Events im MVP-Export gekennzeichnet?
- Darf ein eingeschränkter Actor-Nachweis für MVP produktiv exportiert werden oder nur mit Warnhinweis?
- Welche MVP-Use-Cases müssen vor einem ersten Nachweispaket zwingend bereinigt werden?
- Wie werden historische/Legacy-Einträge mit `unknown` oder fehlender Quelle im Audit-Export dargestellt?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
  - `docs/AP-004_USER_CONTEXT_ADR.md`
  - `docs/AP-005_ROLES_QMB_SEMANTICS_ADR.md`
  - `docs/AP-006_AUDIT_ACTOR_ADR.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Prüfung, ob `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` bereits existiert.
  - Keine zusätzlichen Code-Suchläufe nötig; AP-003 bis AP-006 und die Regel-/Roadmap-Dateien waren ausreichend.
- Keine Testsuite ausgeführt, weil AP-006A ein ADR-/Dokumentationspaket ist.
- Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-006A_MVP_AUDIT_ACTOR_EVIDENCE_LEVEL_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll als nächstes entscheiden, ob `belastbar/eingeschränkt/legacy` als Nachweisstatus-Vokabular für spätere MVP-Audit-Exports verbindlich verwendet wird; keine Implementierung automatisch starten.
