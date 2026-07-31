# AP-028 M3 – PostgreSQL Schema und Migration (Usermanagement)

## Zweck

Paralleler PostgreSQL-Pfad **nur** für Usermanagement. AP-027 (`DatabaseEvolutionService`)
bleibt SQLite-only und wird nicht umgebaut. Kein Repository-, Backend- oder Cutover-Schritt in M3.
Backup/Restore und produktiver Cutover sind **M8**.

## Ablauffolge

1. Administrativ `provision_roles.sql` ausführen (NOLOGIN-Rechterollen + leeres Schema)
2. Deployment-spezifische LOGIN-Rollen außerhalb des Repos anlegen und genau einer Rechterolle zuordnen
3. `migrate_usermanagement_schema(dsn)` als LOGIN-Mitglied von `qmtool_migrator` ausführen
4. Applikation verbindet als LOGIN-Mitglied von `qmtool_runtime`

## Artefakte

| Pfad | Rolle |
| --- | --- |
| `modules/usermanagement/postgres/provision_roles.sql` | Admin-Bootstrap **vor** Migration |
| `modules/usermanagement/postgres/migrations/*.sql` | Versionierte Schema-Migrationen |
| `modules/usermanagement/postgres_schema.py` | Fail-closed Applicator (modulintern) |
| `scripts/postgres_migration_gate.py` | Append-only / Bundle / NOLOGIN-Gate |

Nicht unter `modules/*/migrations/` abgelegt, damit das SQLite-Discovery-Glob sie nicht erfasst.
PG-SQL und Provisioning sind dennoch im Produktionsbundle enthalten.

## Rollenmodell

| Rolle | Art | Zweck |
| --- | --- | --- |
| `qmtool_migrator` | NOLOGIN-Rechterolle | Schema-/Tabellen-Owner, DDL |
| `qmtool_runtime` | NOLOGIN-Rechterolle | DML nur auf `users` und `sessions` |

- Keine Passwörter und keine LOGIN-Attribute in `provision_roles.sql`
- Keine Superuser-/CreateDB-/CreateRole-/Replication-/BypassRLS-Rechte
- Provisioning bricht bei befülltem Schema oder ungeeigneten bestehenden Rollen ab
- Applicator: `SET ROLE qmtool_migrator` + Verifikation von `current_user`
- Tabellen `users`, `sessions`, `_qm_schema_migrations` gehören dauerhaft `qmtool_migrator`
- Runtime: explizite `SELECT/INSERT/UPDATE/DELETE` nur auf `users` und `sessions`
- Kein `CREATE`, kein DDL, keine Rechte auf der Migrationstabelle, kein Wechsel auf die Migrator-Rolle
- Keine pauschalen `ALTER DEFAULT PRIVILEGES` für zukünftige Tabellen

## Schema-Festlegungen (0001)

- History: `version`, `name`, `checksum`, `schema_fingerprint`, `applied_at`
- UUID-PKs anwendungsseitig (kein DB-Default)
- Username: `UNIQUE (lower(username))` — M8 validiert case-insensitive Kollisionen
- Sessions: `token_hash UNIQUE`, `ON DELETE RESTRICT`, Zeit-Checks
- Deaktivierung: Constraint `users_active_requires_null_deactivated_at`
  - Aktiv ⇒ `deactivated_at` muss `NULL` sein
  - Inaktiv mit `deactivated_at NULL` = historisch unbekannt (bewusst)
  - M6 setzt bei neuer Deaktivierung UTC-Zeit und entfernt sie bei Reaktivierung
  - M8 erfindet keinen historischen Deaktivierungszeitpunkt

## Applicator-Invarianten

1. Versionsnummern lückenlos und eindeutig ab 1; Namen eindeutig
2. Historie ist exakter Präfix der registrierten Kette (Version, Name, Checksumme)
3. SHA-256-Checksummen unveränderbar; unbekannte/neuere/umbenannte Schritte → Abbruch
4. Schema ohne Historie nur als leeres, korrekt provisioniertes Bootstrap-Schema zulässig
5. Deterministischer Schema-Fingerprint (Tabellen, Spalten, Typen, Nullability, Defaults, Constraints, FKs, Indizes)
6. Fingerprint wird mit jeder Migration gespeichert und vor dem nächsten Lauf geprüft
7. Verbindung mit `autocommit=True`; sessionweiter `pg_try_advisory_lock` (kein unbegrenztes Warten)
8. Jede Migration in genau einem `conn.transaction()`: Script + Vertragsprüfung + Fingerprint + History-Insert
9. Fehlschlag ⇒ vollständiger Rollback der aktuellen Migration; frühere Versionen bleiben gültig
10. SQL-Datei als Ganzes über libpq `PQexec` — kein Semikolon-Parser
11. `psycopg` ist normale Dependency — Import wird nicht übersprungen

## Tests und CI

- Statisch ohne PG: Kette, SQL-Verträge, Secrets-Verbot, Gate-Discovery, Bundle-Collect
- Live (`@pytest.mark.postgres`): echtes Provisioning, Login-Rollen nur für CI, Migrator-Pfad
- Skip nur ohne `QMTOOL_PG_DSN`; mit `QMTOOL_PG_REQUIRED=1` ist Skip ein Fehler
- CI-Job `postgres-usermanagement`: `fetch-depth: 0`, Gate gegen PR-Base, Timeout, Postgres 16

## Nicht-Ziele (M3)

PostgreSQL-Repositories (M4), Backend-Routen (M5), Cutover/Backup (M8), Foundation-Rewrite, PG für andere Module.
