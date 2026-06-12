# Packaging (Windows)

## Onedir + ZIP

From the repository root:

```bash
python packaging/build_onedir.py
```

Produces:

- `packaging/dist_output/QM-Tool/` — `QM-Tool.exe`, `_internal/`, bundled `prod_ed25519_public.pem` only (no private keys, no license issuer).
- `packaging/dist_output/QM-Tool.zip` — unpack anywhere and run `QM-Tool.exe`.

After PyInstaller, `packaging/verify_customer_bundle.py` runs automatically. The build **fails** if private keys or `tools/internal_license_issuer/` appear in the bundle.

Runtime data (`storage/`, users DB, logs, session, `license/license.json`) is created **next to the executable** unless `QMTOOL_HOME` is set. Customers import a license via the app settings UI.

## Customer license

Licenses are issued offline with the internal tool (not shipped):

```bash
python tools/internal_license_issuer/create_license.py create-license ...
```

See `docs/LICENSE_SPEC.md` and `tools/internal_license_issuer/README.md`.

## First login

The default seeded account is `admin` / `admin` (when `usermanagement.seed_mode` is `admin_only`). On first successful login you must set a new password (cannot reuse `admin`).

## Development license

For local development, use `QMTOOL_LICENSE_MODE=dev` (CLI default). Dev mode auto-provisions a signed dev license for `training` on the local machine. PyQt defaults to `production`; without a customer license the app still starts but `training` remains locked.
