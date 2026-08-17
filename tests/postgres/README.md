# Isolated PostgreSQL 16 destructive test target (J04-M0 M3)

This target is **only** for destructive pytest fixtures. It must never share
host, port, volume/data directory, database, or credentials with runtime/lab
instances such as `qmtool_app`.

## Identity

| Item | Value |
| --- | --- |
| Database | `qmtool_j04_destructive_test` |
| Marker | `public.qmtool_j04_test_cluster_marker.cluster_id = j04_m0_destructive_pg16` |
| PostgreSQL | major version **16** |
| Admin login | dedicated administrative test role (own DB or superuser; `CREATEROLE` + `CREATEDB`) |

## Required local environment

A **separate, fully disposable** PostgreSQL 16 instance must be provided by the
operator. Docker is **not** required. Allowed examples:

- native PostgreSQL 16 installation
- separate VM
- dedicated test server
- a container **only if explicitly chosen**

Generally required:

```text
QMTOOL_PG_TEST_ADMIN_DSN=postgresql://<admin>:<password>@<host>:<port>/qmtool_j04_destructive_test
QMTOOL_PG_TEST_RESET=I_UNDERSTAND_THIS_IS_DESTRUCTIVE
QMTOOL_PG_TEST_EXPECTED_DATABASE=qmtool_j04_destructive_test
```

Optional:

```text
QMTOOL_PG_REQUIRED=1
```

Do **not** point destructive fixtures at `QMTOOL_PG_DSN` / runtime `.env` DSNs.
Secrets stay local and must never be committed.

Notes on tools and variables:

- `psql` is **not** required by the PostgreSQL live pytest classes.
- `pg_dump` / `pg_restore` are required **only** for the M8 backup/restore drill.
- `QMTOOL_PG_TEST_ADMIN_PASSWORD` is **Compose-specific** (optional sketch below),
  not a general M3 prerequisite. The general requirement is a locally set
  `QMTOOL_PG_TEST_ADMIN_DSN`.

## Optional Compose sketch (not approved, not required)

The files `compose.yaml`, `init/`, and `manage.ps1` in this directory are an
**optional, not-yet-approved** convenience sketch. They are **not** the mandated
M3 path and must not be treated as a blocker when Docker is absent.

If an operator explicitly chooses this sketch:

| Sketch item | Value |
| --- | --- |
| Compose project | `qmtool-j04-destructive-pg16` |
| Image | `postgres:16` |
| Bind | `127.0.0.1:55432` |
| Admin login | `qmtool_j04_test_admin` |
| Volume | `qmtool_j04_destructive_pg16_data` |
| Compose-only secret | `QMTOOL_PG_TEST_ADMIN_PASSWORD` |

```powershell
$env:QMTOOL_PG_TEST_ADMIN_PASSWORD = "<local secret>"
docker compose -f tests/postgres/compose.yaml up -d
docker compose -f tests/postgres/compose.yaml ps
docker compose -f tests/postgres/compose.yaml stop
```

Optional helper: `tests/postgres/manage.ps1` (`start`, `status`, `stop`).

Volume deletion / reset is **not** automatic. Explicit operator approval is required.

## CI ephemeral cluster (GitHub Actions)

The `postgres-usermanagement` job in `.github/workflows/ci-gates.yml` provisions an
**ephemeral** PostgreSQL 16 service (`qmtool_j04_destructive_test`) with the marker
from `init/001_test_cluster_marker.sql`. It uses `QMTOOL_PG_TEST_*` variables only;
it is **not** the runtime/lab DSN contract. Local operators must not point a personal
`.env` runtime/lab DSN at this CI sketch.

## Safety

- Destructive fixtures run through `tests/postgres_destructive_guard.py`.
- Helpers connect only with the guard-validated admin DSN from
  `QMTOOL_PG_TEST_ADMIN_DSN`; a freely passed alternate admin DSN cannot bypass
  that boundary.
- Without test DSN + reset opt-in the guard refuses to connect/mutate.
- Preflight checks PostgreSQL 16, database name, cluster marker, ownership /
  admin rights (`CREATEROLE`, `CREATEDB`), and rejects known runtime/lab endpoints.
- Secrets must never appear in logs, pytest IDs, exceptions, or docs.
