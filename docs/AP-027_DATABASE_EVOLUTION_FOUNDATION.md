# AP-027 Database Evolution Foundation

Status: implementation package on `feature/ap-027-database-evolution-foundation`

## Goal

Establish database version 1 and a single forward-only migration mechanism
before productive records exist. This package covers Documents, Registry, User
Management, Signature, Training, and Incident Management.

## Delivered Scope

- shared migration runner with version history, normalized checksums, schema
  fingerprints, module validators, locking, backup sets, restore, and
  interrupted-run journal;
- one registered `0001_initial.sql` per database owner;
- runtime preflight before repository wiring;
- Database CLI and additive Doctor checks;
- CI migration manifest, immutable-history comparison, fresh-install,
  idempotence, repository-DDL, fixture, backup/restore, and go-live gates;
- operational policy in `docs/DATABASE_EVOLUTION_POLICY.md`.

## Deliberate Limits

- Existing development files under `storage/` are not changed by this package.
- Unknown unversioned structures are blocked, not repaired.
- PostgreSQL, backend transport, multiuser behavior, and Documents feature
  extensions remain outside AP-027.
- No downgrade path is introduced.

## Completion Gate

AP-027 is complete only after:

1. all repository, platform, CLI, architecture, and go-live tests are green;
2. copies of the current development databases have been classified under
   `build/`;
3. a six-database backup/restore drill is green;
4. the PR is integrated and the migration gate is green on `main`.

The Documents multiuser MVP starts only after these gates.

## Development Data Rehearsal

Copy-only rehearsal on 2026-07-31:

- Documents, Incidents, Registry, Signature, and Users matched the V1
  fingerprint and were adopted successfully.
- Their table row counts were identical before and after adoption.
- The current Training database contains additional historical tables and was
  correctly classified as `unknown_unversioned`.
- In a second copy, the old Training file was preserved byte-identically and a
  fresh Training V1 database was created; the resulting six-database set was
  fully `current` with integrity `ok`.
- Files under the repository's real `storage/` directory remained unchanged.

No real Training reinitialization or data takeover is authorized by this
rehearsal.
