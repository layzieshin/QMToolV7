# AP-028 Milestone 0 — Ist- und Zielmatrix

Status: abgeschlossen (Dokumentation only)
Datum: 2026-07-31
Branch: `feature/ap-028-m0-state-matrix`
Bezug: `docs/AP-028_USERMANAGEMENT_BACKEND_SESSIONS_ROADMAP.md` (M0), ADRs AP-003–AP-006, Master-Roadmap

Dieses Dokument ist die **einzige Quelle der Wahrheit** für die M0-Ist-/Zielmatrix.
Die Roadmap verweist hierher; Inhalte nicht parallel pflegen.

---

## 1. Verbindlich bestätigt (nicht neu verhandeln)

| Entscheidung | Status | Beleg |
| --- | --- | --- |
| Serverseitige opake Sessions (kein JWT als Erstmodell) | entschieden | Roadmap A/E; Master-Roadmap |
| Internes Login (kein externes IdP/SSO in AP-028) | entschieden | Roadmap A/E; Master-Roadmap |
| Bestätigter, frozen, serverseitig erzeugter UserContext | entschieden | Roadmap A; AP-004 Ziel; AP-028 M1+ |
| Admin ≠ QMB (Option B) | Supervisor 2026-07-31 | AP-005 Statusnachtrag |
| PostgreSQL für Scope Usermanagement (Schema `usermanagement`) | entschieden | Roadmap A/E; Master-Roadmap |
| AP-028 vor Documents-Multiuser-MVP | entschieden | Master-Roadmap Freigabe |

---

## 2. Ist-Matrix (Repo-verifiziert 2026-07-31)

### 2.1 Identität und Benutzer

| Aspekt | Ist | Fundstelle |
| --- | --- | --- |
| User-Contract | `AuthenticatedUser` (frozen): `user_id`, `username`, `role`, Profilfelder, `is_active`, `is_qmb`, `must_change_password` | `modules/usermanagement/contracts.py` |
| Persistenz | SQLite `storage/platform/users.db`, Owner `users`, Migration `modules/usermanagement/migrations/0001_initial.sql` | AP-027 / module wiring |
| `user_id` | Bei Create typischerweise `user_id == username` (kein UUID) | `user_admin_ops.py` |
| Passwort | bcrypt; Legacy-Klartext-Upgrade bei Login möglich | `password_crypto.py`, `auth_ops.py` |
| Basisrollen | `Admin`, `QMB`, `User` (Title-Case in Admin-Ops; Normalisierung uppercase in Policies) | `user_admin_ops.py`, `role_policies.py` |
| Effektives QMB (Usermanagement) | `role == QMB` **oder** `is_qmb=True`; **Admin zählt nicht** | `role_policies.is_effective_qmb` |
| Öffentliche API | Schmal: `AuthenticatedUser`, `get_usermanagement_service`, `bootstrap_admin`, `self_register`, `is_effective_qmb`, `normalize_base_role` | `modules/usermanagement/api.py` |
| Service-Port | Login/Logout/CRUD/Password über Port `usermanagement_service` (nicht alles in `api.py` exportiert) | `service.py` / `module.py` |

### 2.2 Session / Auth-Zustand

| Aspekt | Ist | Fundstelle |
| --- | --- | --- |
| Session-Modell | Eine lokale JSON-Datei pro App-Home | `session_store.py` |
| Pfad | `{app_home}/storage/platform/session/current_user.json` | `module.py` |
| Inhalt | `user_id`, `username`, `role` — kein Token, kein Ablauf, kein Widerruf | `session_store.save` |
| Login | Authenticate + Datei schreiben | `auth_ops.login` |
| Logout | Datei löschen | `auth_ops.logout` / `SessionStore.clear` |
| Reload | Optional User aus Repository per username nachladen | `session_store.get_current_user` |
| Multiuser / HTTP | Nicht geeignet (ein globaler Dateizustand) | AP-003 Kat. A |
| `wiring.py` | Duplikat der Port-Registrierung; **nicht aktiv importiert** | `modules/usermanagement/wiring.py` |

### 2.3 Weitergabe an andere Module / Adapter

| Aspekt | Ist | Risiko |
| --- | --- | --- |
| Implizit | Module rufen `get_current_user()` über Port | Keine Sessionbindung |
| Explizit | CLI/PyQt übergeben oft `actor_user_id` / `actor_role` | Client-behauptete Identität/Rolle |
| UX-Gates | PyQt `access_guards`, Visibility mit `is_effective_qmb` | OK als UX; keine fachliche Wahrheit |
| Backend | **Keine** Anbindung an Usermanagement | Auth-Use-Cases lokal/Desktop |

### 2.4 Backend

| Aspekt | Ist |
| --- | --- |
| Framework | FastAPI + uvicorn |
| Endpunkte | Nur `GET /health` |
| Middleware / Auth / Request-ID | Keine |
| Runtime/Container-Bootstrap | Nicht angebunden |
| Backend-Tests | Keine dedizierten HTTP-Tests |

### 2.5 Audit / Events

| Aspekt | Ist |
| --- | --- |
| Domain-Events | Auth success/fail, session login/logout, user created/… vorhanden |
| Actor-Qualität | Admin-Events setzen teils **Zieluser** als `actor_user_id` (AP-006) |
| `audit_logger`-Port | In ModuleContract gefordert, im Modulcode praktisch ungenutzt |
| System-/Unknown-Fallbacks | Plattformweit bekannt; für interaktive Auth unzulässig im Zielbild |

### 2.6 Bekannte Abweichung (Out of Scope für AP-028)

| Aspekt | Ist | Behandlung |
| --- | --- | --- |
| Incident Admin=QMB | `incident_management/authorization.is_qmb` gibt bei Rolle `Admin` `True` | Dokumentiert; **kein Cleanup in AP-028** |

### 2.7 Tests (Abdeckung grob)

| Vorhanden | Kaum / nicht |
| --- | --- |
| Persistenz, Seed, QMB-Flag, Self-Register, must_change_password, Auth-Events | SessionStore/JSON, Token/TTL/Revoke, Backend-Auth, AuditLogger-Nutzung, Admin≠QMB-Konsistenz über Module |

---

## 3. Ziel-Matrix (AP-028)

### 3.1 Identität und Kontext

| Aspekt | Ziel | Milestone |
| --- | --- | --- |
| Stabile `user_id` | UUID; Username änderbar und unique | M3/M8 |
| Soft-Deaktivierung | `is_active=false`, kein Hard-Delete | M3/M6 |
| `UserContext` | Frozen; serverseitig aus gültiger Session; mind. `user_id`, `session_id`, `request_id`, `username`, globale Rolleninfo, `is_qmb`, `authenticated_at` (UTC) | M1, Erzeugung M2/M5 |
| `SystemExecutionContext` | Expliziter `system_actor` + `request_id`; nie stiller Ersatz | M1 |
| Admin ≠ QMB | Wie `is_effective_qmb`; Incident-Abweichung bleibt bis Separatpaket | durchgängig |
| Öffentliche API | Contracts + Auth/Session/Context-Use-Cases über `api.py` erweitern | M1+ |

### 3.2 Sessions

| Aspekt | Ziel | Milestone |
| --- | --- | --- |
| Modell | Serverseitig, opak; Klartext-Token nur an Client; DB speichert Hash | M2–M4 |
| Felder | u. a. `session_id`, `token_hash`, `user_id`, Zeiten UTC, `revoked_at`, `client_type` | M1–M3 |
| Resolve-Prüfungen | Token, Existenz, Ablauf, Widerruf, User aktiv, ggf. must_change_password | M2/M5/M6 |
| Rollen | Nicht in Session einfrieren; pro Resolve aus User laden | M2/M6 |
| Parallelität | Mehrere Sessions / Benutzer möglich | M4/M5 |
| Legacy JSON | Keine Backend-Wahrheit; Desktop-Übergang bis M9 | M9 |

### 3.3 Persistenz

| Aspekt | Ziel | Milestone |
| --- | --- | --- |
| DB | PostgreSQL, Schema `usermanagement`, Tabellen mind. `users`, `sessions` | M3 |
| Rollen DB | `qmtool_migrator` / `qmtool_runtime` | M3 |
| Repositories | PG User- + Session-Repository hinter Ports | M4 |
| Dual-Write | **Verboten** als Dauerzustand | M8 |
| Cutover | Reproduzierbar, Backup/Restore, Validierung; Altbestand gesichert | M8 |

### 3.4 Backend-Host

| Aspekt | Ziel | Milestone |
| --- | --- | --- |
| Routen | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password` (+ optional logout-all/sessions) | M5/M6 |
| Verantwortung | HTTP, Serialisierung, Tokenannahme, Request-ID, Sessionauflösung, Context, Aufruf öffentlicher Modul-API, Fehler→HTTP | M5 |
| Nicht | Businesslogik, direkte Repos, Fachautorisierung anderer Module | — |
| Runtime | Backend-Prozess an Container/Bootstrap anbinden | M5 |

### 3.5 Audit

| Aspekt | Ziel | Milestone |
| --- | --- | --- |
| Ereignisse | Login success/fail, Logout, Session create/revoke/expire, User-Admin-Änderungen | M7 |
| Trennung | Actor ≠ Target; Session- und Request-Bezug; UTC | M7 |
| Geheimnisse | Keine Passwörter/Token im Klartext in Logs/Audit | durchgängig |

### 3.6 Kette (Soll)

```text
gültige Session
→ eindeutig aktiver Benutzer
→ bestätigter UserContext
→ fachliche Autorisierung (im jeweiligen Fachmodul)
→ identischer Audit-Actor (aus belastbarer Quelle)
```

---

## 4. Out of Scope (explizit)

| Thema | Begründung |
| --- | --- |
| Incident Admin=QMB-Cleanup | Supervisor: getrenntes Paket; AP-005/Roadmap |
| Documents-Fachautorisierung / Owner/Review/Freigabe | Anderes Modul |
| PyQt-Vollumbau / alle Clients auf Backend | Adapter später; Legacy-Übergang erlaubt |
| PostgreSQL für andere Module | Kein Big-Bang |
| Redis, OAuth/OIDC/SSO, Mandanten | Roadmap Nicht-Ziele |
| RequestContext-Vollmodell (AP-022) | Nur Request-ID am Auth-Rand in AP-028 |
| `wiring.py` reaktivieren | Parallelpfad verboten |

---

## 5. Restoffenheiten (nur Roadmap Abschnitt E)

Nicht in M0 entschieden — Empfehlungen unverändert übernehmen (außer Punkt 5, in M3 entschieden):

1. **Passwortwechsel → Session-Widerruf-Policy** (Empfehlung: alle Sessions widerrufen; aktuelle neu ausstellen) — spätestens M6
2. **user_id-Remapping** username→UUID und Quermodul-Referenzen — vor M8-Cutover eskalieren falls Impact
3. **must_change_password-Enforcement** (Empfehlung: alle Nicht-Auth-Fachaufrufe blockieren) — M2/M5 festschreiben
4. **User-Admin-HTTP-Umfang** in AP-028 vs. Folgepaket — Auth zuerst
5. **PostgreSQL-Testinfrastruktur** — **entschieden in M3:** verbindlicher CI-Job auf `ubuntu-latest` mit Service `postgres:16`. Live-Tests tragen `@pytest.mark.postgres`. Ohne `QMTOOL_PG_DSN` lokal skippen; mit `QMTOOL_PG_REQUIRED=1` (CI) ist Skip ein Fehler. Statische SQL-Textprüfungen allein reichen nicht.

---

## 6. Widersprüche ADR ↔ Code ↔ Roadmap

| Thema | Bewertung | Aktion |
| --- | --- | --- |
| AP-004 ließ Session vs. Token offen | Roadmap/Supervisor schließen auf opake Sessions | Kein Konflikt mehr für AP-028 |
| AP-005 Admin≠QMB vs. Incident Admin=QMB | Bewusste Abweichung | Out of Scope; kein M0-Eskalationsstopp |
| Actor = Target in User-Admin-Events | Bekannt (AP-006); Zielkorrektur M7 | Kein Verhaltens-Change in M0 |
| Master-Roadmap vs. Übergabe (Priorität) | Bereits zugunsten AP-028 aufgelöst | Erledigt |

Keine Eskalation erforderlich für Milestone-0-Abschluss.

---

## 7. Test-Gate M0

- Produktcode unverändert.
- Architektur-Gates: siehe Verifikation im Abschluss dieser Änderung.
- Optionale Usermanagement-Baseline: bei Ausführung Ergebnis dokumentieren.

---

## 8. Übergabe an Milestone 1

Milestone 1 darf starten: öffentliche Contracts (`UserContext`, `SystemExecutionContext`, Session-Typen, Fehlerverträge) und `api.py`-Exporte.

**Nicht** in M0/M1 vermischen: PostgreSQL, HTTP-Routen, Repository-Implementierung, Incident-Cleanup.
