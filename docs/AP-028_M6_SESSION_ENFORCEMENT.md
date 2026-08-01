# AP-028 M6 - Session-Enforcement

## Zweck

M6 macht den bestehenden Backend-Sessionpfad fuer den echten Mehrbenutzerbetrieb
belastbar: Deaktivierungen, Rollen- und QMB-Aenderungen wirken ohne erneuten
Login; Passwortwechsel und Logout-All widerrufen Sessions kontrolliert. Eine
kleine Admin-API erlaubt das Anlegen und Verwalten bekannter Benutzer, ohne eine
vollstaendige Benutzerverwaltung aufzubauen.

Umsetzungsplan: dieses Dokument. Voraussetzung: Milestone 5
(`docs/AP-028_M5_BACKEND_AUTH_FOUNDATION.md`).

## Verbindliche Entscheidungen

- **Passwortwechsel (Abschnitt E.1):** Die aktuelle Session bleibt gueltig
  (kein Re-Issue). Alle anderen Sessions desselben Users werden widerrufen.
  Im PostgreSQL-Pfad laufen Passwortaenderung und Fremdsession-Widerruf in
  einer Transaktion.
- **Admin-HTTP (Abschnitt E.4):** Minimalvertrag in M6:
  `POST /users` und `PATCH /users/{username}/access`. Kein GET/Liste,
  kein Passwort-Reset, keine Session-Viewer.
- **`must_change_password` (Abschnitt E.3):** Nicht wieder geoeffnet. Resolve
  blockiert Nicht-Whitelist-Aufrufe bereits in M2/M5. Create-Default bleibt
  `must_change_password=true`.

## Zielausfuehrungspfad

```text
HTTP request
  -> src/backend middleware/dependency
    -> modules.usermanagement.api
      -> UserManagementService / SessionOps / UserAdminOps
        -> PostgreSQL (Backend) oder SQLite (Desktop Aktivstatus)
```

`src/backend` bleibt reiner Adapter. Fachentscheidungen und Authz liegen im
Usermanagement-Service; die Backend-Dependency prueft Admin zusaetzlich.

## Auth-Erweiterungen

### `POST /auth/logout-all`

Erfordert einen bestaetigten User-Context. Widerruft alle Sessions des Users
einschliesslich der aktuellen. Antwort `204`. Der verwendete Token ist danach
ungueltig.

### `POST /auth/change-password` (M6-Verhalten)

Wie M5: Body nur `new_password`; Zieluser aus dem Context. Zusaetzlich:
Widerruf aller anderen Sessions. Die aktuelle Session bleibt gueltig.

## Aktivstatus und Rollen

- Deaktivierung (aktiv → inaktiv): `deactivated_at` = UTC-Jetzt; alle Sessions
  des Users werden widerrufen.
- Reaktivierung: `deactivated_at = NULL`; alte Sessions werden nicht
  wiederbelebt; neuer Login erforderlich.
- Rollen- und `is_qmb`-Aenderungen widerrufen keine Sessions. Der naechste
  Resolve laedt aktuelle Werte aus der Datenbank.
- `Admin` ohne Rolle `QMB` und ohne `is_qmb=True` ist kein QMB
  (`is_effective_qmb`).
- Der letzte aktive Admin darf weder deaktiviert noch auf eine andere
  Basisrolle gesetzt werden. Selbständerungen sind erlaubt, solange
  mindestens ein weiterer aktiver Admin existiert.

## SQLite-Paritaet

SQLite erhaelt Migration `0002` fuer `deactivated_at TEXT NULL`, damit Desktop-
und PostgreSQL-Pfad denselben Aktivstatusvertrag haben. PostgreSQL benoetigt
keine neue Migration (Spalte und Constraint existieren seit M3); der Write-Pfad
setzt bei Deaktivierung den UTC-Zeitstempel.

Opake Sessions bleiben Backend/PostgreSQL (plus In-Memory fuer Tests). SQLite
hat keine Session-Tabelle.

## Minimaler Admin-HTTP-Vertrag

### `POST /users`

Nur bestaetigte Admin-Kontexte. Body:

- `username` (pflicht)
- `password` (pflicht; zentrale Passwortpolicy)
- `role` optional, Standard `User`
- `is_qmb` optional, Standard `false`
- `must_change_password` optional, Standard `true`

### `PATCH /users/{username}/access`

Nur bestaetigte Admin-Kontexte. Body enthaelt mindestens eines aus
`role`, `is_qmb`, `is_active`.

### Response-Felder

Nur: `user_id`, `username`, `role`, `is_active`, `is_qmb`,
`must_change_password`. Nie Passwort, Hash, Token oder Sessiondaten.

### Stabile Fehler

| HTTP | `error` |
| --- | --- |
| 401 | `unauthorized` |
| 403 | `forbidden` |
| 400 | `weak_password` / `invalid_user_update` |
| 404 | `user_not_found` |
| 409 | `user_exists` / `last_active_admin` |

## Dateigrenzen

| Datei/Bereich | Verantwortung |
| --- | --- |
| `modules/usermanagement/session_ops.py` / session repos | Revoke-all / revoke-others |
| `modules/usermanagement/user_admin_ops.py` / service | Aktivstatus, Last-Admin, Authz |
| `modules/usermanagement/api.py` | oeffentliche Fassaden |
| `src/backend/auth_routes.py` | logout-all |
| `src/backend/user_admin_routes.py` | `/users` Adapter |
| `src/backend/auth_dependencies.py` | Admin-Dependency, Error-Mapping |
| `modules/usermanagement/migrations/0002_*.sql` | SQLite `deactivated_at` |

## Nicht-Ziele

- M7 Audit-Ausbau
- Incident Admin=QMB Cleanup
- M8 Cutover / user_id-Remapping
- Documents-Routen
- PyQt-/CLI-Backend-Migration
- Session-Liste / Session-Viewer
- GET `/users` und vollstaendige User-Admin-CRUD
- Training-CLI-Fix (bekannter unabhaengiger Projektfehler)

## Abnahmekriterien

- Fremdsession nach Passwortwechsel → `401`; aktuelle Session weiter gueltig
- Logout-all → aktueller Token tot
- Deaktivierter User: Resolve/`/auth/me` abgelehnt; nach Reaktivierung alter
  Token tot
- Rollen-/QMB-PATCH: naechster `/auth/me` zeigt neue Werte ohne Re-Login
- Letzter aktiver Admin: `409 last_active_admin`
- Non-Admin auf `/users`: `403`; unauth: `401`
- Leeres/Whitespace-Passwort beim Create: `400 weak_password`
