# AP-029 SQLite Store Inventory (INV00)

Status: Active inventory (P1) · read-only classification · no migration execution  
Canonical steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`  
Evidence: `build/ap-029-inv00/r1-20260822T104500000Z/sqlite-store-inventory.json`

## Scope

Read-only inventory of **productive SQLite database stores** registered in `origin/main` at
`3484d6d`. No data mutation, schema change, or cutover. Actual PostgreSQL migration remains
PG00/PG01+.

## Product SQLite stores (7)

| Store ID | Default path | Owner | Repository / wiring | Migrations (count) | Disposition | Target checkpoint | Rationale |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| `documents` | `storage/documents/documents.db` | `modules/documents` | `sqlite_repository.py`; J04 backend-owned | 2 | **migrate** | PG01 | Core DMS metadata; AP-029 pilot scope |
| `registry` | `storage/documents/registry.db` | `modules/registry` | `sqlite_repository.py` | 1 | **migrate** | PG01 | Document registry; PG01 bundle with Documents |
| `signature` | `storage/signature/templates.db` | `modules/signature` | `sqlite_repository.py` | 1 | **migrate** | PG01 | Template/asset metadata; PG01 bundle |
| `users` | `storage/platform/users.db` | `modules/usermanagement` | `sqlite_repository.py`; PG live tests separate | 2 | **migrate** | PG00 | Auth/users; PostgreSQL path already established for backend |
| `platform_settings` | `storage/platform/platform_settings.db` | `qm_platform/persistence` | `platform_settings_contribution.py` | 2 | **migrate** | PG00 | Platform settings/integrity; PG foundation |
| `training` | `storage/training/training.db` | `modules/training` | `training_*_repository.py` + `wiring.py` (shared `db_path`) | 1 | **archive** | MOD00 | Legacy SQLite until module follows proven PG/web pattern; no AP-029 pilot blocker |
| `incidents` | `storage/incident_management/incidents.db` | `modules/incident_management` | `sqlite_repository.py` | 1 | **archive** | MOD00 | Frozen legacy boundary; SQLite import/reference only in transition |

### Disposition semantics

- **migrate** — planned PostgreSQL schema under the named checkpoint; SQLite remains Ist/import/tests only until cutover.
- **archive** — retain SQLite for read-only import, inventory, and isolated tests; no productive SQLite expansion; PostgreSQL path deferred to the named checkpoint.
- **discard-or-restart** — non-product ephemeral files (see below); safe to recreate.

## Non-main / non-product references

| Reference | Location | Disposition | Notes |
| --- | --- | --- | --- |
| Container prototype DB | `origin/feature/container-module-prototype` (not in `main`) | **archive** | CB00 No-Code-PASS; branch reference only |
| CI/pytest fixture DBs | e.g. `build/ci-documents.db`, pytest basetemp paths | **discard-or-restart** | Ephemeral; not registered product stores |

## Manifest fingerprint source

Migration chain fingerprints are taken from `qm_platform/persistence/migration_manifest.json`
at INV00 base `3484d6d`. Machine-readable rows including latest migration SHA-256 per store
are in the evidence JSON.

## Explicit exclusions (INV00)

- No SQLite file reads/writes executed in this checkpoint.
- No schema or migration script changes.
- No PG00/PG01 implementation started.
- Blob/asset directories (`artifacts_root`, `assets_root`, etc.) are out of scope for this
  **database store** inventory (Blobstore contract is PG00/OPS00).

## Next authorized action

After INV00 PASS and publication: **PG00** only when explicitly commissioned on fresh
`main`; INV00 does not authorize PG00 start by itself beyond ledger advancement.
