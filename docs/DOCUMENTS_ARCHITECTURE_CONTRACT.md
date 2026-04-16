# Documents Architecture Contract (VA-Aligned v1)

This contract defines the normative domain model for document control.
It is the implementation baseline for compliance with the process instruction.

Related guides:
- `docs/MODULES_DEVELOPER_GUIDE.md`
- `docs/MODULES_USER_GUIDE.md`

## Scope

- Internal status names remain unchanged (`PLANNED`, `IN_PROGRESS`, `IN_REVIEW`, `IN_APPROVAL`, `APPROVED`, `ARCHIVED`).
- Compliance is ensured by explicit invariants, role evidence, and a separate registry model.
- Semantic split is mandatory:
  - `doc_type` = fachliche Dokumentart
  - `control_class` = Lenkungsklasse / Governance strictness
  - `workflow_profile_id` = executable process profile
- The model is split into three levels:
  - Document master
  - Document version
  - Central registry view

## Level 1: Document Master (revision-stable)

| Field | Type | Required | Source | Mutable | Rule profile | State dependency | Invariant | Event-derived | Registry relevance |
|---|---|---|---|---|---|---|---|---|---|
| `document_id` | `string` | yes | manual/system | no | all | none | stable across all versions | no | yes |
| `doc_type` | `enum` (`VA`, `AA`, `FB`, `LS`, `EXT`, `OTHER`) | yes | manual | constrained | all | none | fachliche Dokumentart, nicht Governance-Steuerung | no | yes |
| `control_class` | `enum` (`CONTROLLED`, `CONTROLLED_SHORT`, `EXTERNAL`, `RECORD`) | yes | manual/system | constrained | all | none | steuert Lenkungsregeln, nicht fachliche Art | no | yes |
| `workflow_profile_id` | `string` | yes | manual/system | yes | by `control_class` | none | must exist and match `control_class` | no | yes |
| `department` | `string?` | no | manual | yes | all | none | if set, remains stable across versions unless explicit update | no | no |
| `site` | `string?` | no | manual | yes | all | none | if set, remains stable across versions unless explicit update | no | no |
| `regulatory_scope` | `string?` | no | manual | yes | all | none | if set, remains stable across versions unless explicit update | no | no |
| `register_binding` | `boolean` | yes | system | no | all | none | true for all governed documents | no | yes |
| `created_at` | `datetime` | yes | system | no | all | none | immutable | no | no |
| `updated_at` | `datetime` | yes | system | system | all | none | monotonic increasing | no | no |

## Level 2: Document Version (revision-specific)

| Field | Type | Required | Source | Mutable | Rule profile | State dependency | Invariant | Event-derived | Registry relevance |
|---|---|---|---|---|---|---|---|---|---|
| `document_id` | `string` | yes | system | no | all | none | references existing document master | no | yes |
| `version` | `int` | yes | manual/system | no | all | none | `> 0`, unique with `document_id` | no | yes |
| `title` | `string` | yes | manual | yes | all | none | non-empty | no | yes |
| `description` | `string?` | no | manual | yes | all | none | free text allowed | no | no |
| `status` | `enum` | yes | system | no | all | transition-driven | only valid state-machine transitions | yes | yes |
| `workflow_active` | `boolean` | yes | system | no | all | transition-driven | false in terminal states | yes | no |
| `owner_user_id` | `string` | yes | system | no | all | none | immutable owner identity | no | no |
| `assignments.editors` | `set<string>` | profile-based | manual | controlled* | pre/post constraints | required for controlled documents | no | no |
| `assignments.reviewers` | `set<string>` | profile-based | manual | controlled/full | pre/post constraints | required where review phase exists | no | no |
| `assignments.approvers` | `set<string>` | profile-based | manual | controlled* | pre/post constraints | required where approval phase exists | no | no |
| `edit_signature_done` | `boolean` | yes | system | controlled* | transition-driven | owner role update lock gate | yes | no |
| `valid_from` | `datetime?` | profile-based | system | controlled* | set on release | required when released | yes | yes |
| `valid_until` | `datetime?` | no | manual/system | controlled* | only in released states | must be >= `valid_from` if set | yes | yes |
| `next_review_at` | `datetime?` | profile-based | system | controlled* | only in released states | maintained by yearly extension flow | yes | yes |
| `released_at` | `datetime?` | profile-based | system | controlled* | only in `APPROVED`/`ARCHIVED` | only after approval | yes | yes |
| `review_completed_at` | `datetime?` | profile-based | system | where review exists | after review accept | never before review transition | yes | no |
| `review_completed_by` | `string?` | profile-based | system | where review exists | after review accept | assigned reviewer required | yes | no |
| `approval_completed_at` | `datetime?` | profile-based | system | where approval exists | after approval accept | never before approval transition | yes | yes |
| `approval_completed_by` | `string?` | profile-based | system | where approval exists | after approval accept | assigned approver required | yes | yes |
| `archived_at` | `datetime?` | no | system | all | only on archive | set once | yes | yes |
| `archived_by` | `string?` | no | system | all | only on archive | QMB/Admin or system supersede action | yes | yes |
| `superseded_by_version` | `int?` | no | system | controlled* | set on replacement | links old approved version to new approved version | yes | yes |
| `extension_count` | `int` | yes | system | controlled* | released states only | range `0..3` | yes | no |
| `custom_fields_json` | `json object` | no | manual/event | all | none | non-steering metadata only | optional | no |
| `last_event_id` | `string?` | no | system | all | transition-driven | references latest applied domain event | yes | no |
| `last_event_at` | `datetime?` | no | system | all | transition-driven | monotonic increasing | yes | no |
| `last_actor_user_id` | `string?` | no | system | all | transition-driven | stores effective actor for latest transition | yes | no |

Notes:
- `controlled*` means `CONTROLLED` and `CONTROLLED_SHORT`.
- `custom_fields_json` must never contain status, approval, role assignment, archive, identifier, or registry steering data.

## Level 3: Central Registry View (binding release evidence)

| Field | Type | Required | Source | Mutable | Rule profile | State dependency | Invariant | Event-derived | Registry relevance |
|---|---|---|---|---|---|---|---|---|---|
| `document_id` | `string` | yes | system | no | all | none | one registry entry per document | no | yes |
| `active_version` | `int?` | profile-based | system | all | derived | max one active released version | yes | yes |
| `release_note` | `string?` | no | manual/system | profile-based | release/replace | present for release evidence where required | yes | yes |
| `release_evidence_mode` | `enum` (`WORKFLOW`, `REGISTRY_NOTE`) | yes | profile | all | none | must match effective rule profile | no | yes |
| `register_state` | `enum` (`VALID`, `IN_REVIEW`, `IN_PROGRESS`, `INVALID`, `ARCHIVED`) | yes | system | all | derived | must map from documents status model | yes | yes |
| `is_findable` | `boolean` | yes | system | all | derived | false if archived/invalid | yes | yes |
| `valid_from` | `datetime?` | no | system | all | derived | mirrors active released version | yes | yes |
| `valid_until` | `datetime?` | no | system | all | derived | mirrors active released version | yes | yes |
| `last_update_event_id` | `string` | yes | system | all | transition-driven | immutable trace to source event | yes | yes |
| `last_update_at` | `datetime` | yes | system | all | transition-driven | monotonic increasing | yes | yes |

## Registry ownership rule

- Registry is a **derived projection**, not a second business source of truth.
- Authoritative state owner is the documents state machine (`documents_service`).
- Registry write path is projection-only from documents transitions.
- Direct external status writes to registry are forbidden.

## Registry projection recovery contract

### Operational guarantees

- Registry can be rebuilt from authoritative documents state at any time.
- Registry drift is detectable and must be treated as operational incident.
- Registry recovery must never mutate documents business state.

### Drift detection (required checks)

- Missing registry entries for existing document headers.
- Registry `active_version` not matching latest valid documents projection.
- Registry state/status mismatch against document version state mapping.
- Projection reject events (`domain.registry.projection.rejected.v1`) above threshold.
- Reference automation: `python scripts/migration_gates_documents.py --documents-db-path "<...>" --registry-db-path "<...>"` reports machine-readable drift metrics for the first three checks.

### Rebuild/reconciliation strategy

1. Freeze mutating operations if drift is severe (temporary maintenance mode).
2. Export current documents authoritative snapshot.
3. Recompute registry projection deterministically from documents states.
4. Replace or reconcile registry rows in one controlled operation.
5. Re-run drift detection queries and store evidence.
6. Re-enable mutating operations.

### Automated verification (minimum)

- The **projection write primitive** (`RegistryService.apply_documents_state`) is regression-tested for **deterministic replay** (fixed event envelope) and for reproducing the same row on a **fresh empty registry database** after replay. See `tests/modules/test_registry_module.py` and the mapping in `docs/DOCUMENTS_TEST_COVERAGE.md`.
- This does **not** substitute for full incident drills, backup/restore correlation, or batch replay from live documents data; those remain evidence items for serious deployments.

### Incident runbook minimum

- Incident ticket with timestamps and responsible operator.
- Root cause category:
  - projection consumer failure
  - storage corruption
  - unauthorized projection write attempt
  - partial deployment mismatch
- Recovery action log:
  - rebuild/reconcile start and end time
  - affected document count
  - post-recovery verification result
- Mandatory postmortem note with preventive action.

### Recovery drill automation reference

- Internal drill script:
  - `python scripts/registry_recovery_drill.py --documents-db-path "<documents.db>" --registry-db-path "<registry.db>" --evidence-dir "<evidence-dir>" --rebuilt-registry-db-path "<rebuilt-registry.db>"`
- Evidence output:
  - `registry_recovery_drill_evidence.json` with `drift_before` and `drift_after_rebuild` metrics.
- Drill success criterion:
  - `drift_after_rebuild.metrics.drift_total == 0`.

## Rule profiles (mandatory)

At minimum, these control classes and profiles must exist and be executable:

- `CONTROLLED` with profile(s) like `long_release`.
- `CONTROLLED_SHORT` with profile(s) like `fast_path`.
- `EXTERNAL` with profile(s) like `external_control`.
- `RECORD` with profile(s) like `record_light`.

## document_id identity rule (system-wide)

- `document_id` is **always** a caller-provided fachliche Kennung (e.g. `"VA-2024-001"`, `"AA-HR-005"`).
- The system **never** auto-generates a UUID for `document_id`.
  - Internal artifact IDs, event IDs, and asset IDs may use UUIDs — these are opaque system identifiers.
  - `document_id`, `template_id`, `category_id`, `user_id`, and similar business-visible identifiers are explicitly supplied by the caller.
- This rule applies to all layers: CLI (`--document-id`), API, service, repository, and tests.
- Violation: accepting or generating `uuid4()` for `document_id` is an invariant breach.

## Non-negotiable invariants

1. `document_id` is stable across all versions.
2. `version` is per-document and strictly positive.
3. At most one `APPROVED` version exists per document at any time.
4. New approval must supersede prior approved version deterministically.
5. Review completion fields may only be set after review acceptance.
6. Approval/release fields may only be set after approval acceptance.
7. Archived versions are never active in registry validity.
8. Four-eyes constraints must be provable on transition level (assignment vs actual actor).
9. External documents cannot pass through the same internal change workflow as controlled internal docs.
10. Record/simplified types must not accidentally be forced through full controlled workflow.

## Event contract minimum

For transition-relevant document events, the following must be present and test-asserted:

- Envelope: `event_id`, `occurred_at_utc`, `actor_user_id`, `name`, `module_id`
- Payload: `document_id`, `version`
- For transition evidence: transition-specific fields (`to_status`, `profile_id`, `extension_count`, etc.)

## VA mapping note

The internal status names remain unchanged. A VA mapping table is maintained in docs and tests so that:

- software state remains stable for implementation,
- process-phase traceability remains explicit for audits.

## Migration notes (doc_type split)

### Semantic change

- Old meaning (legacy): `doc_type` was used as governance classification.
- New meaning:
  - `doc_type`: fachliche Dokumentart (`VA`, `AA`, `FB`, `LS`, `EXT`, `OTHER`)
  - `control_class`: governance class (`CONTROLLED`, `CONTROLLED_SHORT`, `EXTERNAL`, `RECORD`)
  - `workflow_profile_id`: concrete executable workflow profile

### Compatibility mapping

| Legacy value (formerly in `doc_type`) | New `doc_type` | New `control_class` | Typical profile |
|---|---|---|---|
| `CONTROLLED` | `OTHER` (fallback) | `CONTROLLED` | `long_release` |
| `CONTROLLED_SHORT` | `OTHER` (fallback) | `CONTROLLED_SHORT` | `fast_path` |
| `EXTERNAL` | `EXT` | `EXTERNAL` | `external_control` |
| `RECORD` | `OTHER` | `RECORD` | `record_light` |

Notes:
- Existing records are backfilled conservatively (`OTHER`) where historical fachliche type is unknown.
- Teams should update `doc_type` to precise business values (`VA`/`AA`/`FB`/`LS`) during data cleansing.

### Breaking-change impact

- **CLI**: `documents create-version` now expects both `--doc-type` and `--control-class`.
- **API**: create/update flows carry both fields; profile compatibility is validated against `control_class`.
- **Tests**: matrix and negative tests must cover `doc_type × control_class × workflow_profile_id`.

### Recommended rollout order

1. Deploy schema/repository migrations.
2. Deploy service/profile compatibility checks.
3. Deploy CLI/API consumers with explicit `doc_type` and `control_class`.
4. Execute data quality pass to replace fallback `OTHER` where fachliche type is known.
5. Run full regression matrix (module + e2e + ui smoke).

## Migration hardening runbook (WP1)

### Responsibilities

- Product/data owner: defines target `doc_type` reclassification for legacy `OTHER` records.
- Technical owner: executes migration checks, profile compatibility checks, and rollout gates.
- Release owner: enforces Go/No-Go decision with test and data evidence.

### Data quality report (mandatory before and after rollout)

Minimum metrics:
- Count of `doc_type=OTHER`.
- Distribution of `control_class`.
- Invalid `doc_type/control_class/workflow_profile_id` combinations.

Reference SQL (SQLite):

```sql
SELECT COUNT(*) AS other_count
FROM document_headers
WHERE doc_type = 'OTHER';

SELECT control_class, COUNT(*) AS count_per_class
FROM document_headers
GROUP BY control_class
ORDER BY control_class;

SELECT h.document_id, h.doc_type, h.control_class, h.workflow_profile_id
FROM document_headers h
LEFT JOIN (
  SELECT 'long_release' AS profile_id, 'CONTROLLED' AS control_class
  UNION ALL SELECT 'fast_path', 'CONTROLLED_SHORT'
  UNION ALL SELECT 'external_control', 'EXTERNAL'
  UNION ALL SELECT 'record_light', 'RECORD'
) p
ON h.workflow_profile_id = p.profile_id AND h.control_class = p.control_class
WHERE p.profile_id IS NULL;
```

### Go/No-Go rollout gates

- `OTHER` count must not increase versus pre-rollout baseline.
- Invalid profile/control-class combinations must be `0`.
- Full relevant regression suite must be green.
- Any gate failure is automatic No-Go with rollback to prior release package.
