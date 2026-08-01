# AP-028 M5 - Backend-Auth-Grundlage

## Zweck

M5 verbindet den bestehenden FastAPI-Host mit dem bereits integrierten
Usermanagement- und PostgreSQL-Pfad. Nach M5 koennen mehrere Clients getrennte
opake Sessions verwenden, ohne dass das Backend Benutzer, Rollen oder SQL
selbst verwaltet.

M5 ist ein Authentifizierungs- und Transportpaket. Es ist noch kein
Documents-Multiuser-Paket.

## Ausgangslage und verbindliche Leitplanken

- M1 bis M4 sind in `main` integriert.
- `UserManagementService` verwendet bei expliziter Backend-Komposition
  `PostgresUserRepository` und `PostgresSessionRepository`.
- Der Backend-Prozess darf PostgreSQL nur ueber die Runtime-LOGIN-Rolle
  `qmtool_runtime` verwenden.
- `qmtool_migrator` wird vom Backend nicht verwendet.
- PostgreSQL-Provisioning und Migration muessen vor dem Backend-Start durch
  den vorgesehenen Betriebsablauf erfolgt sein. M5 fuehrt keine Migration mit
  Runtime-Rechten aus.
- Der Klartext-Token wird nur bei Login ausgegeben. In PostgreSQL bleibt nur
  `token_hash`.
- Rollen und `is_qmb` kommen bei jeder Sessionaufloesung aus dem aktuellen
  User-Datensatz.
- Der Desktop bleibt auf seinem bestehenden SQLite-/Legacy-Pfad. Es gibt
  keinen Dual-Write und keinen automatischen Wechsel durch einen zufaelligen
  Umgebungswert.

## Zielausfuehrungspfad

```text
HTTP request
  -> src/backend middleware/dependency
    -> modules.usermanagement.api
      -> UserManagementService
        -> AuthOps / SessionOps
          -> PostgreSQL repositories
```

`src/backend` darf keine Repository-, SQL-, Service- oder internen
Usermanagement-Imports enthalten. Der Zugriff auf fachliche Aktionen erfolgt
ueber die oeffentliche Modulgrenze `modules/usermanagement/api.py`.

## Konfiguration und Bootstrap

### DSN

Der Backend-Composition-Root liest bevorzugt `QMTOOL_PG_DSN`. Alternativ
werden die vollstaendigen Variablen
`QMTOOL_PG_HOST`, `QMTOOL_PG_PORT`, `QMTOOL_PG_DATABASE`,
`QMTOOL_PG_USER` und `QMTOOL_PG_PASSWORD` zusammengesetzt.

Fuer lokale Entwicklung darf die bereits vorhandene `.env` geladen werden.
Die Datei bleibt gitignored. In produktionsnahen Umgebungen kommen die Werte
aus echten Prozessumgebungsvariablen oder einem Secret-Management. Ein
unvollstaendiger DSN, ein fehlendes Passwort oder ein nicht erreichbares
PostgreSQL fuehrt zu einem fail-closed Backend-Start; es gibt keinen
SQLite-Fallback.

### Schlanker Backend-Bootstrap

Der Backend-Host bekommt einen eigenen Composition-Root. Er registriert:

- `logger`, `audit_logger`, `event_bus`, `settings_service`
- die bestehende Lizenz-/Runtime-Infrastruktur gemaess Projektkonvention
- `app_home` und `resource_root`
- `usermanagement_postgres_dsn`

Danach wird nur der fuer M5 erforderliche Usermanagement-Backend-Kontext
verdrahtet. Der komplette Desktop-Core mit Documents, Training, Registry und
Incidents wird nicht als Nebenwirkung des Auth-Smokes gestartet.

Der Bootstrap prueft vor dem Annehmen von Auth-Anfragen mindestens:

- DSN ist vollstaendig vorhanden
- Runtime-LOGIN erfuellt den M4-Rollenvertrag
- Schema ist erreichbar: History-Praefix (Version/Name/Checksumme),
  Zielversion, Schema-Fingerprint und Tabellen-/Privilegienvertraege
  (kein Migrations-Apply mit Runtime-Rechten)
- `seed_mode=hardened` (kein automatisches `admin/admin`)
- leere User-Tabelle: Ersteinrichtung nur mit beiden Variablen
  `QMTOOL_BOOTSTRAP_ADMIN_USERNAME` und `QMTOOL_BOOTSTRAP_ADMIN_PASSWORD`
  (niemals `admin`/`admin`; Passwort unterliegt der zentralen Policy).
  Sind bereits Benutzer vorhanden, werden Bootstrap-Variablen ignoriert.
  Nach einem vollstaendigen User-Verlust ist derselbe Mechanismus erneut
  anwendbar (kein separater One-Shot-Marker).
- `QMTOOL_LICENSE_MODE` ist explizit gesetzt; `dev`/`auto` sind bei
  `QMTOOL_RUNTIME_PROFILE=production` verboten; ungueltige Nicht-Dev-
  Lizenzen brechen den Start ab
- Passwortpolicy zentral im Usermanagement (Standard: min. 10 Zeichen,
  keine Pflicht-Zeichenklassen; technische Untergrenze 8)

Der Backend-Host verwendet weiterhin `create_app(...)` als App-Factory. Tests
koennen einen vorbereiteten Container injizieren; der Healthcheck bleibt ohne
Auth-Konfiguration testbar.

## Oeffentliche Usermanagement-Fassade

`modules/usermanagement/api.py` wird nur um die notwendigen Use-Case-Funktionen
erweitert. Keine Repositories und keine internen Serviceklassen werden
exportiert. Das geplante Minimum ist:

- Credentials authentifizieren
- opake Session aus einem erfolgreich authentifizierten User ausstellen
- Session mit `request_id` aufloesen
- Session widerrufen
- Passwort des aus dem bestaetigten Context stammenden Users aendern

Die Fassaden delegieren an den bestehenden Service. Die Session-Policy bleibt
in `SessionOps`; die API-Datei entscheidet keine Rollen und baut keine SQL-
Anweisungen.

## HTTP-Vertrag

### `POST /auth/login`

Request: `username`, `password`.

Verhalten:

1. Credentials an Usermanagement uebergeben.
2. Bei Erfolg eine Session mit `client_type="backend"` ausstellen.
3. JSON-Antwort mit genau dem Feld `token` (Klartext, einmalig). Keine Rollen,
   kein `user_id`, keine Hashes, keine DB-Details.
4. Keine Passwort-Hashes, internen Rollenobjekte oder DB-Details ausgeben.

Ungueltige Credentials und inaktive Benutzer werden gleichartig als `401`
beantwortet. Ein User mit `must_change_password` erhaelt den Token fuer den
dedizierten Passwortwechselpfad; normale geschuetzte Aufrufe werden danach
mit einem stabilen `409 password_change_required` abgewiesen.

### `GET /auth/me`

Erfordert `Authorization: Bearer <token>`.

Der Host ruft `resolve_session` mit der serverseitig bestimmten Request-ID
auf. `password_change_allowed` bleibt hier immer `False`. Die Antwort enthaelt
nur den aus der Sessionaufloesung stammenden UserContext:

- `user_id`
- `session_id`
- `request_id`
- `username`
- `global_roles`
- `is_qmb`
- `authenticated_at`

Clientfelder fuer `user_id`, Rollen oder QMB werden weder gelesen noch
uebernommen.

### `POST /auth/logout`

Erfordert einen Bearer-Token und widerruft genau die zugehoerige Session.
Weder eine fremde `session_id` noch eine fremde `user_id` wird aus dem Request
akzeptiert. Ein gueltiger Token wird mit `204` beantwortet; ein bereits
widerrufener, aber syntaktisch gueltiger Token bleibt idempotent `204`. Ein
fehlender, syntaktisch ungueltiger oder unbekannter Token wird als `401`
beantwortet.

### `POST /auth/change-password`

Erfordert einen Bearer-Token und nur `new_password` im Body (kein
`current_password` in M5: Authentitaet kommt ausschliesslich aus dem gueltigen
Bearer-Token / bestaetigten Context). Der Zielbenutzer wird ausschliesslich
aus dem bestaetigten `UserContext` genommen.

Nur diese Route darf intern `resolve_session(...,
password_change_allowed=True)` verwenden. Der Parameter darf nicht aus Query,
Body oder Header kommen und wird von `/auth/me`, Logout und jeder kuenftigen
Fachroute niemals gesetzt.

Die M5-Passwortwechsel-Session-Policy ist Supervisor-freigegeben (2026-08-01):

- Der aktuelle Session-Token bleibt nach erfolgreichem Passwortwechsel gueltig.
- `must_change_password` wird entfernt.
- Das Widerrufen aller anderen Sessions des Users folgt erst in M6 und wird in
  M5 nicht vorweggenommen.

Diese Policy wird explizit getestet.

## Request-ID und Fehler

- Jede Anfrage erhaelt eine serverseitige Request-ID.
- Ein gueltiger, begrenzter `X-Request-ID`-Wert darf fuer Korrelation
  uebernommen werden; fehlt er, wird eine UUID erzeugt.
- Die Response gibt die effektive Request-ID im Antwort-Header zurueck.
- Session-, Credential- und Inaktivitaetsfehler werden ohne interne Details
  in stabile HTTP-Fehlerobjekte uebersetzt.
- SQL-Fehler, DSNs, Hashes und Rollen-/ACL-Details werden nicht an den Client
  geleakt.
- HTTP-Fehlerabbildung bleibt im Backend-Adapter; die fachliche Entscheidung
  bleibt im Usermanagement-Service.

## Vorgesehene Dateigrenzen

| Datei/Bereich | Verantwortung |
| --- | --- |
| `src/backend/api.py` | App-Factory, Router-Zusammenbau, oeffentliche Backend-Grenze |
| `src/backend/auth_routes.py` | HTTP-Modelle und Auth-Routen, keine Fachlogik |
| `src/backend/auth_dependencies.py` | Bearer-Parsing, Request-ID, Context-Dependency |
| `src/backend/bootstrap.py` | Backend-Container, `.env`/Umgebungsvariablen, Runtime-DSN |
| `qm_platform/runtime/backend_bootstrap.py` | Verdrahtung des Usermanagement-Vertrags ohne Import aus `src/backend` auf Modul-Internals |
| `modules/usermanagement/api.py` | minimale oeffentliche Auth-/Session-Fassaden |
| `tests/backend/test_auth_api.py` | HTTP- und Negativvertraege |
| `tests/interfaces/test_architecture_gates.py` | bestehende Boundary-Gates erweitern, falls noetig |

`src/backend/bootstrap.py` ist damit der Backend-Composition-Root. Der
plattformseitige Bootstrap registriert und startet ausschliesslich den
Usermanagement-Vertrag fuer M5. Es darf kein zweiter allgemeiner Container
und kein paralleler Usermanagement-Service entstehen.

## Test- und Abnahmekriterien

1. Health bleibt gruen und die App-Factory bleibt importierbar.
2. Login eines Users liefert einen opaken Token; zwei User erhalten getrennte
   Sessions.
3. `auth/me` liefert nur serverseitig bestimmte Identitaet und Rollen.
4. Fehlender, manipulierter, abgelaufener, widerrufener und fremder Token
   fuehrt nicht zu einem Fachaufruf.
5. Inaktive Benutzer koennen sich nicht anmelden; eine nachtraegliche
   Deaktivierung blockiert Resolve.
6. Logout widerruft die richtige Session.
7. Passwortwechsel funktioniert auch fuer `must_change_password` und nur auf
   der dedizierten Route.
8. Kein Request-Parameter kann `password_change_allowed` aktivieren oder den
   Zielbenutzer austauschen.
9. Keine Response enthaelt Passwort, Passwort-Hash, Token-Hash, DSN oder
   interne PostgreSQL-Fehler.
10. Architektur-Gates finden keine Backend-Imports auf Usermanagement-
    Internals oder Repositories.
11. Backend-Start mit fehlendem/ungueltigem DSN scheitert fail-closed und
    verwendet nicht SQLite.
12. Bestehende Modul-, CLI-, Datenbank- und Go-live-Gates bleiben gruen.

## Nicht-Ziele

- Documents-Routen oder Documents-Multiuser-Verhalten
- vollstaendige Benutzeradministration per REST
- Rollen-/QMB-Policy-Ausbau ueber den vorhandenen UserContext hinaus
- Session-Logout-all und Verwaltung fremder Sessions (M6)
- Audit-Vollausbau und Auth-Audit-Nachweispaket (M7)
- SQLite/PostgreSQL-Cutover, Dual-Write oder Backup/Restore (M8/M9)
- JWT, OAuth/OIDC, SSO, Redis oder externe Identity Provider
- CORS-/Reverse-Proxy-/Produktionsdeployment-Haertung

## Verifikation

```powershell
.\.venv\Scripts\python.exe -m pytest tests/backend/test_auth_api.py -q
.\.venv\Scripts\python.exe -m pytest tests/backend/test_auth_api_postgres_live.py -m postgres -q
.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_architecture_gates.py -q
.\.venv\Scripts\python.exe -m pytest tests/modules/usermanagement -q
.\.venv\Scripts\python.exe -m pytest tests/modules -q
.\.venv\Scripts\python.exe -m src.backend
```

Der Backend-Smoke wird mit kontrolliertem Test-DSN und begrenzter Laufzeit
ausgefuehrt. Ein lokaler `.env`-Test darf niemals als Ersatz fuer den
verbindlichen PostgreSQL-CI-Job dienen.

## Integration

- Umsetzung auf `feature/ap-028-m5-backend-auth` vom aktuellen `main`.
- Ein PR fuer M5; keine Vermischung mit M6 oder Documents.
- Vor Merge: lokale Gates, PostgreSQL-Live-Tests, Windows-Matrix und
  PostgreSQL-CI gruen.
- Erst nach Merge beginnt M6 oder ein separat freigegebenes Documents-
  Arbeitspaket.
