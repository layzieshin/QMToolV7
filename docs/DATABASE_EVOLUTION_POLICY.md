# Database Evolution Policy

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

## Productive target runtime (DECIDED)

- Productive runtime persistence is **PostgreSQL only**.
- **No productive SQLite fallback.**
- One PostgreSQL database per installation.
- Separate schema, migrations, and ownership per module.
- No direct cross-schema queries between fach modules.
- Forward-only migrations; no down-migration rollback.
- Rollback after irreversible migration = restore of the **complete** PostgreSQL + Blobstore
  backup set.
- Schema changes require contiguous migration numbering, checksums/fingerprints, advisory
  locking, and readiness/preflight checks (implement in PG00; do not invent unavailable
  operator commands here).

### Target operator posture (planned; not all commands exist yet)

PG00 defines the concrete runner, roles, readiness, and operator commands. Until those
commands are implemented and documented with evidence, do **not** treat them as already
available. Current SQLite-oriented CLI commands below are **Ist/legacy** tooling.

## Ist / legacy SQLite section (import, tests, historical AP-027)

The following rules apply to the **current** SQLite-owned databases used by Documents,
Registry, User Management, Signature, Training, and Incident Management for local/dev,
import, and tests. They are **not** the productive target runtime.

### Version Contract (SQLite Ist)

- Database version 1 is defined exclusively by each module's
  `migrations/0001_initial.sql`.
- New databases are built by the registered migration chain.
- `PRAGMA user_version` and `_qm_schema_migrations` must agree.
- Applied migrations are immutable. Version, name, and normalized SHA-256
  checksum are recorded and checked at every preflight.
- Later schema changes require the next contiguous migration number. Downgrade
  migrations are not supported.
- A database newer than the application, structurally unknown, corrupt, or
  inconsistent is not modified and blocks module wiring.

### Startup And Upgrade (SQLite Ist)

The database preflight runs after module settings are loaded and before any
repository is created.

1. Validate integrity, migration history, schema fingerprint, and module data
   invariants.
2. Acquire the application migration lock.
3. Create a complete backup of every affected database.
4. Record the external migration journal.
5. Execute each database migration transactionally.
6. Repeat integrity, fingerprint, and data validation.
7. Restore the backup set and block startup if any step fails.

An interrupted journal is restored on the next explicit migration attempt. The
recovery run then stops and must be started again deliberately.

### Existing Development Databases (SQLite Ist)

Unversioned databases are adopted only when their structure exactly matches the
registered V1 fingerprint and their data validators pass. Adoption first creates
a backup and then writes version/history metadata. Unknown structures are never
repaired heuristically.

Repository constructors must not create tables, execute migration scripts, add
columns, or backfill legacy structures.

### Operator Commands (SQLite Ist — currently implemented)

```powershell
.\.venv\Scripts\python.exe -m interfaces.cli.main database status
.\.venv\Scripts\python.exe -m interfaces.cli.main database migrate --dry-run
.\.venv\Scripts\python.exe -m interfaces.cli.main database migrate
.\.venv\Scripts\python.exe -m interfaces.cli.main database backups
.\.venv\Scripts\python.exe -m interfaces.cli.main database restore --backup-id "<id>"
```

`restore` validates backup checksums, integrity, database IDs, and configured
target paths. It creates a safety backup of the current set before restoring.

SQLite remains allowed for:

- read-only inventory (INV00)
- one-time import into PostgreSQL
- isolated automated tests

SQLite is **not** allowed as productive runtime fallback.

## Required Change Package (applies to future PostgreSQL schema work and remaining SQLite Ist changes)

Every future schema change must include:

- one new contiguous migration file;
- an updated migration manifest;
- a fixture for the immediately preceding database version;
- upgrade and data-retention coverage;
- fresh-install and idempotence coverage;
- updated target version through the module contribution;
- inclusion of every registered migration in the production bundle;
- green database migration, backup/restore, Doctor, and go-live gates (as applicable).

Run locally (Ist gates; PostgreSQL gates are added by PG00/OPS00):

```powershell
.\.venv\Scripts\python.exe scripts/database_migration_gate.py --output build/database-migration-gate-output.json
.\.venv\Scripts\python.exe scripts/golive_gate.py --output build/golive-gate-output.json
```
