# AP-003 User/Auth Current-State Map

## Status
- Arbeitspaket: AP-003
- Typ: Analyse / Inventar
- Codeänderungen: nein
- Cleanup: nein
- API-Änderungen: nein
- Migration: nein

## Suchmethode
- Verwendete Kommandos / Werkzeuge:
  - `Glob` auf `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` zur Existenzprüfung.
  - `ReadFile` für Roadmap-/Regel-/Vorarbeitsdateien und zentrale Code-Hotspots.
  - `rg`-Suchen nach:
    - `current_user.json`, `SessionStore`, `session_file`, `get_current_user`
    - `users.db`, `users_db_path`, `SQLiteUserRepository`, `authenticate`, `login`, `logout`, `self_register`, `change_password`
    - `is_qmb`, `is_effective_qmb`, `Admin`, `QMB`, `User`, `SystemRole`, `allowed_roles`, `requires_login`, `role`, `permission`
    - `audit_logger`, `emit_audit`, `actor_user_id`, `actor_role`, `EventEnvelope.create`, `"system"`, `"unknown"`
  - Kleine lokale Python-Textanalyse mit `.\.venv\Scripts\python.exe`, nur lesend, zur Rohzählung der Suchtreffer.
- Geprüfte Bereiche:
  - `modules/usermanagement/*`
  - `interfaces/cli/*`
  - `interfaces/pyqt/*`
  - `modules/training/*`
  - `modules/incident_management/*`
  - `modules/documents/*`
  - `src/backend/*`
  - `qm_platform/*`
  - `tests/*`
  - `docs/MASTER_ORCHESTRATION_ROADMAP.md`
  - `AGENTS.md`
  - `.cursor/rules/00-agent-workflow.mdc`
  - `docs/AP-002_PUBLIC_BOUNDARY_VIOLATIONS_INVENTORY.md`
  - `docs/AP-002A_BOUNDARY_EXCEPTIONS_POLICY_ADR.md`
- Ausgeschlossene Bereiche:
  - `modules/incidents/*` existierte im Projekt nicht; stattdessen wurde das vorhandene `modules/incident_management/*` geprüft.
  - Nicht-Python-Dateien wurden nur für Dokumentationskonflikte betrachtet.
- Datum der Analyse: 2026-06-26

## Zusammenfassung
- Rohsuchtreffer in der lokalen Textanalyse: 2118 Trefferzeilen.
- Inventarisierte Kernfunde in den Tabellen: 64.
- Anzahl Kategorie A: 8
- Anzahl Kategorie B: 12
- Anzahl Kategorie C: 14
- Anzahl Kategorie D: 12
- Anzahl Kategorie E: 6
- Anzahl Kategorie F: 5
- Anzahl Kategorie G: 7

Hinweis: Die Rohzählung ist breit und enthält Tests, DTOs, Anzeigezeilen und Mehrfachtreffer. Die Kategorien unten sind kuratierte Kernfundstellen für spätere ADRs, nicht automatisch umzusetzende Aufgaben.

## Kategorie A — Current-User-Datei / lokaler Userzustand

| Datei | Zeile | Fundstelle | Art des lokalen Userzustands | Kurzbewertung | Risiko für Multiuser/UserContext |
| --- | ---: | --- | --- | --- | --- |
| `modules/usermanagement/module.py` | 62 | `session_file=app_home / "storage/platform/session/current_user.json"` | globale lokale Session-Datei unter `QMTOOL_HOME` | Modul-Wiring setzt eine pro Home-Verzeichnis persistierte Current-User-Datei. | hoch |
| `modules/usermanagement/wiring.py` | 37 | `session_file=app_home / "storage/platform/session/current_user.json"` | gleiche Session-Datei im SRP-Wiring-Pfad | Zweiter Wiring-Pfad spiegelt dieselbe lokale Session-Datei. | hoch |
| `modules/usermanagement/session_store.py` | 18 | `def save(self, user: AuthenticatedUser) -> None` | Schreiben lokaler Current-User-Datei | Persistiert `user_id`, `username`, `role` als JSON. | hoch |
| `modules/usermanagement/session_store.py` | 31 | `def clear(self) -> None` | Löschen lokaler Current-User-Datei | Logout entfernt lokale Datei. | mittel |
| `modules/usermanagement/session_store.py` | 37 | `def get_current_user(self) -> AuthenticatedUser | None` | Lesen lokaler Current-User-Datei | Current User wird aus lokaler Datei gelesen und optional per Repository aktualisiert. | hoch |
| `modules/usermanagement/auth_ops.py` | 63 | `self._session.save(user)` | Login schreibt lokalen Userzustand | Login erzeugt pro Prozess/Home lokale Sessionwahrheit. | hoch |
| `modules/usermanagement/auth_ops.py` | 72 | `existing = self._session.get_current_user()` | Logout liest lokalen Userzustand für Actor | Logout-Actor hängt vom bisher gespeicherten lokalen Zustand ab. | mittel |
| `modules/usermanagement/service.py` | 53 | `def get_current_user(self) -> AuthenticatedUser | None` | öffentliche Servicefläche für lokalen Current User | Viele Adapter/Services beziehen UserContext indirekt über diese Methode. | hoch |

## Kategorie B — User/Auth-Service-Flächen

| Datei | Zeile | Funktion/Klasse | Auth-/User-Bezug | Service-/Repository-/Storage-Ebene | Kurzbewertung |
| --- | ---: | --- | --- | --- | --- |
| `modules/usermanagement/auth_ops.py` | 29 | `AuthOps.authenticate` | Credential-Prüfung, Passwortverifikation, aktive User | Service/Ops | Zentrale Authentifizierung; nutzt Repository oder Fallback-Users. |
| `modules/usermanagement/auth_ops.py` | 59 | `AuthOps.login` | Login plus Session-Speicherung | Service/Ops | Authentifiziert und schreibt lokalen Sessionzustand. |
| `modules/usermanagement/auth_ops.py` | 71 | `AuthOps.logout` | Logout plus Session-Löschung | Service/Ops | Löscht lokale Session und publiziert Logout-Event. |
| `modules/usermanagement/auth_ops.py` | 80 | `AuthOps.all_passwords_hashed` | Produktions-/Doctor-Prüfung Passwortspeicher | Service/Ops | Prüft Hash-Status des lokalen Repositories/Fallbacks. |
| `modules/usermanagement/user_admin_ops.py` | 31 | `UserAdminOps.create_user` | Useranlage, Rollenvalidierung | Service/Ops | Validiert Rollenliste `Admin`, `QMB`, `User`; keine Actor-Quelle außer angelegter User. |
| `modules/usermanagement/user_admin_ops.py` | 97 | `UserAdminOps.update_user_admin_fields` | Rolle, Aktivstatus, QMB-Flag | Service/Ops | Zentrale Adminfeld-Änderung für Rolle und `is_qmb`. |
| `modules/usermanagement/user_admin_ops.py` | 151 | `UserAdminOps.set_user_qmb` | QMB-Zusatzrecht | Service/Ops | Publiziert QMB-Flag-Event mit `updated.user_id` als Actor. |
| `modules/usermanagement/user_admin_ops.py` | 168 | `UserAdminOps.self_register` | Selbstregistrierung | Service/Ops | Erstellt inaktive User mit Rolle `User`. |
| `modules/usermanagement/user_admin_ops.py` | 215 | `UserAdminOps.change_password` | Passwortänderung | Service/Ops | Actor wird aus Zieluser bzw. Username abgeleitet. |
| `modules/usermanagement/module.py` | 40 | `users_db_path = Path(...)` | lokale `users.db`-Konfiguration | Module/Wiring | Default `storage/platform/users.db`; relevant für Multiuser-Zentralisierung. |
| `modules/usermanagement/sqlite_repository.py` | 21 | `class SQLiteUserRepository` | SQLite-Userpersistenz | Repository/Storage | Öffnet lokale SQLite-DB, verwaltet User, Rollen, QMB-Flag, Hashes. |
| `interfaces/cli/commands/runtime_commands.py` | 52 | `cmd_init` | Initialisierung von `users_db_path`, Seed Admin | CLI/Runtime-Setup | CLI setzt User-DB-Pfad und seedet Admin über öffentliche API. |

## Kategorie C — Rollen-/QMB-/Admin-Verwendungen

| Datei | Zeile | Fundstelle | Rolle/Berechtigung | Ebene: GUI/CLI/Backend/Service/Repository/Test | Entscheidung oder Anzeige | Kurzbewertung |
| --- | ---: | --- | --- | --- | --- | --- |
| `modules/usermanagement/role_policies.py` | 4 | `normalize_base_role` | Admin/QMB/User-Normalisierung | Service/Policy | Entscheidungshilfe | Zentrale Usermanagement-Rollennormalisierung. |
| `modules/usermanagement/role_policies.py` | 15 | `is_effective_qmb` | QMB oder `is_qmb` | Service/Policy | Entscheidungshilfe | QMB-Semantik: QMB-Rolle oder QMB-Flag. |
| `modules/incident_management/authorization.py` | 31 | `is_admin` | Admin | Service/Policy | fachliche Entscheidung | Incident-Service prüft Admin serverseitig/service-nah. |
| `modules/incident_management/authorization.py` | 35 | `is_qmb` | Admin, QMB, User mit `is_qmb` | Service/Policy | fachliche Entscheidung | Incident-QMB-Semantik weicht von `role_policies.is_effective_qmb` ab: Admin zählt als QMB. |
| `modules/incident_management/authorization.py` | 56 | `require_qmb` | QMB | Service/Policy | fachliche Entscheidung | Service-seitiger Gate für QMB-Aktionen. |
| `modules/incident_management/authorization.py` | 61 | `require_admin_or_qmb` | Admin/QMB | Service/Policy | fachliche Entscheidung | Service-seitiger Gate für Einstellungen/Rollen. |
| `modules/documents/validation.py` | 113 | `ensure_owner_or_privileged` | Owner/Admin/QMB | Service/Validation | fachliche Entscheidung | Dokumentenservice prüft Rollen/Owner explizit über Actor-Parameter. |
| `modules/documents/validation.py` | 131 | `ensure_assignment_update_allowed` | Admin/User/QMB | Service/Validation | fachliche Entscheidung | Zentrale Regeln für Rollenänderungen im Dokumentenworkflow. |
| `interfaces/cli/commands/documents_commands.py` | 22 | `_resolve_current_user_and_role` | Admin/QMB/User und `is_effective_qmb` | CLI | fachliche Rollenabbildung im Adapter | CLI mappt Rolle in `SystemRole`; potenziell ADR-relevant, obwohl Service später nochmal prüft. |
| `interfaces/cli/commands/settings_commands.py` | 24 | `role_map` / `current_role` | Admin/QMB/User | CLI | fachliche Gate-Entscheidung | CLI blockiert Settings-Set für Nicht-QMB/Admin. |
| `interfaces/pyqt/widgets/access_guards.py` | 7 | `require_admin_or_qmb` | Admin/QMB | GUI | fachliche Gate-Entscheidung im Widget-Helfer | GUI-Helfer blockiert Bereiche; Service-Gate muss trotzdem maßgeblich bleiben. |
| `interfaces/pyqt/shell/main_window.py` | 197 | `normalized_role == "ADMIN"` | Admin | GUI/Shell | Navigation/Anzeige | Admin-Debug-Toggle ist Shell-Sichtbarkeit, keine Service-Autorisierung. |
| `interfaces/pyqt/registry/contribution.py` | 26 | `requires_login`, `allowed_roles` | Beitrags-Sichtbarkeit | GUI/Metadata | Anzeige/Navigationsfilter | Navigationssteuerung, darf keine fachliche Autorisierung ersetzen. |
| `interfaces/pyqt/contributions/users_view.py` | 142 | `_require_privileged` | Admin/QMB | GUI | fachliche Gate-Entscheidung im Widget | UI sperrt Benutzerverwaltung; service-seitige Autorisierung ist nicht überall eindeutig aus Code ersichtlich. |

## Kategorie D — Audit-Actor / Actor-Quelle

| Datei | Zeile | Fundstelle | Actor-Quelle | explizit oder implizit | Risiko für Audit-Nachweis |
| --- | ---: | --- | --- | --- | --- |
| `qm_platform/logging/audit_logger.py` | 15 | `emit(self, action: str, actor: str, ...)` | Aufrufer liefert `actor` als String | explizit | mittel: Logger validiert keine UserContext-Quelle. |
| `modules/usermanagement/auth_ops.py` | 55 | `actor_user_id=user.user_id` | authentifizierter User | explizit | niedrig/mittel: Auth-Event Actor ist klar, aber lokal authentifiziert. |
| `modules/usermanagement/auth_ops.py` | 77 | `actor_user_id=existing.user_id if existing else None` | vorheriger lokaler Current User | implizit aus Sessiondatei | mittel: Logout-Actor hängt von lokaler Sessiondatei ab. |
| `modules/usermanagement/user_admin_ops.py` | 51 | `actor_user_id=user.user_id` | neu angelegter User | explizit, aber fachlich fraglich | mittel: Useranlage-Actor ist Zieluser, nicht zwingend ausführender Admin. |
| `modules/usermanagement/user_admin_ops.py` | 164 | `actor_user_id=updated.user_id` | geänderter User | explizit, aber fachlich fraglich | mittel: QMB-Flag-Änderung loggt Zieluser als Actor. |
| `modules/documents/eventing.py` | 11 | `publish_event(... actor_user_id=...)` | Service/API-Parameter | explizit | mittel: Qualität hängt von Adapter-Weitergabe ab. |
| `modules/documents/eventing.py` | 34 | `emit_audit(... actor: str, ...)` | Service liefert Actor-String | explizit | mittel: kein zentraler UserContext erkennbar. |
| `modules/incident_management/service.py` | 53 | `_user()` ruft `get_current_user()` | lokaler Current User aus Usermanagement | implizit | hoch: Service leitet Actor aus lokaler Session statt Request-Kontext ab. |
| `modules/incident_management/incident_ops.py` | 74 | `eventing.emit_audit(... actor=auth.user_id(user))` | Service-User aus `_user()` | implizit aus Current User | hoch: Actor korrekt weitergereicht, aber Quelle ist lokaler Current User. |
| `modules/incident_management/assessment_ops.py` | 122 | `eventing.emit_audit(... actor=auth.user_id(user))` | Service-User aus `_user()` | implizit aus Current User | hoch: Audit abhängig von lokaler Sessionquelle. |
| `qm_platform/logging/log_backup_service.py` | 34 | `actor: str = "system"` | Fallback `"system"` | impliziter Fallback | mittel: Nachweisniveau für Systemaktionen klären. |
| `modules/documents/comment_extractors/docx_comment_reader.py` | 99 | `author_token = ... or "unknown"` | Fallback `"unknown"` für DOCX-Autor | impliziter Fallback | mittel: Kommentar-Autor nicht identisch mit Audit-Actor; Nachweisniveau klären. |

## Kategorie E — Backend-/Multiuser-Risiken

| Datei | Zeile | Fundstelle | Risikoart | betroffener Use Case | Kurzbewertung |
| --- | ---: | --- | --- | --- | --- |
| `src/backend/api.py` | 13 | `create_app()` mit nur `/health` | Noch kein User/Auth-Kontext im Backend | Backend-Basis | Kein direkter Risikozugriff, aber späterer Request-Kontext offen. |
| `modules/usermanagement/module.py` | 62 | `current_user.json` | lokale Sessiondatei | alle aktuellen lokalen User-Flows | Für backend-migrierte Use Cases nicht als Request-Kontext geeignet. |
| `modules/usermanagement/wiring.py` | 15 | `users_db_path` -> `storage/platform/users.db` | lokale SQLite-Userdaten | Auth/Userverwaltung | Multiuser-Zentralisierung braucht spätere ADR/Migration, nicht in AP-003. |
| `modules/incident_management/service.py` | 53 | `_user()` aus `get_current_user()` | Service zieht User implizit aus lokaler Session | Incident/CAPA | Für Backend/Multiuser braucht dieser Use Case später expliziten UserContext. |
| `interfaces/cli/commands/documents_commands.py` | 100 | Current User/Role aus lokaler Session und CLI-Rollenmapping | halb lokaler Kontext | Dokumentenlenkung CLI | Adapter bestimmt Actor/Rolle aus lokaler Datei; für Backend-Slice neu zu klären. |
| `interfaces/pyqt/shell/session_coordinator.py` | 17 | `current_user()` über Usermanagement | GUI-Sitzung liest lokalen Current User | PyQt-GUI | Desktop-tauglich, aber kein Multiuser-Request-Kontext. |

## Kategorie F — Zulässige oder unkritische Funde
- `modules/usermanagement/contracts.py`: DTO `AuthenticatedUser` mit Rollen-/Profilfeldern; reine Modelldefinition ohne IO.
- `interfaces/pyqt/contributions/settings_sections/profile_section.py`: Anzeige von User-ID/Rolle im Profilbereich; primär Darstellung.
- `interfaces/pyqt/presenters/settings_presenter.py`: Darstellung von `Rolle: {user.role}`; keine fachliche Entscheidung.
- `interfaces/pyqt/contributions/audit_logs_view.py`: Anzeige/Filter von Audit-Actor-Spalten; keine Actor-Bestimmung.
- `tests/*`: zahlreiche Fake-User, Rollenmatrizen und Login-Smokes; keine Produktivwirkung, aber Testnähe je Ebene später separat zu bewerten.

## Kategorie G — Supervisor-Entscheidung nötig

| Datei | Zeile | Fundstelle | Grund der Unklarheit | benötigte Entscheidung |
| --- | ---: | --- | --- | --- |
| `modules/usermanagement/role_policies.py` | 15 | `is_effective_qmb` | QMB = Rolle QMB oder `is_qmb`, Admin zählt hier nicht automatisch. | QMB-Semantik gegenüber Incident-Policy vereinheitlichen. |
| `modules/incident_management/authorization.py` | 35 | `is_qmb` | Admin wird als QMB-äquivalent behandelt; User braucht `is_qmb`. | Klären, ob Admin fachlich immer QMB-Rechte hat. |
| `interfaces/cli/commands/documents_commands.py` | 22 | `_resolve_current_user_and_role` | CLI mappt User mit `is_effective_qmb` auf `SystemRole.QMB`. | Klären, ob Adapter-Rollenmapping erlaubt bleibt oder nur Anzeige/Parameterübergabe ist. |
| `interfaces/cli/commands/settings_commands.py` | 42 | `if current_role not in (SystemRole.ADMIN, SystemRole.QMB)` | CLI trifft fachliche Blockentscheidung für Settings. | Klären, welche Adapter-Gates zulässig sind und welche Service-Gates brauchen. |
| `interfaces/pyqt/widgets/access_guards.py` | 7 | `require_admin_or_qmb` | GUI-Helfer trifft Zugriffsgate. | Klären, ob GUI-Gate nur UX-Sichtbarkeit oder fachliche Entscheidung ist. |
| `modules/usermanagement/user_admin_ops.py` | 51 | Useranlage-Event mit `actor_user_id=user.user_id` | Actor scheint Zieluser statt ausführender Admin zu sein. | Audit-Actor-Nachweisniveau und Actor-Quelle für Adminaktionen klären. |
| `interfaces/gui/main.py` | 1 | `LEGACY FROZEN` mit direkten Auth-/Rollen-/Service-Nutzungen | Legacy/Test-Pfad, aber weiterhin mit Current User und Services verbunden. | Legacy-Behandlung aus AP-002A bestätigen. |

## Legacy/Test-Funde
- `interfaces/gui/*`:
  - `interfaces/gui/main.py` nutzt `get_current_user()`, `login()`, `logout()` und direkte Serviceports.
  - Datei ist als `LEGACY FROZEN` markiert; Funde werden nicht ignoriert, aber getrennt von aktiver PyQt-GUI behandelt.
- `tests/*`:
  - Viele Fake-User, Rollenmatrizen, CLI-Login-Smokes und Repository-Tests.
  - Keine Produktivwirkung, aber relevant für spätere Testimport-/UserContext-ADR.
- Historische oder compatibility-nahe Funde:
  - Default-User `admin/admin` in Tests und Dev-/Seed-Pfaden.
  - Legacy-GUI-Sitzungs- und Rollenlogik.

## Dokumentationskonflikte

| Datei | Stelle | Konflikt zur aktuellen Roadmap-/Architekturregel | Empfehlung: markieren, nicht ändern |
| --- | --- | --- | --- |
| `docs/MASTER_ORCHESTRATION_ROADMAP.md` | Risiken / AP-003 | Benennt `current_user.json`, lokale `users.db` und impliziten Actor bereits als Risiken. | Bestätigt AP-003-Befund; keine Änderung. |
| `docs/MODULE_INTEGRATION_POLICY.md` | User accounts / Session file | Dokumentiert `current_user.json` als aktuelle CLI-Sessiondatei. | Kein Konflikt zum Ist-Stand; für UserContext-ADR als Übergangsschuld markieren. |
| `docs/TRAINING_MODULE_SPEC.md` | Usermanagement-Zielzustand | Beschreibt `get_current_user()`/`list_users()` als aktuell und ein späteres Read-API als Ziel. | Nicht ändern; als Hinweis für spätere UserContext-/Read-API-ADR nutzen. |

## Kritischste Funde
1. `modules/usermanagement/session_store.py:18-50`: Current User wird lokal als JSON-Datei gelesen/geschrieben.
2. `modules/usermanagement/module.py:62` und `modules/usermanagement/wiring.py:37`: feste Sessiondatei `storage/platform/session/current_user.json`.
3. `modules/usermanagement/module.py:40-44` / `wiring.py:15-20`: lokale `users.db` über `SQLiteUserRepository`.
4. `modules/incident_management/service.py:53-59`: Service zieht User implizit über `get_current_user()`.
5. `interfaces/cli/commands/documents_commands.py:22-30`: CLI mappt lokalen User/Rolle inklusive QMB-Flag auf `SystemRole`.
6. `interfaces/cli/commands/settings_commands.py:42-44`: CLI blockiert Settings-Änderung nach Rolle.
7. `interfaces/pyqt/widgets/access_guards.py:7-14`: GUI-Helfer blockiert Admin/QMB-Bereiche.
8. `modules/incident_management/authorization.py:35-42`: QMB-Semantik unterscheidet sich von `modules/usermanagement/role_policies.py`.
9. `modules/usermanagement/user_admin_ops.py:48-52` und `161-165`: User-Admin-Events verwenden Zieluser als Actor.
10. `qm_platform/logging/log_backup_service.py:34`: Audit-Fallback `actor="system"` braucht Nachweisniveau-Entscheidung.

## Offene Supervisor-Entscheidungen
- Wie soll der zukünftige explizite UserContext die lokale `current_user.json` ablösen oder kapseln?
- Ist `current_user.json` nur Desktop-/Legacy-Sessionzustand oder auch Übergangsquelle für backend-migrierte Use Cases?
- Wie wird `users.db` im Multiuser-Zielbild behandelt, solange PostgreSQL/zentraler Auth-Store offen ist?
- Soll Admin fachlich automatisch QMB-Rechte haben?
- Wie ist `is_qmb` gegenüber Rolle `QMB` und Modulrollen zu gewichten?
- Welche GUI-/CLI-Rollengates sind reine UX-Sichtbarkeit und welche sind unzulässige fachliche Entscheidungen?
- Welche Actor-Quelle gilt für Adminaktionen: Zieluser, ausführender User, System oder expliziter Request-Kontext?
- Welche System-/Unknown-Fallbacks sind auditierbar akzeptabel?
- Wie werden Legacy-GUI-Funde behandelt?
- Welche Test-Fakes und Rollenmatrizen bleiben Whitebox-Testbestand?

## Auswirkungen auf spätere ADRs
- UserContext-ADR:
  - Muss klären, wie `current_user.json`, `get_current_user()`, CLI/PyQt-Sitzung und Backend-Request-Kontext zusammenhängen.
  - Muss entscheiden, ob Services User explizit erhalten oder weiterhin Usermanagement abfragen dürfen.
- Rollen-/QMB-Semantik-ADR:
  - Muss Admin/QMB/User, `is_qmb`, Modulrollen wie `Leitung`, Adapter-Sichtbarkeit und Service-Autorisierung vereinheitlichen.
  - Muss definieren, welche Rolle in APIs/Events/Audit persistiert wird.
- Audit-Actor-ADR:
  - Muss Actor-Quelle, System-Fallbacks, Unknown-Fallbacks, Adminaktionen und EventEnvelope-Actor verbindlich regeln.
  - Muss klären, ob Actor aus lokalem Current User, explizitem UserContext oder Request-Kontext kommt.

## Ausgeführte Gates
- Such-/Analysekommandos:
  - `Glob` Existenzprüfung für `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` -> Datei existierte nicht.
  - `ReadFile` der Roadmap-/Regel-/Vorarbeitsdateien und zentraler Code-Hotspots -> erfolgreich.
  - Mehrere `rg`-Suchen nach User/Auth/Rollen/Audit-Actor-Mustern -> erfolgreich.
  - Lokale Python-Textanalyse mit `.\.venv\Scripts\python.exe` -> erfolgreich; 2118 breite Rohsuchtreffer.
- Ergebnis:
  - Current-State-Map erstellt.
  - Keine Testsuite ausgeführt, weil AP-003 ein Analyse-/Inventar-Paket ist.
  - Keine Linter oder Typechecker ausgeführt.

## Bestätigung
- Keine Codeänderungen durchgeführt.
- Keine Refactorings durchgeführt.
- Keine API-Änderungen durchgeführt.
- Keine Migrationen durchgeführt.
- Keine Dependency-Änderungen durchgeführt.
- Keine verbotenen Dateien geändert.
- Nur `docs/AP-003_USER_AUTH_CURRENT_STATE_MAP.md` wurde neu angelegt oder geändert.

## Maximal ein sinnvoller nächster Schritt
Supervisor soll entscheiden, ob als nächstes die UserContext-ADR, die Rollen-/QMB-Semantik-ADR oder die Audit-Actor-ADR priorisiert wird; keine ADR und keine Implementierung automatisch starten.
