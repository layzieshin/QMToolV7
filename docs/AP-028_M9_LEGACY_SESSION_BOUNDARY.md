# AP-028 M9 – Legacy-Session-Grenze und Abschluss

## Zweck

M9 schließt AP-028 im vereinbarten Usermanagement-Scope ab. M8 ist in `main`
(`0e25f9f`, PR #17). M9 führt **keinen** produktiven PostgreSQL-Cutover durch und
migriert keine Fachmodule.

Status nach M9:

- **AP-028 scope-complete** (vereinbarter Usermanagement-/Backend-Scope)
- **nicht** „repo release-green“ / produktionsnaher Gesamtstand, solange
  `tests/e2e_cli/test_training_cli.py` fehlschlägt (unabhängiges Folgepaket)

## Finaler Backend-Ausführungspfad

```text
POST /auth/login
  → src.backend.auth_routes.login
  → modules.usermanagement.api.login_backend
  → PostgreSQL users + sessions + audit_events

Bearer-geschützte Requests
  → src.backend.auth_dependencies.require_user_context*
  → modules.usermanagement.api.resolve_session
  → bestätigter UserContext (serverseitig)

POST /auth/logout
  → api.logout_backend

POST /auth/change-password
  → api.change_own_password

POST /auth/logout-all
  → api.revoke_all_own_sessions

POST /users , PATCH /users/{username}/access
  → api.create_user_as_admin / update_user_access_as_admin
```

Quellen der Wahrheit: PostgreSQL-Schema `usermanagement`, opake Session-Tokens
(nur Hash persistiert), Audit in `audit_events`. Kein Lesen von
`current_user.json` und kein Aufruf von `get_current_user()` im Backend.

Absicherung: `tests/interfaces/test_architecture_gates.py`
(`test_backend_uses_only_usermanagement_public_api`,
`test_backend_auth_path_uses_public_resolve_session`).

## Backend-Session vs. Desktop-Legacy-Session

| Aspekt | Backend | Desktop/CLI Legacy |
| --- | --- | --- |
| Speicher | PostgreSQL `sessions` | `storage/platform/session/current_user.json` |
| API | `login_backend` / `resolve_session` / … | `UserManagementService.get_current_user()` |
| Owner-Modul | `session_ops` + PG-Repos | `session_store.SessionStore` |
| Multiuser | ja (parallele Sessions) | nein (Prozess-/Desktop-Zustand) |
| Zulässig für backend-migrierte Actor | ja | **nein** |

`SessionStore` ist ausdrücklich Desktop-/Legacy-Sessionquelle und niemals
Backend-Authentifizierungswahrheit
(`modules/usermanagement/session_store.py`).

## Inventar aktiver `get_current_user()`-Produktionsverbraucher

Jeder Eintrag gilt verbindlich als:

- lokaler Prozess-/Desktop-Zustand;
- keine belastbare Multiuser- oder Backend-Identität;
- keine zulässige Actor-/Rollenquelle für backendmigrierte Use-Cases;
- spätere Migration nur im jeweiligen Fachmodul-Arbeitspaket.

### CLI

| Pfad | Kontext |
| --- | --- |
| `interfaces/cli/commands/users_commands.py` | Users-CLI |
| `interfaces/cli/commands/settings_commands.py` | Settings-CLI |
| `interfaces/cli/commands/documents_commands.py` | Documents-CLI |
| `interfaces/cli/commands/training_commands.py` | Training-CLI |
| `interfaces/cli/commands/incident_management_commands.py` | Incident-CLI |

### PyQt / GUI

| Pfad | Kontext |
| --- | --- |
| `interfaces/pyqt/shell/session_coordinator.py` | Shell-Session |
| `interfaces/pyqt/widgets/access_guards.py` | Zugriffs-Guards |
| `interfaces/pyqt/contributions/home_view.py` | Home |
| `interfaces/pyqt/contributions/users_view.py` | Users |
| `interfaces/pyqt/contributions/settings_view.py` | Settings |
| `interfaces/pyqt/contributions/settings_sections/profile_section.py` | Profil |
| `interfaces/pyqt/contributions/settings_sections/module_settings_section.py` | Modul-Settings |
| `interfaces/pyqt/contributions/settings_sections/workflow_profiles_section.py` | Workflow-Profile |
| `interfaces/pyqt/contributions/settings_sections/signature_settings_section.py` | Signature-Settings |
| `interfaces/pyqt/contributions/documents_pool_view.py` | Documents Pool |
| `interfaces/pyqt/contributions/documents_workflow/core_mixin.py` | Documents Workflow |
| `interfaces/pyqt/contributions/documents_workflow/actions_mixin.py` | Documents Actions |
| `interfaces/pyqt/contributions/documents_workflow/selection_mixin.py` | Documents Selection |
| `interfaces/pyqt/presenters/documents_signature_ops.py` | Documents/Signature Ops |
| `interfaces/pyqt/widgets/signature_sign_wizard.py` | Signature Wizard |
| `interfaces/pyqt/contributions/training_workspace.py` | Training |
| `interfaces/pyqt/contributions/training_sections/user_actions_section.py` | Training User Actions |
| `interfaces/pyqt/contributions/incident_management_sections/base.py` | Incident |
| `interfaces/pyqt/contributions/audit_logs_view.py` | Audit-Logs UI |
| `interfaces/gui/main.py` | Legacy GUI Host |

### Module (Legacy-Aufruf, nicht Backend)

| Pfad | Kontext |
| --- | --- |
| `modules/usermanagement/service.py` | Wrapper auf `SessionStore` |
| `modules/usermanagement/session_store.py` | JSON-Store |
| `modules/usermanagement/auth_ops.py` | Desktop-AuthOps |
| `modules/training/api.py` | Training liest Desktop-User |
| `modules/incident_management/service.py` | optionaler Getter auf UM-Service |

Test-Doubles unter `tests/` sind kein Produktionspfad und hier nicht inventarisiert.

## Nachweisverweise (Sicherheit / Sessions / Audit)

| Thema | Nachweis |
| --- | --- |
| Token nur gehasht | `tests/modules/usermanagement/test_session_ops.py`, M2/M5/M6 |
| Passwort-Policy / Hash | `password_crypto`, `test_password_policy.py`, M5 |
| Session-Widerruf / Passwortwechsel | `docs/AP-028_M6_SESSION_ENFORCEMENT.md`, M6-Tests |
| Auth-Audit | `docs/AP-028_M7_AUDIT_EVIDENCE.md`, M7-Tests |
| Backend-Legacy-Grenze | Architektur-Gates (dieses Dokument § Backend-Pfad) |
| Cutover-Prep / Drill | `docs/AP-028_M8_CUTOVER_PREP.md` (Prep-only, kein Cutover) |

## Statusübersicht M0–M8

| Milestone | Inhalt | Stand |
| --- | --- | --- |
| M0 | Ist-/Zielmatrix | erledigt |
| M1 | Contracts / UserContext | erledigt |
| M2 | Session-Logik | erledigt |
| M3 | PostgreSQL-Schema | erledigt |
| M4 | Repositories | erledigt |
| M5 | Backend-Auth-Foundation | erledigt |
| M6 | Session-Enforcement + Admin-HTTP | erledigt |
| M7 | Audit Evidence | erledigt |
| M8 | Cutover-Prep only (`ready_for_remapping`) | erledigt in `main` (`0e25f9f`) |

Produktiver Cutover und UUID-Remapping der Quermodule sind **Folgepakete außerhalb AP-028**.

## Abschnitt-D-Abschlussmatrix

Statuswerte: `erfüllt` | `vorbereitet_cutover_folgepaket` | `ausserhalb_scope` | `blockiert_unabhaengig`

### Fachlogik

| Punkt | Status |
| --- | --- |
| Mehrere parallele Sessions unterschiedlicher Benutzer | `erfüllt` |
| Jeder Backend-Request eindeutig einer gültigen Session zuordenbar | `erfüllt` |
| Aktiver Benutzer ausschließlich serverseitig bestimmt | `erfüllt` |
| Keine autoritativen Client-`user_id`-/Rollen-Claims | `erfüllt` |
| Deaktivierte Benutzer blockiert; Ablauf und Widerruf | `erfüllt` |
| Login/Logout backendgestützt | `erfüllt` |
| Bestätigter frozen UserContext über öffentliche Grenze | `erfüllt` |
| Usermanagement nur globale Identitätsgrundlagen; Fachautorisierung in Fachmodulen | `erfüllt` |

### Architektur

| Punkt | Status |
| --- | --- |
| Backend ohne Businesslogik und ohne direkte Fach-Repositories | `erfüllt` |
| Öffentliche Grenze `modules/usermanagement/api.py` | `erfüllt` |
| Keine neuen externen Imports auf Modul-Internals (Backend) | `erfüllt` |
| CLI/PyQt keine fachliche Auth-Quelle | `ausserhalb_scope` — gilt nur für noch nicht migrierte Desktop-/CLI-Use-Cases, die weiterhin `get_current_user()` nutzen; Backend-Pfad ist getrennt (siehe Inventar) |
| `current_user.json` keine Backend-Wahrheit | `erfüllt` |
| Keine optionalen Actor-Parameter als Ersatz für bestätigten Kontext | `erfüllt` |
| Systemactor ≠ Useractor | `erfüllt` |

### Persistenz

| Punkt | Status |
| --- | --- |
| Usermanagement produktiv auf PostgreSQL oder technisch cutover-bereit | `vorbereitet_cutover_folgepaket` |
| Versionierte Migrationen; Sessions serverseitig; Token gehasht | `erfüllt` (Runtime-Backend); Desktop-SQLite-Legacy bis Cutover-Folgepaket |
| Stabile User-IDs (SQLite-String-IDs vs. PostgreSQL-UUIDs; Remapping ausstehend) | `vorbereitet_cutover_folgepaket` |
| Soft-Deaktivierung | `erfüllt` |
| Getrennte Migrator-/Runtime-Rechte | `erfüllt` |
| Backup/Restore-Drill (M8) | `vorbereitet_cutover_folgepaket` |
| Datenübernahme / produktiver Import | `ausserhalb_scope` |
| Kein Dual-Write | `erfüllt` |

### Sicherheit

| Punkt | Status |
| --- | --- |
| Verpflichtende Auth-/Session-Negativtests (UM-Scope) | `erfüllt` |
| Globale Aussage „alle Repo-Tests grün“ | `blockiert_unabhaengig` — `tests/e2e_cli/test_training_cli.py` (`TrainingAdminApi.create_category` fehlt) |
| Deaktivierung und Rollenänderungen laut Policy | `erfüllt` |
| Keine Klartextpasswörter/Tokens persistiert oder geloggt | `erfüllt` |
| Auth-Fehler ohne unnötige User-Enumeration | `erfüllt` |

### Audit

| Punkt | Status |
| --- | --- |
| Login/Logout/Session/User-Admin nachvollziehbar | `erfüllt` |
| Actor, Target, Session, Request unterscheidbar | `erfüllt` |
| UTC-Zeitstempel | `erfüllt` |
| Keine stillen Actor-Fallbacks (Backend-/M7-Pfad) | `erfüllt` — Aussage gilt für den backendgestützten Auth-/Audit-Pfad; der lokale Legacy-Desktop-Pfad ist davon nicht uneingeschränkt abgedeckt |

### Migration

| Punkt | Status |
| --- | --- |
| Forward-only Migrationen | `erfüllt` |
| Cutover dokumentiert / Prep | `vorbereitet_cutover_folgepaket` |
| Produktiver Cutover + UUID-Remapping + Quermodul-Datenmigration | `ausserhalb_scope` |
| Documents-/Training-/Incident-Backend-Migration | `ausserhalb_scope` |
| Altbestand gesichert (Foundation-/M8-Gates) | `vorbereitet_cutover_folgepaket` |

### Tests / Dokumentation

| Punkt | Status |
| --- | --- |
| Neue und relevante UM-/Backend-/Architektur-Tests | `erfüllt` |
| Gesamtes `tests/e2e_cli` ohne Ausnahme | `blockiert_unabhaengig` (Training-CLI) |
| Roadmap / Master / M8-/M9-Doku | `erfüllt` (dieses Dokument + Roadmap-Updates) |

## Unabhängiger Fehler (nicht M9)

- Pfad: `tests/e2e_cli/test_training_cli.py`
- Ursache: fehlende `TrainingAdminApi.create_category` (Training-Modul)
- Behandlung: separates Folgepaket; in M9 weder Fix noch Skip/Abschwächung
- CI Windows-Gate listet diesen Test derzeit nicht; dennoch keine Release-green-Behauptung

## Übergabe

AP-028 (vereinbarter Scope) → abgeschlossen nach M9.

Nächster separat freizugebender Schwerpunkt: Documents-Multiuser-MVP.

Außerhalb AP-028: UUID-Remapping, Quermodul-Migration, produktiver UM-PostgreSQL-Cutover,
Training-CLI-Reparatur.
