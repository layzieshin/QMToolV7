# Packaging (Windows)

## Onedir + ZIP

From the repository root:

```bash
.\.venv\Scripts\python.exe packaging/build_onedir.py
```

Produces:

- `packaging/dist_output/QM-Tool/` — `QM-Tool.exe`, `_internal/`, bundled `prod_ed25519_public.pem` only (no private keys, no license issuer).
- `packaging/dist_output/QM-Tool.zip` — unpack anywhere and run `QM-Tool.exe`.

After PyInstaller, `packaging/verify_customer_bundle.py` and `packaging/verify_bundle_imports.py` run automatically. The build **fails** if private keys, internal issuer tools, local `.env`/database files, J04 evidence artifacts, or critical runtime modules (e.g. `fitz`/PyMuPDF) are missing from the bundle.

The shipped PyQt onedir client targets a **separate backend process**. Configure it at runtime with `QMTOOL_BACKEND_URL` (never baked into the build script). Default when unset: `http://127.0.0.1:8000`.

Runtime data (`storage/`, users DB, logs, session, `license/license.json`) is created **next to the executable** unless `QMTOOL_HOME` is set. Customers import a license via the app settings UI.

## Why onedir (not onefile)

Production builds use **onedir + ZIP**, not a single-file EXE:

- Faster startup (no unpack to `%TEMP%` on every launch)
- More reliable for native DLLs (PyQt6, PyMuPDF, pywin32, cryptography)
- Easier partial updates and fewer antivirus false positives

Legacy `scripts/build_pyqt_onefile.ps1` is deprecated; use `packaging/build_onedir.py` only.

### Customer distribution (without installer)

1. Ship `QM-Tool.zip`; customer unpacks to e.g. `%LOCALAPPDATA%\QM-Tool\` or `C:\Programme\QM-Tool\`
2. Shortcut to `QM-Tool.exe`
3. Import license; runtime data appears next to the EXE (or under `QMTOOL_HOME`)

A Windows installer (Inno Setup / NSIS) can wrap the same onedir folder later — it does not replace onedir.

## Internal license issuer (operators only)

```bash
.\.venv\Scripts\python.exe packaging/build_license_issuer.py
```

Produces `packaging/dist_output/QM-Tool-LicenseIssuer.zip` — **not** for customer distribution. See `tools/license_issuer_gui/README.md`.

## DOCX workflow (Microsoft Word)

Documents imported as DOCX are converted to PDF when the editor phase is completed (before signature/review). This requires **Microsoft Word** on Windows. If you deploy without Word, import documents as PDF instead.

## Customer license

**One-time setup:** generate the production Ed25519 key pair before issuing licenses (the private key is not in the repo). See `tools/internal_license_issuer/README.md` — use `generate_prod_keypair.py generate`, install the public key into `qm_platform/licensing/keys/`, rebuild this bundle, then issue licenses.

Licenses are issued offline with the internal tool (not shipped):

```bash
.\.venv\Scripts\python.exe tools/internal_license_issuer/create_license.py create-license ...
```

Verify before customer delivery:

```powershell
python tools/internal_license_issuer/generate_prod_keypair.py verify-key --private-key-pem path\to\prod_ed25519_private.pem
python tools/internal_license_issuer/generate_prod_keypair.py verify-license --license-json path\to\license.json
```

See `docs/LICENSE_SPEC.md` and `tools/internal_license_issuer/README.md`.

## First login

The default seeded account is `admin` / `admin` (when `usermanagement.seed_mode` is `admin_only`). On first successful login you must set a new password (cannot reuse `admin`).

## Development license

For local development, use `QMTOOL_LICENSE_MODE=dev` (CLI default). Dev mode auto-provisions a signed dev license for `training` and `incident_management` on the local machine. PyQt defaults to `production`; without a customer license the app still starts but licensed modules remain locked.
