# Internal License Issuer GUI (operator tool)

**Not shipped to customers.** Use this GUI to issue signed customer licenses offline.

## Run from source

```powershell
python -m tools.license_issuer_gui
```

## Build portable ZIP (internal only)

```powershell
.\.venv\Scripts\python.exe packaging/build_license_issuer.py
```

Output: `packaging/dist_output/QM-Tool-LicenseIssuer/` and `QM-Tool-LicenseIssuer.zip`.

## One-time setup (production signing key)

The customer application only contains the **public** production key. The matching **private** key is **not** created automatically — you must generate it once before issuing licenses.

See the full walkthrough in [`../internal_license_issuer/README.md`](../internal_license_issuer/README.md#first-time-setup-production-signing-key).

Short version:

```powershell
python tools/internal_license_issuer/generate_prod_keypair.py generate --output-dir I:\qmtool-license-secrets
```

Then copy `prod_ed25519_public.pem` into `qm_platform/licensing/keys/`, rebuild `.\.venv\Scripts\python.exe packaging/build_onedir.py`, and point the GUI at `prod_ed25519_private.pem`.

**Do not** use `storage/platform/license/dev_ed25519_private.pem` — that is the auto-generated **dev** key for local development only.

In the GUI **Einstellungen**:

1. Set the path to `prod_ed25519_private.pem` (or env `QMT_LICENSE_ISSUER_KEY`).
2. Set a default output folder for `license.json` and `license.txt` files.
3. Click **Key testen** — confirms the selected private key signs correctly (roundtrip only).
4. Run on the command line (recommended before first customer delivery):

```powershell
python tools/internal_license_issuer/generate_prod_keypair.py verify-key --private-key-pem I:\qmtool-license-secrets\prod_ed25519_private.pem
```

`keys match: True` means your private key matches the public key bundled in the customer build.

## Issue a license

1. Customer sends **Maschinen-ID** from QM-Tool → Einstellungen → Lizenzverwaltung.
2. Choose a preset (Trial 30/90, Voll-Lizenz, Nur Training Trial).
3. Fill `issued_to`, `customer_id`, paste `machine_id`.
4. Select enabled modules (tags from `core_license_tags()`).
5. Click **Lizenz erstellen** — files are written to the output folder.
6. Optional check before sending:

```powershell
python tools/internal_license_issuer/generate_prod_keypair.py verify-license --license-json path\to\license.json
```

7. Send `license.json` or the code from `license.txt` to the customer for import.

## Module tags vs signing key

- **Module access** is controlled by `enabled_modules` in one license file (e.g. `training`).
- **`key_id`** identifies which public key validates the signature (`prod-key` for customers).
- You do not need a separate private key per module.

## CLI alternative

See [`../internal_license_issuer/README.md`](../internal_license_issuer/README.md).
