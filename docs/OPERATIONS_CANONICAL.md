# Canonical Operations Entry

Status: Canonical (P0)
Valid from: 2026-08-21
Canonical index: `docs/DOCS_CANONICAL_INDEX.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`

This is the single operational starting point for daily work, release checks, and incident handling.

## Target operations posture (DECIDED; OPS00 operator contracts in-repo)

First productive deployment target (OPS00 implemented as uninstalled host + operator
contracts; PILOT00 LAN/SCM/cert-store deployment **not** implemented):

- Windows Server first; central on-prem server
- Browser clients on the LAN over Same-Origin HTTPS
- Backend as a controlled Windows service
- Controlled releases (no in-app auto-update as the productive model)
- Maintenance mode, preflight, full backup, migration, healthcheck
- Shared PostgreSQL + Blobstore backup/restore contract
- Restore drill is a pilot gate
- Irreversible migration rollback = restore of the complete backup set (no down-migration)
- Portability export ≠ technical backup; separate readable audit/evidence export
- Protect secrets and license material; never export password hashes, private keys, or session secrets

OPS00-A–F implement the uninstalled host and operator contracts described below. This local
technical contract is not a Windows-SCM, LAN, firewall, certificate-store, packaging, pilot,
human-acceptance, or merge proof; those deployment effects remain PILOT00 or later gates.
Legacy SQLite/desktop commands are retained only in their explicitly marked sections.

## Backend service host (OPS00-A/B; implemented uninstalled contract)

OPS00-A delivers an **uninstalled** local-process backend host (`python -m src.backend`)
with configuration fail-closed behavior, `QMTOOL_HOME` layout expectations, graceful
stop/drain hooks, and the documented Windows service **installation contract** below.
OPS00-B adds **loopback file-PEM HTTPS** on that same host: production refuses plain HTTP,
uvicorn terminates TLS from operator-managed PEM files, and an optional static webclient
dist directory can be mounted on the same origin as `/health` and `/api/v1`. OPS00-B is
**not** deployment qualification: it does not register a Windows service, open firewall
ports, configure LAN ACLs, interact with the certificate store, or prove PILOT00 LAN
deployment. SCM/LAN/ACL/AV/cert-store evidence remains **PILOT00**.

### `QMTOOL_HOME` layout (implemented OPS00 runtime contract)

| Path (under `QMTOOL_HOME`) | Purpose |
| --- | --- |
| `storage/platform/logs/` | Technical platform and audit logs |
| `storage/platform/blobs/` | Productive blob root (wired in OPS00-C backend bootstrap) |
| `license/` | License file (`license.json`) |
| `certs/` | Operator-managed PEM TLS material (paths referenced by env) |
| `backups/` | Sealed PG+Blob backup sets (OPS00-C+) |
| `maintenance/` | Maintenance/update flags (OPS00-D+) |

Production profile (`QMTOOL_RUNTIME_PROFILE=production`) rejects missing DSN, invalid
license mode, unwritable home paths, missing TLS cert/key paths, unreadable or invalid PEM
material, cert/key mismatch, and insecure HTTP-only bind configuration **before**
serving. With valid PEM files the host serves **HTTPS only** (uvicorn `ssl_certfile` /
`ssl_keyfile`); plain HTTP is not started in production. Non-production/local development
may continue to use loopback HTTP with defaults `127.0.0.1:8000`.

Environment variables (see also `.env.example`): `QMTOOL_HOME`, `QMTOOL_BIND_HOST`,
`QMTOOL_BIND_PORT`, `QMTOOL_TLS_CERT_FILE`, `QMTOOL_TLS_KEY_FILE`, `QMTOOL_WEBCLIENT_DIST`
(or `{QMTOOL_HOME}/webclient/dist` when that directory contains `index.html`), PostgreSQL
DSN keys, `QMTOOL_LICENSE_MODE`, `QMTOOL_RUNTIME_PROFILE`. Never commit secrets.
The repository/install-root `.env` is loaded before `QMTOOL_HOME`, operation-lock, bind,
runtime-profile, and TLS decisions. Explicit process-environment values take precedence;
`.env` is not loaded from inside `QMTOOL_HOME`.

Same-origin static fixture: when `QMTOOL_WEBCLIENT_DIST` (or the home-relative dist path)
points at an existing directory containing `index.html`, the backend host mounts it at `/`
without colliding with `/health` or `/api/v1`. This is transport-only static serving for
contract evidence; it is not Vue product work and does not implement WCON00 GAP-16.

OPS00-C implements backup/restore drill, OPS00-D maintenance/update rehearsal abort,
OPS00-E portability/Nachweis export, and OPS00-F `/ready` plus the diagnostic bundle.

### PostgreSQL + blob backup (OPS00-C)

Write-quiescent backup contract:

1. Stop the backend host so in-flight state-changing work drains and the host-running marker is removed.
2. Acquire the installation-scoped exclusive operation lock (`{QMTOOL_HOME}/storage/platform/operation.lock`).
3. Seal one backup set under `{QMTOOL_HOME}/backups/<backup_id>/` containing a whole-database
   custom-format `pg_dump`, a complete blob-tree copy, `manifest.json`, and checksums.

Backend startup fails closed while the operation lock is held. Backup is refused while the
host-running marker is present or the lock is unavailable.
`operation.lock` and `host-running.pid` are exclusive ownership directories. Each acquiring
instance owns a unique child/token and removes only that owned entry; a replacement or foreign
owner remains fail-closed. Explicit `backup_id` values must parse as UUIDs and are normalized
to canonical UUID form.

Release identity file (required): `{QMTOOL_HOME}/release/identity` — its SHA-256 is recorded as
`app_release_fingerprint` in the manifest together with `schema_migration_fingerprint`.

Operator commands (adapter only; no secrets on stdout):

```powershell
.\.venv\Scripts\python.exe -m interfaces.cli.main ops backup
.\.venv\Scripts\python.exe -m interfaces.cli.main ops restore-drill --backup-dir backups/<backup_id>
```

The restore drill runs only through the guarded script invoked by `ops restore-drill`:

```powershell
.\.venv\Scripts\python.exe scripts\run_ops00_restore_drill.py --backup-dir backups/<backup_id>
```

Slot-2 restore targets must use the prefix `qmtool_ops00_restore_`. The drill never restores
into the lab database (`192.168.0.4` / `qmtool_test`) or overwrites the Slot-2 source database
name in place. Live restore evidence is Slot-2 only — not a PILOT00 deployment qualification.
The restore target must not already exist. Only a database created by the current locked restore
may be removed after failure or drill completion, and that cleanup completes before the shared
operation lock is released. A pre-existing prefixed target is preserved.

SQLite `database backups|restore` below remains **Ist/legacy** tooling and is not the productive
PostgreSQL path.

### Maintenance mode and update rehearsal abort (OPS00-D)

Installation maintenance mode blocks state-changing HTTP requests with **503** while
`GET /health` continues to return liveness **ok**. Maintenance state is stored under
`{QMTOOL_HOME}/maintenance/enabled`. Rollback after a rehearsed update **aborts** by restoring
the prior `{QMTOOL_HOME}/release/` tree (including `identity`) and the **complete** sealed
PostgreSQL + Blob backup set from OPS00-C into an isolated Slot-2 database named
`qmtool_ops00_restore_*` (never lab, never in-place overwrite of `qmtool_j04_destructive_test`).
Backend startup remains migration-free and fails closed while the operation lock is held, while a
candidate release is staged without abort, or when the current release fingerprint does not match
the abort-restored expectation. There is no in-app auto-update and no down-migration.
Unknown, malformed, incomplete, unreadable, or non-regular rehearsal-state artifacts block both
backend startup and `/ready`; they are never treated as an absent state.
Before `ops update-rehearsal` start the operator must stop and drain the backend host (the CLI
stops an in-process host automatically); backup remains refused while the host-running marker is present.
Update rehearsal start and abort each hold **one** installation `OperationLock` continuously from
preflight through C `create_backup` / `restore_backup_set` and state persistence. Standalone
`ops backup` still self-locks. There is no second lock path.

Operator commands (adapter only; no secrets on stdout):

```powershell
.\.venv\Scripts\python.exe -m interfaces.cli.main ops maintenance enter
.\.venv\Scripts\python.exe -m interfaces.cli.main ops maintenance exit
.\.venv\Scripts\python.exe -m interfaces.cli.main ops update-rehearsal --candidate-release-dir <path-to-tree-b>
.\.venv\Scripts\python.exe -m interfaces.cli.main ops update-rehearsal --abort --backup-dir backups/<backup_id>
```

The abort restore runs only through the guarded script invoked by `ops update-rehearsal --abort`:

```powershell
.\.venv\Scripts\python.exe scripts\run_ops00_update_rehearsal.py --backup-dir backups/<backup_id>
```

Live abort+restore evidence is Slot-2 only — not a PILOT00 deployment qualification.
`GET /ready` is implemented in OPS00-F as installation ops readiness (not WCON00 GAP-16).

### Windows service installation contract (provider-neutral; documentation only)

This section describes how an operator **would** register the same backend executable with
Windows Service Control Manager (SCM). OPS00-A does **not** execute `sc create`, NSSM,
registry writes, firewall rules, or certificate-store imports.

| Item | Contract |
| --- | --- |
| Executable | `python -m src.backend` from the installation venv, or an equivalent packaged entrypoint invoking the same module |
| Arguments | none required when configuration is supplied via process environment or `.env` in the repository/install root (process environment wins) |
| Working directory | Repository or on-prem install root containing `src/` and dependencies |
| `QMTOOL_HOME` | Absolute writable data root (logs, license, certs, blobstore, backups); service account must have modify rights |
| Secrets | PostgreSQL DSN/password, bootstrap admin password, license material, TLS private key — file permissions or OS secret store; never in HTTP responses or docs examples |
| Service account | Dedicated low-privilege account or `NT AUTHORITY\LOCAL SERVICE` with ACL on `QMTOOL_HOME`, cert files, and log paths only; no interactive desktop requirement |
| Start type | Automatic (delayed) recommended; manual for lab |
| Start timeout | Allow at least 120s for first PostgreSQL schema readiness on cold start |
| Stop timeout | Allow at least 60s for graceful drain before SCM kill |
| Data paths | `{QMTOOL_HOME}/storage/platform/logs/`, `{QMTOOL_HOME}/storage/platform/blobs/`, `{QMTOOL_HOME}/backups/` |
| Certificate paths | `{QMTOOL_HOME}/certs/` or explicit `QMTOOL_TLS_*` paths readable by the service account |
| HTTPS endpoint | Same-origin `https://<host>:<port>/api/v1` with OPS00-B file-PEM TLS on the host (loopback contract evidence; not PILOT00 LAN/cert-store deployment) |

The SQLite desktop commands below remain legacy tooling and are not a productive PostgreSQL
backup, restore, update, export, or service-host path.

## Mandatory Reading Order

1. `docs/DOCS_CANONICAL_INDEX.md` (priority and conflict resolution)
2. `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` (active transition steering)
3. `docs/MODULE_INTEGRATION_POLICY.md` (module onboarding and integration rules)
4. `docs/GUI_SOURCE_OF_TRUTH.md` (active/new GUI source and constraints)
5. `docs/MODULES_DEVELOPER_GUIDE.md` (module ports/settings/events/contracts; Ist marked)
6. `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md` (normative domain invariants and registry contract)
7. `docs/MODULES_USER_GUIDE.md` (operational CLI usage and role-facing flows)

## Daily Start Flow (current Ist)

1. Run health and runtime checks:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database status`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main health`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor --strict` for production-hardening checks (`seed_mode=hardened` and hashed credential store).
2. Confirm login/session behavior with hardened credentials:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main login --username admin --password "<strong-password>"`
3. Verify required module settings visibility:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main settings list-modules`
4. For release/migration windows, execute migration gates from `docs/DATABASE_EVOLUTION_POLICY.md` and `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md`.

## Release Gate Checklist (Blocking)

- Database status reports expected databases as `current` with integrity `ok` (Ist SQLite set today).
- `scripts/database_migration_gate.py` is green and its JSON evidence is attached (Ist).
- Pre/post migration data-quality report attached when Documents data moves.
- No increase in `doc_type=OTHER`.
- Invalid `doc_type/control_class/workflow_profile_id` combinations are `0`.
- Regression suite relevant to changed modules is green.
- Release owner records explicit Go/No-Go decision.
- CI reference: `.github/workflows/ci-gates.yml` enforces regression + migration gate script in automated runs.
- Consolidated local gate command:
  - `.\.venv\Scripts\python.exe scripts/golive_gate.py --output "<evidence-dir>/golive-gate.json"`
  - optional DB-backed checks: add `--documents-db-path "<documents.db>" --registry-db-path "<registry.db>" --baseline-other-count <n>`.

OPS00 additions now required by the package gate: shared PG+blob backup evidence, HTTPS
host checks, maintenance/update rehearsal, guarded restore drill, portability/evidence export,
`/ready`, and diagnostic redaction. PILOT00 still owns SCM/LAN/certificate-store deployment,
packaging and human operational acceptance.

## Database Migration Window (current Ist SQLite tooling)

1. Inspect without changing data:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database status`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database migrate --dry-run`
2. Run the controlled forward migration:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database migrate`
3. Verify:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database status`
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main doctor --strict`
4. List recovery points:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database backups`
5. Restore only under an explicit incident/release decision:
   - `.\.venv\Scripts\python.exe -m interfaces.cli.main database restore --backup-id "<id>"`

The full contract is defined in `docs/DATABASE_EVOLUTION_POLICY.md`
(productive target = PostgreSQL-only; SQLite section is Ist/legacy).

## Data export distinctions (DECIDED; OPS00-E)

- **Technical backup:** full PostgreSQL + Blobstore set for restore (OPS00-C). Not an export ZIP.
- **Portability export:** Admin ZIP with `ops00-portability-v1` manifest, checksums,
  machine-readable allowlisted records, and released artifacts only. Unknown keys and nested
  secret fields fail closed. Never a substitute for backup; `database.dump` is refused.
- **Audit/evidence export:** separate `ops00-evidence-v1` readable Nachweis ZIP of allowlisted
  audit fields. Technical logs remain a separate diagnostic concern (OPS00-F).
- Never export secrets, password hashes, private keys, session tokens, or DSNs.
- Canonical redaction consumes Basic/Bearer credentials, PostgreSQL DSNs, `pass`/`pwd` and
  other secret aliases, including camel-case, composite, namespaced, nested assignments and
  URL-query tokens. Diagnostic output rejects any remaining secret marker; evidence export
  fails closed before creating a ZIP when canonical redaction would change an allowlisted scalar.

Operator commands (adapter only; no secrets on stdout):

```powershell
.\.venv\Scripts\python.exe -m interfaces.cli.main ops export portability --records-file records.json --output-dir exports
.\.venv\Scripts\python.exe -m interfaces.cli.main ops export evidence --audit-file audit-records.jsonl --output-dir exports
```

## Health, readiness, and diagnostic bundle (OPS00-F)

`GET /health` is process **liveness** and remains `ok` while the host can answer. `GET /ready`
is installation **ops readiness** (PostgreSQL reachable, blob root writable, not in
maintenance, no staged update rehearsal, operation lock free, platform migrations current).
It is **not** the WCON00 GAP-16 versioned browser connection contract and is not deployment
qualification. HTTP 200 only when every check is `ok`; otherwise HTTP 503 with the check
payload. Check bodies contain no DSN, password, or key material. TestClient green is not a
restore or PILOT00 deployment proof.

The diagnostic ZIP (`ops00-diagnostic-v1`) is a secret-redacted technical bundle: manifest,
checksums, readiness snapshot, config-key presence booleans, and redacted technical logs.
It does not truncate live logs (`logs-backup` still does). It is not a backup set, not a
portability export, and not a fachliche Nachweisquelle.

Operator commands (adapter only; no secrets on stdout):

```powershell
.\.venv\Scripts\python.exe -m interfaces.cli.main health
.\.venv\Scripts\python.exe -m interfaces.cli.main logs-backup
.\.venv\Scripts\python.exe -m interfaces.cli.main ops diagnostic-bundle --output-dir diagnostics
```

## Registry Projection Recovery Entry

When registry projection drift is suspected:

1. Follow `docs/DOCUMENTS_ARCHITECTURE_CONTRACT.md` section:
   - `Registry projection recovery contract`
2. Capture incident ticket and evidence before/after reconciliation.
3. Re-run verification checks and attach results to release/incident record.
4. Optional drill automation command:
   - `.\.venv\Scripts\python.exe scripts/registry_recovery_drill.py --documents-db-path "<documents.db>" --registry-db-path "<registry.db>" --evidence-dir "<evidence-dir>" --rebuilt-registry-db-path "<rebuilt-registry.db>"`

## Security Defaults

- Use `init` with explicit strong password:
  - `.\.venv\Scripts\python.exe -m interfaces.cli.main init --non-interactive --admin-password "<set-strong-password>"`
- Keep hardened seed mode for production operations.
- Prefer `doctor --strict` (or set `QMTOOL_DOCTOR_STRICT=1`) in release/operational validation runs.
- Treat simple password examples in docs as local dev/smoke only.
- For production-like license validation, run with `QMTOOL_LICENSE_MODE=strict` to disable implicit dev license autogeneration.
- When `QMTOOL_RUNTIME_PROFILE=production`, startup enforces `usermanagement.seed_mode=hardened`.
- Protect license material and secrets in backups and exports.

## Settings Governance

Apply governance classes from `docs/MODULES_DEVELOPER_GUIDE.md` / historical notes in `docs/DEVGUIDE.md`:

- `operational`
- `development`
- `governance_critical`

Do not apply ad-hoc runtime changes for `governance_critical` settings without release control.
