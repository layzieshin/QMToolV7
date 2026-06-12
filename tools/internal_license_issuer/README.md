# Internal License Issuer

**Not part of the customer application.** This tool signs customer licenses offline.

## Private key storage

- Never commit `*.pem` private keys to this repository.
- Store production private keys outside the repo (encrypted), e.g. `../qmtool-license-secrets/prod_ed25519_private.pem`.
- Set `QMT_LICENSE_ISSUER_KEY` to the private key path, or pass `--private-key-pem`.

## Usage

```bash
python tools/internal_license_issuer/create_license.py create-license \
  --type trial \
  --customer-id CUST-001 \
  --issued-to "Example GmbH" \
  --machine-id qmt-xxxxxxxxxxxxxxxx \
  --enable-module training \
  --expires-at 2026-12-31T23:59:59+00:00 \
  --private-key-pem /path/to/prod_ed25519_private.pem \
  --out customer/license.json \
  --out-code customer/license.txt
```

The customer imports `license.json` or the code from `license.txt` in the app settings.
