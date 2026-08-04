# J03 Workflow Engine Capability Matrix

Generated for J03-R1 / R1.1 against the existing Documents workflow engine.

| Runtime step | Engine entry | Evaluated role/assignment | Decision policy | Signature | Four-eyes | Notes |
|---|---|---|---|---|---|---|
| Workflow start | `start_workflow` | assignment presence via profile flags | none | none | none | Not a profile transition; document status becomes `IN_PROGRESS` |
| Complete editing | `complete_editing` | editors/owner/privileged | `ONE_OF_POOL` semantics | `IN_PROGRESS-><next>` via `signature_required_transitions` | no | First enabled runtime transition from `IN_PROGRESS` |
| Accept review | `accept_review` | reviewer assignment set | `ONE_OF_POOL` | `IN_REVIEW->...` | no | |
| Accept approval | `accept_approval` | approver assignment set | `ONE_OF_POOL` | `IN_APPROVAL->APPROVED` | profile/transition-derived `four_eyes_required` | Reviewer may not approve same version |
| Reject review/approval | reject_* | assignment set | n/a | none | none | Returns to `IN_PROGRESS` |

## Relational vs runtime vocabulary (R1.1)

- Relational storage uses start status `DRAFT`
- Runtime engine / `workflow_profile_json` / `DocumentVersionState` use `IN_PROGRESS`
- Translation occurs only in `modules/documents/workflow_profile_runtime_adapter.py` via `WorkflowProfileVersionDefinition.to_runtime_profile()`
- Existing snapshots are never rewritten during upgrade

## Storage rules derived from this matrix

- Allowed transition statuses (relational): `DRAFT`, `IN_REVIEW`, `IN_APPROVAL`, `APPROVED`
- `IN_PROGRESS` is legacy-only and normalized to `DRAFT` before storage
- Allowed decision policy values stored by J03: `ONE_OF_POOL` (and `NONE` where no pool decision applies)
- `ALL_ASSIGNED` is rejected until a later package implements it
- `deadline_seconds` and `revoke_if_changed=true` are rejected because the current engine does not evaluate them
- `required_role` must match the engine bucket for the transition (`EDITOR`/`REVIEWER`/`APPROVER`)
