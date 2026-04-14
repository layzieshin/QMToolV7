# Documents CLI Reference

This is a practical command reference for the `documents` CLI commands in `interfaces/cli/main.py`.

## Quick Start

Login (all documents commands are session-bound):

Security note:
- Password examples in this file are placeholders.
- In production, use strong credentials provisioned via `init` and hardened user setup.

```bash
python -m interfaces.cli.main login --username admin --password "<strong-password>"
```

Create a document version (starts in `PLANNED`):

```bash
python -m interfaces.cli.main documents create-version \
  --document-id DOC-100 --version 1 \
  --doc-type VA --control-class CONTROLLED --workflow-profile-id long_release
```

Assign workflow roles:

```bash
python -m interfaces.cli.main documents assign-roles \
  --document-id DOC-100 --version 1 \
  --editors editor-1,editor-2 \
  --reviewers reviewer-1 \
  --approvers approver-1,approver-2
```

Start workflow with default profile:

```bash
python -m interfaces.cli.main documents workflow-start --document-id DOC-100 --version 1
```

## Workflow Commands

### Complete Editing (optional signature request payload via CLI args)

If profile transition `IN_PROGRESS->IN_REVIEW` requires signature, pass sign parameters:

```bash
python -m interfaces.cli.main documents editing-complete \
  --document-id DOC-100 --version 1 \
  --sign-input C:/tmp/input.pdf \
  --sign-output C:/tmp/output.pdf \
  --sign-signature-png C:/tmp/signature.png \
  --sign-page 0 --sign-x 100 --sign-y 100 --sign-width 120 \
  --signer-password admin \
  --sign-dry-run
```

### Review

Accept:

```bash
python -m interfaces.cli.main login --username reviewer --password "<strong-password>"
python -m interfaces.cli.main documents review-accept \
  --document-id DOC-100 --version 1
```

Reject (template and/or free text required):

```bash
python -m interfaces.cli.main documents review-reject \
  --document-id DOC-100 --version 1 \
  --reason-template-id TPL-001 --reason-template-text "Missing reference" \
  --reason-free-text "Please add SOP link."
```

### Approval

Accept:

```bash
python -m interfaces.cli.main login --username approver --password "<strong-password>"
python -m interfaces.cli.main documents approval-accept \
  --document-id DOC-100 --version 1 \
  --sign-input C:/tmp/input.pdf \
  --sign-output C:/tmp/output.pdf \
  --sign-signature-png C:/tmp/signature.png \
  --sign-page 0 --sign-x 100 --sign-y 100 --sign-width 120 \
  --signer-password approver \
  --sign-dry-run
```

Reject:

```bash
python -m interfaces.cli.main documents approval-reject \
  --document-id DOC-100 --version 1 \
  --reason-template-text "Insufficient validation evidence"
```

### Abort Workflow

```bash
python -m interfaces.cli.main documents workflow-abort --document-id DOC-100 --version 1
```

### Archive Approved Version

Only `QMB` or `ADMIN` is allowed:

```bash
python -m interfaces.cli.main login --username qmb --password "<strong-password>"
python -m interfaces.cli.main documents archive \
  --document-id DOC-100 --version 1
```

### Annual Validity Extension

```bash
python -m interfaces.cli.main documents annual-extend \
  --document-id DOC-100 --version 1 --signature-present
```

## Document Pool API via CLI

### List by Status

Default status is `PLANNED`:

```bash
python -m interfaces.cli.main documents pool-list-by-status
```

Explicit status:

```bash
python -m interfaces.cli.main documents pool-list-by-status --status APPROVED
```

### Header and metadata

Read/update header:

```bash
python -m interfaces.cli.main documents header-get --document-id DOC-100
python -m interfaces.cli.main documents header-set --document-id DOC-100 --department QC --site HQ
```

Read/update version metadata:

```bash
python -m interfaces.cli.main documents metadata-get --document-id DOC-100 --version 1
python -m interfaces.cli.main documents metadata-set --document-id DOC-100 --version 1 --title "Updated title" --custom-fields-json "{\"topic\":\"sterility\"}"
```

Read central registry projection:

```bash
python -m interfaces.cli.main documents pool-get-register --document-id DOC-100
```

## Runtime Notes

- `documents` module uses dedicated storage at `storage/documents/documents.db` (configurable via module settings).
- Workflow profiles are loaded from `modules/documents/workflow_profiles.json`.
- Events are published to EventBus for lifecycle and workflow decisions.
