# AP-028 Usermanagement Backend Sessions Roadmap

Status: freigegebene Roadmap / Planungsartefakt (Dokumentation)
Typ: Implementierungs-Roadmap (Milestones), keine Code-Implementierung in diesem Dokument
Bezug: Übergabeauftrag Backend-gestütztes Usermanagement; ADRs AP-003 bis AP-006/AP-022; AP-027 Database Evolution Foundation
Branch-Ziel: `feature/ap-028-*` je Milestone; dieser Planungs-Commit: `feature/ap-028-usermanagement-roadmap`

---

## A. Zusammenfassung des Arbeitspakets

### Ziel

Eine gültige serverseitige Session bestimmt eindeutig den aktiven Benutzer. Das Backend erzeugt daraus einen bestätigten, unveränderlichen Benutzerkontext. Das Usermanagement verwaltet Identität, Sessions und globale Berechtigungsgrundlagen. Andere Module erhalten keinen frei manipulierbaren Actor und keine vom Client behauptete Rolle. Die fachliche Autorisierung anderer Module bleibt in diesen Modulen. PostgreSQL wird zur zentralen, backendkontrollierten Persistenz für den Scope Usermanagement.

### Scope

Ausschließlich `modules/usermanagement` inklusive der für Backend-Nutzung zwingend notwendigen öffentlichen Verträge und Ports, plus der Transport-Anbindung in `src/backend` ohne Businesslogik:

- Benutzeridentität, Login, Logout
- serverseitige opake Sessions (Token-Hash in DB, kein JWT als Erstlösung)
- Sessionvalidierung, -ablauf, -widerruf
- Benutzeraktivstatus, globale Basisrollen, `is_qmb`
- Erzeugung eines bestätigten UserContext / SystemExecutionContext
- Authentifizierungs- und globale Autorisierungsgrundlagen
- PostgreSQL-Zielmodell Schema `usermanagement`
- Auditierbarkeit von Login-, Logout-, Session- und Benutzerverwaltungsaktionen
- Backend-Auth-Endpunkte über öffentliche Modul-APIs

### Nicht-Ziele

- fachliche Berechtigungsregeln von Documents, Incident, Training usw.
- Owner-/Editor-/Reviewer-/Approver-Logik, Vier-Augen, Freigabe-/Review-Workflow
- vollständige PostgreSQL-Migration aller Module
- vollständige Umstellung der PyQt-Oberfläche
- Redis, OAuth/OIDC/SSO, externe Identity Provider
- Mandantenfähigkeit
- vollständige Kompetenz-/Schulungslogik
- generische Enterprise-RBAC-Plattform
- Cleanup der Incident-Abweichung Admin=QMB (bekannt, außerhalb; wird dokumentiert)

### Architekturprinzipien

- `src/backend` bleibt Transport-/Hostadapter; Businesslogik in Modul-Services.
- Öffentliche Python-Grenze: `modules/usermanagement/api.py` und `src/backend/api.py`.
- Adapter transportieren Identität/Eingaben und dürfen UX-Gates; keine abschließende fachliche Autorisierung.
- Client darf weder `user_id` noch Rolle als autoritative Identität vorgeben.
- Session verweist primär auf `user_id`; aktuelle Rollen/`is_qmb` werden pro Request aus der DB geladen.
- Kein dauerhafter Dual-Write SQLite↔PostgreSQL.
- `current_user.json` ist keine Backend-Wahrheit (Legacy-/Übergangspfad nur für Desktop).
- Systemactor und Useractor sind getrennt; kein stiller `system`-Fallback bei interaktiven Aktionen.
- Admin ≠ QMB (Supervisor-Entscheidung 2026-07-31, bestätigt AP-005 Option B).

### Wichtigste Risiken

- Backend hat heute nur `/health` und keine Runtime-Anbindung.
- PostgreSQL-Unterstützung (Treiber, Evolution-Runner, DB-Rollen) fehlt vollständig; AP-027 ist SQLite-only.
- `user_id` wird heute beim Create mit `username` gesetzt — Cutover muss stabile UUIDs und Referenzintegrität planen.
- Actor in Domain-Events ist teils Zieluser statt Handelnder (AP-006).
- Incident behandelt Admin noch als QMB — Scope-Risiko, wenn Milestones versehentlich dorthin greifen.
- Desktop-Legacy-Session und Backend-Session dürfen nicht still vermischt werden.

---

## B. Abhängigkeitsübersicht

```text
Milestone 0 (Bestandsaufnahme + Sollentscheidungen)
  → Milestone 1 (Öffentliche Identitäts- und Sessionverträge)
    → Milestone 2 (Repositoryunabhängige Sessionlogik)
      → Milestone 3 (PostgreSQL-Fundament + Schema)
        → Milestone 4 (PostgreSQL-Repositories)
          → Milestone 5 (Backend-Auth-Grundlage)
            → Milestone 6 (Aktivstatus, Rollenänderung, Sessionwiderruf)
              → Milestone 7 (Auditnachweis)
                → Milestone 8 (Migrations-/Cutover-Vorbereitung)
                  → Milestone 9 (Legacy-Grenze + Abschluss)
```

Keine parallelen Implementierungs-Milestones. M0 ist dokumentations-/entscheidungsbasiert und muss vor M1 abgeschlossen sein. M3 darf nicht vor M2 beginnen (Sessionlogik muss repositoryunabhängig getestet sein). M5 braucht M1–M4. M8 braucht stabile Repositories und Auth-Pfad.

---

## C. Milestones

### Milestone 0 – Bestandsaufnahme und verbindliche Sollentscheidungen

**Ergebnisartefakt:** [`docs/AP-028_M0_STATE_MATRIX.md`](AP-028_M0_STATE_MATRIX.md) (Ist-/Zielmatrix; einzige Wahrheit für M0).

**Ziel**

Ist- und Zielmatrix für Usermanagement/Auth/Sessions/Backend/Persistenz verbindlich festschreiben. Keine Code-Implementierung.

**Voraussetzungen**

- AP-027 in `main` integriert
- Dieses Roadmap-Dokument und Master-Roadmap-Freigabe für AP-028
- Supervisor-Entscheidung Admin ≠ QMB dokumentiert (AP-005-Nachtrag)

**Scope**

- Aktuelle Usermanagement-API, SessionStore, AuthOps, UserAdminOps, SQLite-Repository, Migrationen
- Backend-Skelett (`GET /health`)
- Bestehende Tests und ADRs AP-003–AP-006, AP-022
- Sollentscheidungen in dieser Roadmap und ggf. knappe ADR-Statusnachträge
- Dokumentation der bekannten Incident-Admin=QMB-Abweichung als Out-of-Scope

**Nicht-Ziele**

- Code-, Schema-, API-, Dependency-Änderungen
- Cleanup in anderen Modulen
- Beginn der Session-/UserContext-Implementierung

**Betroffene Dateien/Bausteine**

- Lesend: `modules/usermanagement/*`, `src/backend/*`, `docs/AP-003_*.md` bis `AP-006*.md`, `AP-022_*.md`, `docs/DATABASE_EVOLUTION_POLICY.md`, Tests unter `tests/modules/test_usermanagement*`
- Schreibend nur Planungsartefakte unter `docs/` (Ist-/Zielmatrix-Nachtrag in diesem Dokument oder schlankes `docs/AP-028_M0_STATE_MATRIX.md` falls nötig)

**Implementierungsaufgaben**

1. Ist-Matrix bestätigen (Session JSON, SQLite users, öffentliche API-Exporte, Actor-Weitergabe).
2. Zielmatrix bestätigen (opake Sessions, UserContext, PostgreSQL Schema `usermanagement`, Backend-Auth-Endpunkte).
3. Offene Restentscheidungen auflisten (Abschnitt E); keine neuen fachlichen Erfindungen.
4. Bekannte Abweichungen und Out-of-Scope-Items explizit markieren.

**Tests**

- Keine neuen Produkt-Tests erforderlich
- Optional: vorhandene Usermanagement-Tests als Baseline grün halten (ohne Codeänderung)

**Test-Gate**

```text
Dokumentierte Ist- und Zielmatrix vorhanden und widerspruchsfrei zu ADRs/Roadmap
Admin ≠ QMB als Supervisor-Entscheidung dokumentiert
Keine Codeänderung in diesem Milestone
Architektur-Gates unverändert grün (falls Suite läuft)
```

**Abnahmekriterien**

- Ausführende KI für M1 kann ohne Repo-Rätsel starten
- Keine unbestätigte Verhaltensänderung
- Escalationspunkte klar getrennt von Annahmen

**Risiken**

- Veraltete Roadmap-Passagen erzeugen Doppeldeutigkeit → Master-Roadmap muss synchron bleiben

**Eskalationskriterien**

- Widerspruch zwischen ADR, Code und diesem Plan, der Verhalten ändern würde
- Wunsch, Documents-Fachautorisierung oder Incident-Cleanup in M0 zu ziehen

**Übergabe an nächsten Milestone**

Freigegebene Ist-/Zielmatrix + Abschnitt E Restoffenheiten → Milestone 1.

---

### Milestone 1 – Öffentliche Identitäts- und Sessionverträge

**Ziel**

Unveränderliche öffentliche Verträge für Session, UserContext, SystemExecutionContext und Fehlerfälle; Export über `modules/usermanagement/api.py`.

**Voraussetzungen**

Milestone 0 abgeschlossen.

**Scope**

- Datentypen (frozen): Session-Metadaten (ohne Klartext-Token), `UserContext` (oder gleichwertiger Name), `SystemExecutionContext`
- Fehlerverträge für ungültige/abgelaufene/widerrufene Session, inaktiven Benutzer, Auth-Fehler
- Öffentliche API-Exporte; keine Persistenz, keine HTTP-Routen

**Nicht-Ziele**

- Repository-Implementierung, Backend-Routen, PostgreSQL, PyQt-Umbau
- Fachautorisierung anderer Module

**Betroffene Dateien/Bausteine**

- `modules/usermanagement/contracts.py` (oder klar benannte Contract-Dateien im Modul)
- `modules/usermanagement/api.py`
- ggf. schmale Fehler-Typen im Modul
- Tests: Contract-/Import-Tests unter `tests/modules/`

**Implementierungsaufgaben**

1. `UserContext` mit mindestens: `user_id`, `session_id`, `request_id`, `username`, globale Rolleninfo, `is_qmb`, `authenticated_at` (UTC); frozen; nicht clientbefüllbar.
2. `SystemExecutionContext` mit explizitem `system_actor` und `request_id`.
3. Session-Contract-Felder gemäß Zielmodell (`session_id`, `user_id`, Zeiten, `revoked_at`, `client_type`, …) — Token nur als Hash-Seite im Persistenzvertrag, Klartext-Token nie im Contract-Persistenzobjekt.
4. Öffentliche Exporte und Docstrings; interne Dateien bleiben nicht-öffentlich.
5. Naming an AP-004 angleichen (`UserContext` bevorzugt).

**Tests**

- Contract-Tests: Immutability, Pflichtfelder, Trennung User vs. System
- Architektur-Gate: keine neuen externen Imports auf Modul-Internals
- Negative: Client-ähnliche Konstruktion darf nicht als „bestätigt“ gelten (Factory nur serverseitig dokumentiert/getestet)

**Test-Gate**

```text
# PowerShell: Shell-Globs wie test_usermanagement*.py werden nicht expandiert;
# pytest erhält sonst ein Literal und findet keine Dateien. Mit FullName auflösen:
.\.venv\Scripts\python.exe -m pytest @((Get-ChildItem -Path tests/modules -Filter 'test_usermanagement*.py').FullName) tests/modules/usermanagement -q
.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_architecture_gates.py -q
Neue Contract-Tests grün
Keine Backend-/Persistenz-Regression
```

**Abnahmekriterien**

- Andere Module können den Typ importieren, ohne Sessionlogik zu erhalten
- Begriffe authenticated/effective/actor/target/system bleiben getrennt dokumentiert

**Risiken**

- Zu breite öffentliche Fläche; nur notwendige Typen exportieren

**Eskalationskriterien**

- Änderung der öffentlichen Modulgrenze über das geplante Export-Set hinaus
- Wunsch nach JWT-Claims im UserContext

**Übergabe**

Stabile Contracts → Milestone 2.

---

### Milestone 2 – Repositoryunabhängige Sessionlogik

**Ziel**

Session erzeugen, Token hashen, auflösen, ablaufen lassen, widerrufen; Aktivstatus prüfen — zunächst mit In-Memory-/Test-Repository.

**Voraussetzungen**

Milestone 1.

**Scope**

- Token-Erzeugung (hohe Entropie), Speicherung nur als Hash
- Resolve-Pfad mit Prüfungen: Token vorhanden/gültig, Session existiert, nicht abgelaufen, nicht widerrufen, Benutzer existiert und aktiv, ggf. `must_change_password`-Policy-Hook (Policy-Details siehe Abschnitt E)
- Logout / Revoke
- Erzeugung von `UserContext` nur nach erfolgreicher Auflösung

**Nicht-Ziele**

- PostgreSQL, HTTP, Audit-Vollausbau, Desktop-JSON als Wahrheit

**Betroffene Dateien/Bausteine**

- `modules/usermanagement/` Session-Service/Ops (Erweiterung bestehender `auth_ops.py` / neuer klarer Owner, kein Parallelpfad)
- Abstract Session-Repository-Port
- In-Memory-Test-Double
- Tests unter `tests/modules/`

**Implementierungsaufgaben**

1. Session-Lifecycle-Use-Cases hinter Service-Schicht.
2. Passwortprüfung bleibt ausschließlich im Usermanagement.
3. Rollen/`is_qmb` bei Resolve aus aktuellem User-Stand laden (nicht in Session einfrieren).
4. Negative Pfade für alle Session-Ablehnungsgründe.

**Tests**

- Unit: create/resolve/expire/revoke/deactivate-Wirkung
- Negative: fehlendes/ungültiges/abgelaufenes/widerrufenes Token; deaktivierter User; fremde user_id/Rolle nicht einschleusbar
- Admin nicht automatisch QMB (`is_effective_qmb`)

**Test-Gate**

```text
.\.venv\Scripts\python.exe -m pytest tests/modules -q
Gezielte neue Session-Unit-Tests grün
Architektur-Gates grün
```

**Abnahmekriterien**

- Ohne gültige Session kein UserContext
- Deaktivierung blockiert Resolve spätestens beim nächsten Aufruf (In-Memory)

**Risiken**

- Parallelpfad neben `session_store.py` — Legacy-Store klar als Desktop-Übergang kennzeichnen, nicht erweitern

**Eskalationskriterien**

- Wechsel zu JWT als Grundmodell
- Businesslogik im Backend vorziehen

**Übergabe**

Getestete Session-Domainlogik → Milestone 3.

---

### Milestone 3 – PostgreSQL-Fundament und Schema

**Ziel**

PostgreSQL-Anbindung für Usermanagement vorbereiten: Treiber-Dependency, paralleler
PG-Schema-Pfad (ohne AP-027-Rewrite), Schema `usermanagement` mit `users` und `sessions`,
fail-closed Applicator mit Fingerprint, NOLOGIN-Rechterollen, Bundle-/CI-Absicherung.
Details: `docs/AP-028_M3_POSTGRES_SCHEMA.md`.

**Voraussetzungen**

Milestone 2 integriert in `main`; AP-027-Policy verstanden (`docs/DATABASE_EVOLUTION_POLICY.md`).

**Scope**

- Dependency `psycopg[binary]` in `requirements.txt` / `constraints-py314.txt`
- `provision_roles.sql` **vor** `0001_initial` (NOLOGIN-Rollen, leeres Schema, kein Secret)
- Migrationen unter `modules/usermanagement/postgres/migrations/`
- History mit `schema_fingerprint`; Applicator mit `SET ROLE qmtool_migrator`
- `scripts/postgres_migration_gate.py` (fail-closed Basisprüfung, append-only, immutable, Bundle)
- Bundle: PG-SQL + `psycopg`/`psycopg_binary`; CI-Job mit echtem Provisioning
- M3.1-Härtung vor M4: vollständiger Rollen-/ACL-Vertrag und OID-freier Fingerprint aller relevanten Schemaobjekte

**Nicht-Ziele**

- Migration aller anderen Module
- Produktiv-Cutover / Dual-Write / Backup-Restore (M8)
- Rewrite von AP-027 / `database_evolution.py`
- PostgreSQL-Repositories (M4), Backend-Routen (M5)
- Vollständige generische RBAC-Tabellen

**Betroffene Dateien/Bausteine**

- `modules/usermanagement/postgres/` und `postgres_schema.py`
- `docs/AP-028_M3_POSTGRES_SCHEMA.md`, M0-State-Matrix Punkt 5
- `requirements.txt`, `constraints-py314.txt`, `pytest.ini`, `.github/workflows/ci-gates.yml`
- `packaging/build_onedir.py`, `packaging/verify_bundle_imports.py`
- `scripts/postgres_migration_gate.py`
- Tests unter `tests/modules/usermanagement/test_postgres_schema_*.py`

**Implementierungsaufgaben**

1. Stabile `user_id` als UUID (App-seitig); Username unique case-insensitiv (`lower(username)`).
2. Soft-Deaktivierung: aktiv ⇒ `deactivated_at` NULL; inaktiv darf historisch unbekannt NULL bleiben.
3. Sessions: `token_hash UNIQUE`, Zeiten UTC, `revoked_at`, FK `ON DELETE RESTRICT`, Index auf `user_id`.
4. Keine Klartextpasswörter/Klartexttokens; Provisioning ohne Passwörter.
5. Fail-closed: Historien-Präfix, Fingerprint-Drift, `pg_try_advisory_lock`, echte Migrationstransaktion.
6. Runtime: DML auf `users`/`sessions`, kein DDL, keine History-Änderung.
7. Gate: ungültige Basis-Refs, Listing-Fehler, gelöschte oder mutierte Basismigrationen und nicht angehängte Versionen blockieren.
8. Rollenvertrag: keine gefährlichen Mitgliedschaften; Runtime-Rechte werden einzeln bei jedem Lauf validiert.

**Tests**

- Statisch ohne PG: Kette, SQL-Verträge, Secrets-Verbot, Scratch-Git-Gate, Bundle-Collect
- Live mit PG: echtes Provisioning, Fresh Install, No-Op, Constraints, Objekt-/Fingerprint-Drift, Lock/Rollback, Rollenmitgliedschaften und Runtime-Rechte
- SQLite-Evolution-Gates und Onedir-Build unverändert bzw. erweitert grün

**Test-Gate**

```text
git diff --check
.\.venv\Scripts\python.exe -m pytest tests/modules/usermanagement -q
.\.venv\Scripts\python.exe -m pytest tests/modules -q
.\.venv\Scripts\python.exe -m pytest tests/platform/test_database_evolution.py tests/platform/test_core_database_migrations.py tests/platform/test_database_migration_gate.py tests/interfaces/test_architecture_gates.py -q
.\.venv\Scripts\python.exe scripts/postgres_migration_gate.py --base-ref origin/main --output build/postgres-migration-gate-output.json
.\.venv\Scripts\python.exe scripts/postgres_migration_gate.py --base-ref invalid-ref --output build/postgres-migration-gate-negative.json
.\.venv\Scripts\python.exe scripts/database_migration_gate.py --output build/database-migration-gate-output.json
.\.venv\Scripts\python.exe scripts/golive_gate.py --output build/golive-gate-output.json
.\.venv\Scripts\python.exe packaging/build_onedir.py
Live-PG: lokal falls QMTOOL_PG_DSN gesetzt, sonst verbindlich CI-Job postgres-usermanagement (QMTOOL_PG_REQUIRED=1, keine Skips)
Keine produktiven storage/-Dateien mutieren
```

**Abnahmekriterien**

- Schema versioniert; Tabellen-Owner = `qmtool_migrator`; Runtime ohne DDL, History-Rechte oder Migrator-Mitgliedschaft
- Foundation-Invarianten nicht gebrochen
- PG-Live-Tests und Bundle-Prüfung in CI nicht übersprungen
- Kein produktiver PG-Cutover vor M8

**Risiken**

- Scope-Explosion der Foundation → bewusst paralleler UM-Pfad statt Foundation-Rewrite

**Eskalationskriterien**

- Irreversible Migration ohne Backup-Pfad
- Big-Bang-Migration aller Module

**Übergabe**

Versioniertes und durch M3.1 gehärtetes PG-Schema → Milestone 4.

---

### Milestone 4 – PostgreSQL-Repositories

**Ziel**

UserRepository und SessionRepository auf PostgreSQL; Transaktionen, Fehlerbehandlung, Integrität.

**Voraussetzungen**

Milestone 3 einschließlich M3.1 integriert. M4 prüft zusätzlich die deployment-spezifische Runtime-LOGIN-Rolle, die außerhalb von M3 provisioniert wird.

**Scope**

- Konkrete PG-Implementierungen hinter bestehenden/erweiterten Ports
- Mapping Domain ↔ Tabellen
- Transaktionale Login-Session-Erzeugung
- Keine Klartext-Token-Persistenz

**Nicht-Ziele**

- HTTP-Endpunkte
- Cutover aus SQLite
- Fachmodule umstellen

**Betroffene Dateien/Bausteine**

- `modules/usermanagement/repository.py` und neue PG-Implementierung (kein Import von Internals außerhalb des Moduls)
- Wiring/`module.py` (Runtime-Registrierung nur über Composition Root / ModuleContract)
- Repository-Tests
- `docs/AP-028_M4_POSTGRES_REPOSITORIES.md`

**Implementierungsaufgaben**

1. CRUD/Lookup User inkl. Aktivstatus und Rollenfeldern.
2. Session insert/find-by-hash sowie atomare `touch`-/`revoke`-/`revoke_all_for_user`-Transitions; ein paralleler Touch darf einen Widerruf niemals überschreiben.
3. Fehler bei Constraint-Verletzungen klar mappen.
4. SQLite-Repo bleibt bis M8/M9 als Legacy-Pfad gekennzeichnet, nicht Dual-Write.

**Tests**

- Repository-Integrationstests gegen Test-PostgreSQL (oder dokumentierte Teststrategie)
- Live-Test des expliziten PostgreSQL-Composition-Ports und des opaken `UserManagementService`-Sessionpfads
- Integrität: Unique username, FK session→user, revoked/expired Filter
- Konkurrenztest: paralleler Touch/Widerruf bleibt monoton widerrufen

**Test-Gate**

```text
Neue Repository-Tests grün
.\.venv\Scripts\python.exe -m pytest tests/modules -q
Keine Architekturverletzungen
```

**Abnahmekriterien**

- Sessionlogik aus M2 läuft unverändert gegen PG-Repos
- Token nur gehasht gespeichert

**Risiken**

- Testumgebung ohne PostgreSQL → Eskalation mit reproduzierbarem Setup-Bedarf, nicht still überspringen

**Eskalationskriterien**

- Direkter SQL-Zugriff aus Backend oder anderen Modulen

**Übergabe**

Persistente Repositories → Milestone 5.

---

### Milestone 5 – Backend-Auth-Grundlage

**Ziel**

Auth-HTTP-Endpunkte und Sessionauflösung im Backend-Host; Runtime-Anbindung; UserContext-Erzeugung; Request-ID.

**Voraussetzungen**

Milestones 1–4.

**Scope**

Mindestens:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/change-password`

Zusätzlich Dependency/Middleware: Token annehmen, hashen, Session resolve, Context bauen, Request-ID setzen. Aufrufe nur über `modules/usermanagement/api.py` / öffentlichen Service-Port.

**Nicht-Ziele**

- Documents-/Fachrouten
- Vollständige PyQt-Umstellung
- Benutzeradmin-REST (optional später / eigener Schnitt, nicht M5 überladen)
- Businesslogik in FastAPI-Routen

**Betroffene Dateien/Bausteine**

- `src/backend/api.py` und ggf. schlanke Router-/Dependency-Module unter `src/backend/` (öffentliche Importgrenze bleibt `api.py`)
- Runtime-Bootstrap-Anbindung für Backend-Prozess
- Backend-API-Tests (neu)

**Implementierungsaufgaben**

1. Login: Credentials → Usermanagement → Session-Token an Client; Hash in DB.
2. Authentifizierte Requests: Token → Context; bei Fehler kein Fachaufruf.
3. Logout widerruft aktuelle Session.
4. `/auth/me` liefert serverseitig bestimmten Kontext (keine Client-Rollen).
5. HTTP-Fehlerübersetzung ohne Geheimnisoffenlegung.
6. Übergabepunkt aus M2: `resolve_session(..., password_change_allowed=True)` darf ausschließlich vom dedizierten Change-Password-Endpunkt gesetzt werden — niemals client-steuerbar, niemals von anderen Routen.

**Tests**

- Backend-API-Tests: login/logout/me/change-password
- Negative: kein Token, ungültiges Token, inaktiver User
- Architektur-Gates: keine Modul-Internal-Imports im Backend, keine Repo-Nutzung

**Test-Gate**

```text
Neue Backend-Auth-Tests grün
.\.venv\Scripts\python.exe -m pytest tests/interfaces/test_architecture_gates.py -q
.\.venv\Scripts\python.exe -m src.backend  und GET /health weiterhin ok
Gezielte Module-Tests grün
```

**Abnahmekriterien**

- Mehrere parallele Sessions unterschiedlicher Benutzer möglich
- Client kann keine fremde `user_id`/Rolle als Actor setzen

**Risiken**

- Godfile in `api.py` — Router schlank halten
- Desktop-Runtime und Backend-Runtime vermischen

**Eskalationskriterien**

- Fachlogik oder SQL im Backend
- Neue öffentliche Modulfläche ohne Plan

**Übergabe**

Funktionierende Auth-HTTP-Basis → Milestone 6.

---

### Milestone 6 – Aktivstatus, Rollenänderung und Sessionwiderruf

**Ziel**

Deaktivierung, Rollen-/`is_qmb`-Änderung und Sessionwiderruf wirken spätestens beim nächsten Request; Logout-All falls im Scope.

**Voraussetzungen**

Milestone 5.

**Scope**

- `set_user_active` / Deaktivierung blockiert bestehende Sessions bei Resolve
- Bei neuer Deaktivierung: `deactivated_at` als echten UTC-Zeitpunkt setzen; bei Reaktivierung entfernen (`NULL`)
- Rollen- und `is_qmb`-Änderungen ohne Session-Freeze
- `POST /auth/logout-all` und/oder Session-Liste/Löschung falls ohne Überladung
- Passwortwechselwirkung gemäß Abschnitt E (wenn entschieden; sonst explizite Default-Policy dokumentieren und testen)

**Nicht-Ziele**

- Vollständige User-Admin-REST-Oberfläche aller CRUD-Routen (kann folgen, wenn Scope klein bleibt)
- Incident-Admin=QMB-Cleanup

**Betroffene Dateien/Bausteine**

- Usermanagement Admin-/Auth-Ops und Session-Resolve
- Backend Auth-Routen Erweiterung
- Tests Negativpfade

**Implementierungsaufgaben**

1. Deaktivierung → nächster Request abgelehnt.
2. QMB-Flag/Rolle → nächster Request ohne alte Wirkung.
3. Logout-All widerruft alle Sessions des Users.
4. Admin ≠ QMB in Resolve/`is_effective_qmb` absichern.

**Tests**

- Alle verpflichtenden Session-/Identitäts-Negativtests aus Übergabeabschnitt 16.2 soweit M6 betroffen
- Passwortwechsel-Session-Policy-Tests

**Test-Gate**

```text
Neue Auth-/Session-Negativtests grün
.\.venv\Scripts\python.exe -m pytest tests/modules -q
Backend-Auth-Tests grün
```

**Abnahmekriterien**

- Keine gültige Session für deaktivierte Benutzer
- Rollenänderung ohne Re-Login wirksam (Resolve-Pfad)

**Risiken**

- Caching ohne Invalidierung — kein Rollen-Cache ohne Strategie

**Eskalationskriterien**

- Unklare Passwortwechsel-Revoke-Policy (Abschnitt E)

**Übergabe**

Durchgesetzte Session-Wirkung → Milestone 7.

---

### Milestone 7 – Auditnachweis

**Ziel**

Auth- und Usermanagement-Ereignisse auditierbar mit Actor/Target/Session/Request-Trennung.

**Voraussetzungen**

Milestones 5–6; Orientierung an AP-006 / AP-006A.

**Scope**

Mindestens auditierbare Ereignisse:

- Login success/fail, Logout, Session create/revoke/expire, logout-all
- User create/deactivate/reactivate, Rolle/`is_qmb` geändert, Passwort geändert / Wechsel erzwungen

Felder u. a.: `event_id`, `event_type`, `occurred_at` (UTC), `actor_user_id`, `actor_session_id`, `target_user_id`, `request_id`, `result`, `reason`, `source/client_type`.

**Nicht-Ziele**

- Elektronische Signatur
- Documents-Evidence-Ketten-Upgrade
- Freie Client-Vorgabe von Audit-Actor

**Betroffene Dateien/Bausteine**

- Usermanagement Event-/Audit-Integration (bestehende Domain-Events korrigieren: Actor ≠ Target)
- Nutzung Platform-`audit_logger` wo Port bereits gefordert
- Audit-Nachweistests

**Implementierungsaufgaben**

1. Login-Fehlschläge intern differenziert, extern ohne User-Enumeration.
2. Systemactor nur bei echten Systemaktionen (z. B. Session-Cleanup).
3. Keine Passworthashes/Tokens in Logs.

**Tests**

- Auditnachweistests für Erfolg/Fehler/Logout/Revoke
- Actor/Target-Verwechslungs-Negativtests

**Test-Gate**

```text
Audit- und Auth-Tests grün
Relevante Module-/Platform-Tests grün
Keine P0/P1 offen
```

**Abnahmekriterien**

- Audit-Actor stammt aus belastbarer Session/Context-Quelle
- Kein Owner-/Zieluser-/`system`-Fallback für interaktive Aktionen

**Risiken**

- Doppelte Event- und Auditlog-Semantik — AP-016/AP-006A beachten, Scope klein halten

**Eskalationskriterien**

- Unklare Nachweisniveau-Änderung gegenüber AP-006A

**Übergabe**

Auditfähig → Milestone 8.

---

### Milestone 8 – Migrations- und Cutover-Vorbereitung

**Ziel**

Reproduzierbare Datenübernahme SQLite/`users.db` (+ Analyse JSON-Session) nach PostgreSQL; Validierung; Backup/Restore; kein Dual-Write.

**Voraussetzungen**

Milestones 3–7; Backup/Restore-Gates der Foundation.

**Scope**

- Inventar Altbestand
- Übernahmeskript/Use-Case: User-IDs, Rollen, Aktivstatus, Passwort-Hashes erhalten
- Validierungsreport
- Wartungs-/Cutover-Schritt dokumentiert
- Altbestand nur als gesicherte Quelle

**Nicht-Ziele**

- Gleichzeitiges Schreiben in SQLite und PostgreSQL
- Migration anderer Module
- Hard-Delete historischer User

**Betroffene Dateien/Bausteine**

- Migrations-/Cutover-Werkzeuge unter dokumentiertem Owner (Modul oder `scripts/`, ohne Parallelwahrheit)
- Gate-Outputs unter `build/`
- Doku Cutover-Runbook in `docs/` (schlank, AP-028-bezogen)

**Implementierungsaufgaben**

1. Mapping alter `user_id`(=username) → stabile UUID-Strategie explizit entscheiden und dokumentieren (wenn noch offen → Eskalation).
2. Case-insensitive Username-Kollisionen gegen PG-Index `UNIQUE (lower(username))` vor Import validieren und auflösen.
3. Hash-Übernahme ohne Re-Hash-Verlust.
4. Sessions: Alt-JSON nicht als PG-Sessions importieren (kein Fake-Token); Nutzer müssen neu einloggen nach Cutover.
5. Backup/Restore-Drill für Usermanagement-PG.

**Tests**

- Datenübernahme-Validierungstests
- Backup/Restore grün
- Keine Klartextgeheimnisse im Ziel

**Test-Gate**

```text
Cutover-Validierungstests grün
Backup/Restore-Drill grün
Migration-/Go-live-Gates soweit betroffen grün
```

**Abnahmekriterien**

- Reproduzierbare Übernahme
- PostgreSQL ist nach Cutover einzige Wahrheit für Usermanagement

**Risiken**

- Referenzbruch in anderen Modulen bei user_id-Änderung → muss vor Cutover geklärt/eskaliert werden

**Eskalationskriterien**

- Möglicher Datenverlust oder irreversible Migration ohne validierten Restore
- user_id-Remapping mit Quermodul-Impact

**Übergabe**

Cutover-bereit → Milestone 9.

---

### Milestone 9 – Legacy-Grenze und Abschluss

**Ziel**

`current_user.json` nur noch klarer Desktop-Übergang oder entfernt aus Backend-Pfad; öffentliche API stabil; Volltestlauf; Abschlussdokumentation.

**Voraussetzungen**

Milestone 8 erfolgreich (oder Cutover technisch freigegeben und getestet).

**Scope**

- Backend nutzt niemals lokale Sessiondatei als Wahrheit
- Kennzeichnung/Abschaltung Legacy-Session für backend-migrierte Auth-Use-Cases
- Abschlussmatrix gegen Abschnitt D
- Dokumentation Status AP-028

**Nicht-Ziele**

- Vollständige PyQt-Multiuser-UX
- Documents-Multiuser-MVP (folgt separat)

**Betroffene Dateien/Bausteine**

- `session_store.py` Legacy-Grenze
- `docs/AP-028_*` Abschlussstatus
- Master-Roadmap Statusnachtrag (AP-028 erledigt / nächster Schwerpunkt Documents-MVP)

**Implementierungsaufgaben**

1. Sicherstellen: keine Backend-Resolve-Pipeline liest JSON-Session.
2. CLI/PyQt: Auth-Fachlogik nicht neu erfinden; Übergang dokumentieren.
3. Gesamttestlauf laut Gates.
4. Abschlussbericht mit Ausführungspfad und DoD.

**Tests**

- Alle neuen Unit-/Contract-/Repo-/Backend-/Migrations-/Audit-/Architektur-Tests
- Verpflichtende Negativtests Abschnitt 16.2 der Übergabe

**Test-Gate**

```text
.\.venv\Scripts\python.exe -m pytest tests/platform -q
.\.venv\Scripts\python.exe -m pytest tests/modules -q
.\.venv\Scripts\python.exe -m pytest tests/interfaces -q
.\.venv\Scripts\python.exe -m pytest tests/e2e_cli -q
Architektur-Gates grün
Anwendbare Migration-/Go-live-Gates grün
Keine offenen P0/P1
```

**Abnahmekriterien**

- Gesamtabschlussdefinition (Abschnitt D) erfüllt oder Abweichungen supervisor-freigegeben dokumentiert

**Risiken**

- Verfrühte Entfernung der Desktop-Session bricht lokale CLI/PyQt — Übergangspfad bewusst belassen bis Clients umgestellt sind

**Eskalationskriterien**

- Bedarf, Documents-MVP in denselben Milestone zu ziehen

**Übergabe**

AP-028 abgeschlossen → Documents-Multiuser-MVP als nächstes separat freizugebendes Paket (Voraussetzung: bestätigter UserContext verfügbar).

---

## D. Gesamte Abschlussdefinition

### Fachlogik

- Mehrere parallele Sessions unterschiedlicher Benutzer
- Jeder Backend-Request eindeutig einer gültigen Session zuordenbar
- Aktiver Benutzer ausschließlich serverseitig bestimmt
- Keine autoritativen Client-`user_id`-/Rollen-Claims
- Deaktivierte Benutzer blockiert; Ablauf und Widerruf funktionieren
- Login/Logout backendgestützt
- Bestätigter frozen UserContext über öffentliche Grenze
- Usermanagement nur globale Identitäts-/Berechtigungsgrundlagen; Fachautorisierung bleibt in Fachmodulen

### Architektur

- Backend ohne Businesslogik und ohne direkte Fach-Repositories
- Öffentliche Grenze `modules/usermanagement/api.py`
- Keine neuen externen Imports auf Modul-Internals
- CLI/PyQt keine fachliche Auth-Quelle
- `current_user.json` keine Backend-Wahrheit
- Keine optionalen Actor-Parameter als Ersatz für bestätigten Kontext
- Systemactor ≠ Useractor

### Persistenz

- Usermanagement produktiv auf PostgreSQL oder technisch cutover-bereit
- Versionierte Migrationen; Sessions nur serverseitig; Token nur gehasht
- Stabile User-IDs; Soft-Deaktivierung
- Getrennte Migrator-/Runtime-Rechte
- Backup/Restore und Datenübernahme validiert
- Kein Dual-Write

### Sicherheit

- Alle verpflichtenden Negativtests grün
- Deaktivierung und Rollenänderungen wirken laut Policy
- Keine Klartextpasswörter/Tokens persistiert oder geloggt
- Auth-Fehler ohne unnötige User-Enumeration

### Audit

- Login/Logout/Session/User-Admin-Ereignisse nachvollziehbar
- Actor, Target, Session, Request unterscheidbar
- UTC-Zeitstempel
- Keine stillen Actor-Fallbacks

### Migration

- Forward-only; Cutover dokumentiert; Altbestand gesichert

### Tests

- Neue und relevante bestehende Tests grün; Architektur- und Migrations-Gates grün

### Dokumentation

- Diese Roadmap, Master-Roadmap-Status, AP-005-Supervisor-Nachtrag, Cutover-Runbook (M8/M9)

---

## E. Kritische offene Entscheidungen

Nur echte Restoffenheiten. Bereits entschieden und hier nicht erneut fraglich:

- Serverseitige opake Sessions (kein JWT als Erstmodell)
- Internes Login (kein externes IdP in diesem AP)
- UserContext als bestätigter serverseitiger Kontext
- Admin ≠ QMB (Supervisor 2026-07-31)
- PostgreSQL für Usermanagement-Scope in diesem AP
- AP-028 vor Documents-Multiuser-MVP

### Noch offen (vor oder während betroffener Milestones zu klären)

1. **Passwortwechsel und bestehende Sessions**
   Widerruf aller Sessions bei Passwortänderung vs. nur aktuelle vs. Behalten bis Ablauf?
   Empfehlung: alle Sessions des Users widerrufen (außer ggf. die Session, in der geändert wurde, neu ausstellen).
   Eskalation spätestens in Milestone 6, falls abweichend gewünscht.

2. **user_id-Remapping bei Cutover**
   Heute oft `user_id == username`. Ziel UUID. Strategie für Referenzen in anderen Modulen (Documents, Training, Incident, Audit)?
   Eskalation zwingend vor Milestone-8-Cutover, sobald Quermodul-Referenzen betroffen sind.

3. **must_change_password-Enforcement**
   Nur Login blockieren außer change-password, oder jeden Request außer whitelisteten Auth-Endpunkten?
   Empfehlung: alle Nicht-Auth-Fachaufrufe blockieren, bis geändert.
   Festschreiben in M2/M5.

4. **Umfang User-Admin-HTTP**
   Ob `GET/POST/PATCH /users` und activate/deactivate in AP-028 oder Folgepaket.
   Empfehlung: Auth/Session zuerst (M5–M7); Admin-REST nur wenn Milestone-Größe es erlaubt, sonst eigenes kleines Folge-Milestone/AP.

5. **PostgreSQL-Testinfrastruktur** — **entschieden in M3:** verbindlicher CI-Job
   `postgres-usermanagement` (`ubuntu-latest`, Service `postgres:16`, `QMTOOL_PG_REQUIRED=1`).
   Lokal ohne DSN nur Live-Tests skippen; in CI ist Skip ein Fehler.

### Bewusst nicht in diesem AP entschieden

- RequestContext-Vollmodell (AP-022) jenseits Request-ID am Auth-Rand
- Incident-Modul Admin=QMB-Cleanup
- Documents-Multiuser-MVP
- Externe Identität / SSO
---

## Anhang: Mapping Übergabe → Repo

| Übergabe-Baustein | Repo-Ist | Ziel in AP-028 |
| --- | --- | --- |
| `session_store.py` / `current_user.json` | Desktop-Legacy | Übergang; nicht Backend-Wahrheit |
| `AuthenticatedUser` | vorhanden | bleibt; ergänzt um `UserContext` |
| `api.py` schmal | Port-lastig | Auth/Session/Context-Exporte erweitern |
| SQLite `users.db` + `0001_initial.sql` | AP-027 Owner `users` | PG Schema `usermanagement` + Cutover |
| `src/backend` | nur `/health` | Auth-Routen + Dependencies |
| `is_effective_qmb` | Admin nicht QMB | beibehalten; Incident-Abweichung out of scope |
| Domain-Events Auth | vorhanden | Actor-Korrektur + Auditnachweis M7 |
| `wiring.py` Duplikat | ungenutzt | nicht als Parallelpfad reaktivieren |
