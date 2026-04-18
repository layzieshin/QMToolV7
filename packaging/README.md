# Packaging (Windows)

## Onedir + ZIP

From the repository root:

```bash
python packaging/build_onedir.py
```

Produces:

- `packaging/dist_output/QM-Tool/` — `QM-Tool.exe`, `_internal/`, `license/license.json`, and `storage/platform/license/` (prod signing keys generated at build time).
- `packaging/dist_output/QM-Tool.zip` — unpack anywhere and run `QM-Tool.exe`.

Runtime data (`storage/`, `users.db`, logs, session) is created **next to the executable** unless `QMTOOL_HOME` is set.

## First login

The default seeded account is `admin` / `admin` (when `usermanagement.seed_mode` is `admin_only`). On first successful login you must set a new password (cannot reuse `admin`).

## Development license

For local development without a shipped license, run with `QMTOOL_LICENSE_MODE=dev` (CLI default). The PyQt entry sets `QMTOOL_LICENSE_MODE` to `production` unless already set; ship a valid `license/license.json` with the bundle.
