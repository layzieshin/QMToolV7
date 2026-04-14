# Release Readiness (Go/No-Go)

Status: Legacy/History (P2)  
Canonical replacement: `docs/DOCS_CANONICAL_INDEX.md` and P0 docs

This file is the operational checklist for final release approval.

Primary gate commands:

- `python scripts/golive_gate.py --output "<evidence-dir>/golive-gate.json"`
- `python scripts/migration_gates_documents.py --documents-db-path "<documents.db>" --profiles-path "modules/documents/workflow_profiles.json" --baseline-other-count <n>`
- `python scripts/registry_recovery_drill.py --documents-db-path "<documents.db>" --registry-db-path "<registry.db>" --evidence-dir "<evidence-dir>" --rebuilt-registry-db-path "<rebuilt-registry.db>"`

## Required Technical Conditions

- Central settings governance enforcement is active in `qm_platform/settings/settings_service.py`.
- CLI and GUI settings paths both require explicit acknowledge semantics for `governance_critical` keys.
- License integration supports new licensed modules via runtime contract discovery (`core_license_tags()`).
- Production startup blocks unsafe seed mode when `QMTOOL_RUNTIME_PROFILE=production`.
- CI gate workflow exists and is green (`.github/workflows/ci-gates.yml`).

## Required Evidence Artifacts

- `golive-gate.json` from `scripts/golive_gate.py` with `"ok": true`.
- Migration gate output JSON (no increase of `doc_type=OTHER`, invalid combinations = `0`).
- Recovery drill evidence (`registry_recovery_drill_evidence.json`) with drift reduced to `0` on rebuilt registry.
- Relevant regression test logs for touched modules/interfaces.
- Explicit release owner decision record.

## Go/No-Go Decision Rule

- **GO** only if all required technical conditions are met and all evidence artifacts are complete and green.
- **NO-GO** if any blocking gate fails or evidence is missing.

## Operational Notes

- For production-like license validation, run with `QMTOOL_LICENSE_MODE=strict`.
- For production runtime hardening checks, run with `QMTOOL_RUNTIME_PROFILE=production` and `doctor --strict`.
