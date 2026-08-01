# AP-028 M7 - Atomarer Backend-Auditnachweis

## Zweck

M7 macht Auth- und Usermanagement-Aktionen auf dem PostgreSQL-Backendpfad
nachweisbar: jede gelistete Aktion schreibt genau einen finalen Eintrag in
`usermanagement.audit_events` in derselben Transaktion wie die Zustandsänderung
(Logout-Retry und Expiry-Wiederholung ausgenommen wie unten).

Umsetzungsplan: dieses Dokument. Voraussetzung: Milestone 6
(`docs/AP-028_M6_SESSION_ENFORCEMENT.md`).

## Verbindliche Entscheidungen

- **Einzige M7-Nachweisquelle:** `usermanagement.audit_events` (append-only PG).
- **Nicht** M7-Nachweis: JSONL-`AuditLogger`, Domain-`EventEnvelope` von
  AuthOps/UserAdminOps auf den acht PG-Backend-Use-Cases.
- Feldvertrag: `audit_id`, `reason_code` (nicht Roadmap-Rohnamen `event_id`/`reason`).
- Jeder M7-Eintrag hat eine nichtleere `request_id`; ein fehlender Nachweis ist
  ein Audit-Ausfall, nie ein erfolgreiches Fachereignis.
- Runtime (`qmtool_runtime`) hat nur `INSERT` auf `audit_events`; kein SELECT/
  UPDATE/DELETE. Live-Tests lesen ausschließlich über Migrator-/Admin-DSN.
- Audit-Insert-Fehler → gesamte Fach-TX rollback → HTTP `503`
  `{"error":"unavailable",...}` (nie scheinbarer Erfolg).
- Keine Audit-UI/Export/GET-API; kein SQLite-Audit; keine Documents-Ketten.

## Ereignistypen

| event_type | Actor | Besonderheit |
| --- | --- | --- |
| `auth.login.succeeded` | neuer User + neue Session | Auth+Session+Audit in einer TX |
| `auth.login.denied` | anonymous | `reason_code` intern; HTTP bleibt generische 401 |
| `auth.logout.succeeded` | Session-User | nur bei erstem Revoke |
| `auth.logout_all.succeeded` | Context | `affected_session_count` |
| `auth.session.expired` | system `qmtool.session-expiry` | einmalig via Partial Unique Index |
| `user.created` | Admin-Context | Actor ≠ Target |
| `user.access_changed` | Admin-Context | Diff-Felder + `changed_fields` |
| `user.password_changed` | Context | Actor=Target erlaubt |

## Zielausführungspfad

```text
HTTP auth_routes / user_admin_routes
  -> modules.usermanagement.api (login_backend / logout_backend / ...)
    -> UserManagementService
      -> runtime_connection (eine TX)
        -> users/sessions write
        -> audit_events INSERT
```

## Öffentliche API

Neu:

- `login_backend(container, username, password, *, request_id) -> IssuedSession`
- `logout_backend(container, *, raw_token, request_id) -> None`
- `AuditUnavailableError` → HTTP 503

Es gibt keine separate öffentliche Backend-Fassade zum Erzeugen oder direkten
Widerrufen einer Session: Login und Logout bleiben die einzigen auditierbaren
Backend-Sessionübergänge.

Bestehende Fassaden schreiben auf dem PG-Pfad mit:

- `revoke_all_own_sessions`, `change_own_password`
- `create_user_as_admin`, `update_user_access_as_admin`
- `resolve_session` (Expiry-Audit vor `ExpiredSessionError`)

Intern: `PostgresAuditRepository.insert_on_connection` — nicht öffentlich.

## Logout / Expiry Regeln

- Logout lädt die Session **ohne** `must_change_password`-Sperre.
- Erster Übergang `revoked_at NULL → gesetzt` = ein Nachweis; Retry = `204`
  ohne zweiten Eintrag; unbekannter Token = `401` ohne Audit.
- Expiry: beim ersten `ExpiredSessionError` einmalig Insert; Duplikat wird über
  Partial Unique Index + UniqueViolation (ohne `ON CONFLICT`/`RETURNING`, da
  beides SELECT erfordern würde) übersprungen.

## Schema

Migration `modules/usermanagement/postgres/migrations/0003_audit_evidence.sql`.
Fingerabdruck entsteht beim Apply. Packaging und Schema-Validator erwarten die
Tabelle, CHECKs und INSERT-only Privilegien.

## Außerhalb von M7

- Audit-UI / Export / GET
- Documents-Evidence-Ketten
- SQLite-Audit
- Cleanup-Job für abgelaufene Sessions
- EventEnvelope-/AP-022-Umbau
- JSONL als M7-Senke

## Abnahme

- Jede gelistete Backend-Aktion → genau ein finaler PG-Audit-Row in derselben TX
  (Logout-Retry und Expiry-Wiederholung ausgenommen).
- Runtime kann Audit nicht lesen/ändern/löschen.
- Fehlgeschlagenes Audit → keine committed Fachänderung + HTTP 503.
- JSONL und EventEnvelope sind keine M7-Nachweisquelle für diese Pfade.
