# Internal License Issuer



**Not part of the customer application.** This tool signs customer licenses offline.



## First-time setup: production signing key



The customer app bundles only the **public** half of the production key pair:



`qm_platform/licensing/keys/prod_ed25519_public.pem`



There is **no** production private key in this repository (by design). You must create it once before issuing customer licenses.



### Dev key vs production key (do not mix them up)



| Key | Created how | Used for |

| --- | --- | --- |

| **Dev** (`dev-key`) | Auto-generated on first run with `QMTOOL_LICENSE_MODE=dev` under `storage/platform/license/dev_ed25519_private.pem` | Local development only |

| **Production** (`prod-key`) | **You** generate once and store outside the repo | Customer licenses; public key is bundled in `QM-Tool.exe` |



Signing with the dev private key while `key_id` is `prod-key` produces a license that looks valid in the issuer but fails on customer PCs with **`license signature verification failed`**.



The GUI **Key testen** button only checks sign/verify against the **selected** private key. It does **not** check against the bundled `prod_ed25519_public.pem`.



### Generate a new production key pair



Run from the repository root (choose a directory **outside** the repo):



```powershell

python tools/internal_license_issuer/generate_prod_keypair.py generate --output-dir I:\qmtool-license-secrets

```



This writes:



- `prod_ed25519_private.pem` — **secret**; back up securely; never commit or ship to customers

- `prod_ed25519_public.pem` — copy into the repo (next step)



Then:



1. Copy the new public key to `qm_platform/licensing/keys/prod_ed25519_public.pem`

2. Rebuild the customer bundle: `.\.venv\Scripts\python.exe packaging/build_onedir.py`

3. Set `QMT_LICENSE_ISSUER_KEY` (or the GUI path) to your `prod_ed25519_private.pem`

4. Verify the private key matches the bundled public key:



```powershell

python tools/internal_license_issuer/generate_prod_keypair.py verify-key --private-key-pem I:\qmtool-license-secrets\prod_ed25519_private.pem

```



Expected output: `keys match: True`



Before sending a license to a customer, you can also run:



```powershell

python tools/internal_license_issuer/generate_prod_keypair.py verify-license --license-json path\to\license.json

```



Expected output: `signature valid for customer build: True`



If you rotate the production key pair, you must rebuild and redeploy `QM-Tool` to customers and re-issue all licenses with the new private key.



## Recommended: GUI



```powershell

python -m tools.license_issuer_gui

```



Portable build (internal operators only):



```powershell

.\.venv\Scripts\python.exe packaging/build_license_issuer.py

```



See [`../license_issuer_gui/README.md`](../license_issuer_gui/README.md).



## CLI (automation / scripts)



```bash

python tools/internal_license_issuer/create_license.py create-license \

  --type trial \

  --customer-id CUST-001 \

  --issued-to "Example GmbH" \

  --machine-id qmt-xxxxxxxxxxxxxxxx \

  --enable-module training \
  --enable-module incident_management \

  --expires-at 2026-12-31T23:59:59+00:00 \

  --private-key-pem /path/to/prod_ed25519_private.pem \

  --out customer/license.json \

  --out-code customer/license.txt

```



## Private key storage



- Never commit `*.pem` private keys to this repository.

- Store production private keys outside the repo (encrypted), e.g. `I:\qmtool-license-secrets\prod_ed25519_private.pem`.

- Set `QMT_LICENSE_ISSUER_KEY` to the private key path, or pass `--private-key-pem`.



The customer imports `license.json` or the code from `license.txt` in the app settings.



## Troubleshooting



| Symptom | Likely cause | Fix |

| --- | --- | --- |

| `license signature verification failed` on customer PC | Private key used for signing does not match bundled `prod_ed25519_public.pem` (often the dev key was used) | Run `verify-key` and `verify-license`; re-issue with the correct prod private key |

| `machine_id mismatch` | License bound to another PC | Re-issue with the customer's machine ID from Einstellungen → Lizenzverwaltung |

| Key testen OK, customer import fails | Dev/prod key confusion | Run `verify-key` against `prod_ed25519_private.pem` |



Canonical spec: [`docs/LICENSE_SPEC.md`](../../docs/LICENSE_SPEC.md).


