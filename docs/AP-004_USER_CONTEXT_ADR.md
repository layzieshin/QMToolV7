# AP-004 UserContext ADR

## Status
- Typ: ADR / Entscheidung
- Implementierung: nein
- Cleanup: nein
- API-Änderung: nein
- Migration: nein

## Kontext
- Bezug auf AP-003: `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` inventarisiert den aktuellen Zustand zu `current_user.json`, `get_current_user()`, lokaler `users.db`, Rollen-/QMB-/Admin-Verwendungen und Audit-Actor-Quellen.
- Aktuelle Risiken aus AP-003:
  - Current User wird lokal über `storage/platform/session/current_user.json` persistiert.
  - Viele Adapter und einzelne Services ermitteln den User implizit über `get_current_user()`.
  - `users.db` ist aktuell eine lokale SQLite-Userdatenbank.
  - CLI/PyQt enthalten Rollen-Gates und Rollenmapping, die später nicht fachliche Wahrheit sein dürfen.
  - Audit-Actor wird teils explizit übergeben, teils aus lokalem Current User, Zielusern oder Fallbacks abgeleitet.
- Geltende Architekturregeln:
  - Rollen-/Rechteprüfungen gehören in Services.
  - GUI, CLI und Backend sind Adapter und dürfen keine fachlichen User-/Rollen-/Actor-Entscheidungen treffen.
  - Backend ist Host/Transport-Adapter und darf UserContext später transportieren, nicht fachlich interpretieren.
  - Audit-Actor darf langfristig nicht implizit aus lokalem Current User oder Prozesszustand geraten.
  - Diese ADR ist ein Dokumentations-/Entscheidungspaket; keine Implementierung, keine API-Änderung, keine Migration.

## Begriffe
- **authenticated user**: Die Identität, deren Zugangsdaten oder Session/Token erfolgreich authentifiziert wurden. Das ist die technische Login-Identität, nicht automatisch die fachliche Berechtigungsentscheidung.
- **effective user**: Die fachlich wirksame Benutzeridentität, für die ein Use Case ausgeführt wird. Im Normalfall identisch mit dem authenticated user; Sonderfälle wie Stellvertretung, Serviceausführung oder spätere Delegation bleiben offen und brauchen separate Freigabe.
- **actor**: Die Identität, die für Audit/Nachweis als handelnde Instanz protokolliert wird. Actor ist nicht gleich Rolle und nicht automatisch gleich Current User; die genaue Nachweissemantik gehört in die Audit-Actor-ADR.
- **system actor**: Nicht-menschlicher Actor für systeminitiierte Vorgänge, Jobs, Wartung oder technische Operationen. Zulässige Namen, Nachweisniveau und Grenzen gehören in die Audit-Actor-ADR.
- **session**: Serverseitig oder lokal verwalteter Anmeldezustand, der eine authentifizierte Identität referenziert. Ob langfristig serverseitige Session oder Token verwendet wird, bleibt offen.
- **token**: Transportierbarer Nachweis bzw. Verweis auf eine Authentifizierung. Token-Inhalt, Signatur, Laufzeit und Speicherung sind Nicht-Ziele dieser ADR.
- **request context**: Technischer Kontext einer konkreten Ausführung, z. B. Request-/Command-ID, Correlation-ID, Causation-ID, Clienttyp und Zeitbezug. Er ist vom UserContext getrennt, kann aber zusammen mit ihm an Services übergeben werden.
- **UserContext**: Expliziter, servicegrenzennaher Kontext für die Identität, in deren Namen ein Use Case ausgeführt wird. Er ersetzt langfristig implizite Current-User-Abfragen innerhalb fachlicher Use Cases.

## Entscheidung
Empfohlene Zielentscheidung:

UserContext wird als expliziter, minimaler Identitätskontext an fachliche Services übergeben. Er enthält stabile Identitätsreferenzen und Auth-/Session-Bezüge, aber keine selbstentscheidende Rollenlogik und kein Audit-Nachweisniveau. Services verwenden den UserContext als Eingabe für fachliche Autorisierung; die konkrete Rollen-/QMB-/Befugnissemantik wird in der Rollen-/QMB-Semantik-ADR festgelegt.

Request-Kontext und UserContext bleiben begrifflich getrennt. Ein späteres Implementierungspaket darf sie technisch gemeinsam transportieren, z. B. als Execution-/Call-Kontext, aber diese ADR entscheidet keine konkrete API-Signatur.

Actor bleibt begrifflich getrennt vom UserContext. Der UserContext kann die Identitätsbasis liefern, aus der ein Audit-Actor abgeleitet wird, aber die Actor-Auswahl, System-Fallbacks, Nachweisqualität, elektronische Signatur und Auditpflichten werden an die Audit-Actor-ADR delegiert.

`current_user.json` bleibt nur als aktuelle Legacy-/Desktop-Sessionquelle dokumentiert. Für backend-migrierte Use Cases darf der UserContext nicht still aus dieser Datei oder aus Prozesszustand entstehen. GUI, CLI und Backend dürfen künftig Kontext transportieren und an Services weitergeben; sie dürfen die fachliche Bedeutung von Rollen, QMB-Flag oder Actor nicht entscheiden.

## UserContext-Inhalt

| Feld/Konzept | gehört in UserContext: ja/nein/offen | Begründung | Abgrenzung zu Rollen-ADR oder Audit-ADR |
| --- | --- | --- | --- |
| `user_id` | ja | Stabile technische Identitätsreferenz für den authenticated/effective user. | Rollen-ADR entscheidet nicht die ID, sondern Rechte/Befugnisse dieser Identität. |
| `username` | ja, als Anzeige-/Diagnosefeld | Hilfreich für CLI/PyQt-Anzeige und Diagnose; darf nicht primärer Schlüssel sein. | Nicht als Actor-Nachweisniveau verwenden; Audit-ADR entscheidet protokollierte Darstellung. |
| `display_name` | offen/optional | Nützlich für UI, aber nicht nötig für Autorisierung. | Kann aus Userprofil stammen; keine Rollen- oder Auditentscheidung. |
| Rollen oder Rollenreferenzen | offen, nur als Input-Claims/Referenzen | Services brauchen später Informationen oder Referenzen, um Rollenregeln anzuwenden. UserContext darf Rollen nicht selbst fachlich interpretieren. | Rollen-/QMB-ADR entscheidet Rolle, `is_qmb`, Modulrollen, Befugnisse und Priorität. |
| `tenant` / Organisation | offen | Mehrmandantenfähigkeit und Organisationsmodell sind noch offene Roadmap-Entscheidungen. | Separate Produkt-/Architekturentscheidung vor Mandantenlogik nötig. |
| `organization_unit` / Scope | offen | Kann für spätere Sichtbarkeit/Befugnisse relevant werden, ist aktuell nicht eindeutig als Autorisierungsmodell definiert. | Rollen-/QMB-ADR oder spätere Befugnisse-ADR entscheidet fachliche Wirkung. |
| `session_id` | offen, wahrscheinlich Referenz | Sinnvoll, falls serverseitige Session gewählt wird; nicht entschieden. | Auth-/Session-Entscheidung offen; Token-Implementierung ist Nicht-Ziel. |
| Token-Referenz | offen, alternativ zu `session_id` | Sinnvoll, falls Tokenmodell gewählt wird; UserContext soll keine Token-Secrets enthalten. | Token-Format, Validierung und Laufzeit sind Nicht-Ziele. |
| `actor_id` | offen, nicht als fachliche Entscheidung | Kann als vorab bestimmter Audit-Actor transportiert werden, wenn Audit-ADR das erlaubt. | Audit-Actor-ADR entscheidet Actor-Quelle, Fallbacks und Nachweisniveau. |
| `correlation_id` | nein, gehört in Request Context | Technischer Trace-Kontext, nicht Identität. | Audit-ADR kann Correlation für Nachweis nutzen, aber nicht als UserContext-Feld definieren. |
| `causation_id` | nein, gehört in Request/Event Context | Event-/Command-Verkettung, nicht Useridentität. | Audit-/Event-Konzept entscheidet Verwendung. |
| Source / Clienttyp | nein, gehört in Request Context | `cli`, `pyqt`, `backend`, job oder import sind technische Herkunft, keine Useridentität. | Kann Auditkontext ergänzen; kein Rollenmodell. |
| Timestamp Handling | nein, gehört in Request/Event/Audit Context | Zeitpunkte müssen zentral und konsistent erzeugt werden, aber nicht im UserContext entschieden werden. | Audit-Actor-ADR bzw. Event-Konzept entscheidet Nachweiszeitpunkte. |
| Authentifizierungsstärke | offen | Könnte für sensible Aktionen relevant werden, z. B. Re-Auth oder Signatur. | Elektronische Signatur und Nachweisniveau sind Nicht-Ziele dieser ADR. |

## Schichtenfluss
- CLI:
  - CLI sammelt Eingaben, startet Runtime/Container und kann einen technischen Aufrufkontext bilden.
  - CLI darf Login-Status anzeigen und UX-nahe Blockmeldungen ausgeben.
  - CLI darf Rollen/QMB/Befugnisse nicht fachlich entscheiden; Services müssen die fachliche Autorisierung durchführen.
  - Für spätere backend-migrierte Use Cases darf CLI UserContext nicht aus `current_user.json` als fachliche Wahrheit ableiten.
- PyQt:
  - PyQt sammelt Eingaben, zeigt Benutzer- und Rolleninformationen an und kann Navigations-/Sichtbarkeitsfilter anwenden.
  - PyQt darf UX-Gates nutzen, aber diese ersetzen keine Service-Autorisierung.
  - PyQt übergibt später den expliziten Kontext an den fachlichen Use Case oder an das Backend.
- Backend:
  - Backend authentifiziert oder validiert später den transportierten Auth-/Session-/Token-Bezug nach freigegebener Auth-Entscheidung.
  - Backend erzeugt oder transportiert Request Context und UserContext zur Servicegrenze.
  - Backend interpretiert keine fachlichen Rollen, QMB-Regeln, Befugnisse oder Audit-Actor-Semantik.
- Services:
  - Services erhalten UserContext explizit an der Use-Case-Grenze.
  - Services entscheiden fachliche Autorisierung, Invarianten und Transaktionsgrenzen.
  - Services dürfen Audit-Actor nicht still aus Prozesszustand ableiten; Actor-Behandlung folgt später der Audit-Actor-ADR.
- Repositories/Storage:
  - Repositories/Storage erhalten nur technisch notwendige Persistenzdaten, z. B. `user_id` als gespeichertes Feld.
  - Repositories/Storage treffen keine fachlichen Rollenentscheidungen.
  - Persistenz darf nicht zur impliziten Current-User-Quelle für Use Cases werden.

## Umgang mit aktuellem Zustand

| AP-003-Fundtyp | Zielrichtung | spätere Behandlung | benötigte Vorentscheidung |
| --- | --- | --- | --- |
| `current_user.json` | Nur Legacy-/Desktop-Sessionquelle, nicht langfristiger UserContext für backend-migrierte Use Cases. | Später pro Use Case durch explizite Kontextübergabe kapseln oder ersetzen. | Session vs. Token; Desktop-Übergangsmodell. |
| `get_current_user()` | Nicht als implizite Service-Quelle für fachliche Use Cases verwenden. | Später schrittweise an Use-Case-Grenzen durch expliziten Kontext ersetzen. | Konkrete API-Signaturen und Migrationsschnitt je Use Case. |
| lokale `users.db` | Aktueller lokaler Auth-/User-Store, nicht Zielbild für echten Multiuser-Betrieb. | Spätere Persistenz-/Auth-Migration separat planen. | PostgreSQL/Auth-Store-Zeitpunkt; internes Login vs. externe Identität. |
| implizite Actor-Fallbacks | Nicht als langfristiger Auditnachweis akzeptieren. | In Audit-Actor-ADR festlegen und später gezielt ersetzen oder markieren. | Actor-Nachweisniveau, System-/Unknown-Fallback-Policy. |
| Rollen-Gates in CLI/GUI | Als UX-/Sichtbarkeitsgates tolerierbar, aber keine fachliche Wahrheit. | Später prüfen, ob Service-Gates vollständig vorhanden sind. | Rollen-/QMB-Semantik-ADR; Adapter-Gate-Policy. |
| QMB/Admin-Unschärfen | Nicht in UserContext lösen. | Rollen-/QMB-Semantik-ADR muss Admin, QMB, `is_qmb`, Modulrollen und Befugnisse regeln. | Entscheidung, ob Admin automatisch QMB-Rechte hat. |
| Tests/Legacy-Funde | Dokumentiert, nicht bereinigt. | Test-/Legacy-Policy aus AP-002A beachten. | Testimport-/Legacy-Entscheidung bleibt separat. |

## Nicht-Ziele
- Kein konkretes Rollenmodell.
- Keine QMB/Admin-Semantik.
- Kein Audit-Nachweisniveau.
- Keine elektronische Signatur.
- Keine Token-Implementierung.
- Keine Entscheidung für serverseitige Session oder Token.
- Keine externen Identity Provider.
- Keine PostgreSQL-Migration.
- Keine konkrete API-Signatur.
- Keine DTO-, Contract-, Export- oder Re-Export-Entscheidung.
- Keine Reparatur von `current_user.json`, `get_current_user()`, CLI-/GUI-Gates oder Actor-Fallbacks.

## Konsequenzen
- Für Rollen-/QMB-Semantik-ADR:
  - Muss definieren, welche Rollen-/Befugnisinformationen Services aus UserContext oder nachgelagerten User-/Role-Services nutzen dürfen.
  - Muss `Admin`, `QMB`, `User`, `is_qmb`, Modulrollen und spätere Befugnisse abgrenzen.
  - Muss klären, welche GUI-/CLI-Sichtbarkeitsgates als UX zulässig sind.
- Für Audit-Actor-ADR:
  - Muss entscheiden, wann UserContext-Identität zum Actor wird.
  - Muss System Actor, Unknown-Fallbacks, Zieluser-vs-ausführender-User und Correlation/Causation regeln.
  - Muss festlegen, ob und wie Actor in Events, Auditlog und Nachweispaketen persistiert wird.
- Für spätere Implementierungspakete:
  - Erst nach ADR-Freigaben darf ein kleinstes Vorbereitungspaket entworfen werden, z. B. nur eine Bestands-Schnittkarte für Use-Case-Grenzen.
  - Keine API-Signatur, kein DTO und keine Migration ist durch diese ADR freigegeben.
- Für Backend/Multiuser-Migration:
  - Backend-migrierte Use Cases brauchen expliziten Kontext an der Servicegrenze.
  - Ein Use Case darf nicht halb lokal und halb backendseitig betrieben werden.
  - Lokale Sessiondateien und lokale SQLite-Stores bleiben Übergangsschulden, bis der jeweilige Use Case migriert wird.

## Risiken
- Technische Risiken:
  - Zu breiter UserContext könnte Rollen-, Audit-, Session- und Request-Themen vermischen.
  - Zu schmaler UserContext könnte Services zu Rückgriffen auf impliziten Current User verleiten.
  - Unterschiedliche Übergangspfade für CLI, PyQt und Backend können Doppelwahrheiten erzeugen.
- Fachliche Risiken:
  - QMB/Admin-Semantik bleibt bis AP-005 uneinheitlich.
  - Adapter-Gates könnten fälschlich als fachliche Autorisierung verstanden werden.
  - Organisation/Tenant/Scope bleiben offen und können spätere Berechtigungen beeinflussen.
- Migrationsrisiken:
  - `current_user.json` und lokale `users.db` können in backend-migrierten Use Cases versehentlich weiterverwendet werden.
  - Explizite Kontextübergabe kann viele Use-Case-Grenzen betreffen und muss klein geschnitten werden.
  - Bestehende Tests mit Fake-Usern müssen später nach Testebene eingeordnet werden.
- Audit-/Nachweisrisiken:
  - Actor-Fallbacks wie `system` oder `unknown` sind ohne Audit-ADR nicht belastbar.
  - Zieluser kann heute teilweise als Actor erscheinen; das kann Nachweise verfälschen.
  - Correlation/Causation fehlen als verbindlicher Kontext für spätere Auditketten.

## Offene Supervisor-Entscheidungen
- Soll das Zielmodell serverseitige Session, Token oder eine Zwischenform verwenden?
- Soll ein späterer technischer Gesamtcontainer `UserContext` und `RequestContext` gemeinsam tragen, oder bleiben sie auch technisch getrennte Parameter?
- Welche minimalen Rollenreferenzen dürfen in UserContext enthalten sein, ohne die Rollen-/QMB-ADR vorwegzunehmen?
- Wie wird ein optionaler Tenant-/Organisation-/Scope-Bezug priorisiert?
- Wie werden Desktop-Legacy-Session und backend-migrierte Use Cases während der Übergangszeit strikt getrennt?
- Welche Actor-Felder dürfen vor der Audit-Actor-ADR überhaupt im UserContext vorbereitet werden?

## Ausgeführte Prüfungen
- Gelesene Dateien:
  - `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
- Verwendete Suchmethode/Kommandos:
  - `Glob` zur Prüfung, ob `docs/AP-004_USER_CONTEXT_ADR.md` bereits existiert.
  - Keine zusätzlichen Code-Suchläufe nötig; AP-003 war vorhanden und ausreichend.
- Keine Testsuite ausgeführt, weil AP-004 ein ADR-/Dokumentationspaket ist.
- Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-004_USER_CONTEXT_ADR.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll als nächstes die Rollen-/QMB-Semantik-ADR freigeben oder zurückstellen; keine Implementierung automatisch starten.
