# Cursor Workflow Runtime

This directory stores small local state for the Cursor-native work-package workflow. It is not
fachliche documentation and must not replace the owning `docs/AP-*` specification, execution
journal, final report, or Git history.

`workflow-state.json` and `*.log` are local and ignored. New worktrees copy
`workflow-state.template.json` once when no local state exists. Hooks may read the local state;
skills update it directly at verified transition points. No script in this directory implements a
workflow engine or launches agents.

## State contract

Required status values:

`IDLE`, `RUNNING`, `BLOCKED_HUMAN`, `DONE`

Required phases:

`PLAN`, `IMPLEMENT`, `REVIEW`, `REWORK`, `ESCALATION_REVIEW`, `CHECKPOINT_GIT`,
`FULL_REGRESSION`, `FINAL_AUDIT`, `FINAL_GIT`, `NEXT_PACKAGE`

Required fields:

- `status`, `work_package`, `base_branch`, `work_branch`
- `phase`, `checkpoint`, `rework_count`, `final_rework_count`
- `escalation_used`, `human_gate`, `last_green_commit`, `next_action`, `updated_at`
- `work_package_path`, `execution_journal_path`, `final_report_path`
- `external_review.status`, `external_review.round`, `external_review.reviewed_head`,
  `external_review.blocking_findings`, `external_review.last_checked_at`,
  `external_review.bindingRecord`, `external_review.recovery_proposal_bound`
- `gates.full_regression_pass`, `gates.final_audit_pass`, `gates.ci_pass`

`updated_at` uses UTC ISO 8601. Set `human_gate=true` with `status=BLOCKED_HUMAN`. A manual Cursor
stop is represented by the hook input `status=aborted`; the stop hook then emits no follow-up.

External-review statuses:

- `NOT_REQUESTED`: enabled provider has not yet been attempted for the current final-PR lifecycle.
- `PENDING`: the hook atomically reserved exactly one bounded request while authorizing it; a
  resumed coordinator waits for that result and never resends the same round.
- `PASS`: no blocking finding on `reviewed_head`; it is stale if PR head changes.
- `FINDINGS`: findings await/failed independent triage or confirmed rework is open.
- `STALE`: the PR head changed after the recorded review.
- `BOUNDED_COMPLETE`: all configured Codex rounds were consumed, the last confirmed findings were
  repaired, and full regression, fresh final audit and CI passed on the resulting unreviewed head.
  It requires `round=max_review_rounds`, `reviewed_head=null`, no open findings and journaled repair
  evidence; it explicitly is not an external PASS.
- `UNAVAILABLE`: bounded wait ended without a usable review.
- `LIMIT_REACHED`: provider explicitly reported exhausted review quota.
- `DISABLED`: external review is disabled for this lifecycle.

With otherwise green internal gates, only `PASS` on the current PR head, `BOUNDED_COMPLETE`, `UNAVAILABLE`,
`LIMIT_REACHED`, and `DISABLED` are mergeable. `NOT_REQUESTED` while enabled, `PENDING`,
`FINDINGS`, `STALE`, missing or unknown values fail closed. Numeric limits and provider identities
come only from `.cursor/agent-system.json`.

Keep requirement sources, risk matrices, contract bodies and review comments in the owning
AP/evidence documents, not runtime JSON. This file remains resume/gate state only.

## Coordinator operational sequencing (registry + hooks)

During PLAN, autonomously install complete verified `review_route_bindings` records in the existing
`.cursor/agent-system.json` owner from the approved package contract. Include this exact metadata
owner in the checkpoint allowlist before scope freeze; registration is covered by the named
autonomous mandate and requires no new approval per package. Preserve unrelated records and policy.
Register `recovery_diagnosis` plus the subsequent review route required by the existing review policy,
for the actual package/checkpoint, before contract/profile/manifest hashes or Commission are frozen.
Run `EXTERNAL_CODEX_ROUTE_PREFLIGHT` with each exact package/checkpoint/review_need; an unregistered
route remains denied. Do not copy historical AGENT-COST-01/W3 facts or add fallback routing. Normal implementer
Task ingress requires RUNNING state, the canonical role and existing model/identity validation,
not an external-review registry entry. If migration is interrupted, preserve the source tree and
perform only explicit narrow config recovery on the registry owner; never switch hooks off to
bypass validation. PRE computes
`bindingRecord`; the coordinator anchors it once in `external_review.bindingRecord` through the
existing metadata writer path (journal → full state → separate readback). BOUND and recovery receipt
validation reuse the anchored state record plus existing `manifest-validate`; they do not accept
payload seal replacement or grant review PASS/CONTINUE/commit privilege.

## Authorized engineering recovery

`technical_recovery` is disabled by default; no automatic migration of old blocked/stopped attempts.
At a new explicitly autonomous package/checkpoint or explicitly approved resume, finish registry
preflight, freeze the contract and build its manifest against the final profile, then create one
commission bound to package, checkpoint, target, branch and contract. Initialize counters only for
a genuinely new IDLE/DONE package; blocked/aborted attempts retain their counters and batch history. Record user authorization, repair allowlist
and existing counter floors. Preserve its hash, old counters and evidence interpretation; a positive
`defaults.max_technical_recovery_batches` alone grants nothing.

Lifecycle: complete diagnostic inventory -> bounded `TECHNICAL_RECOVERY_PROPOSAL` within the commission
-> hash-bound proposal receipt -> guarded `REWORK` -> independent review -> normal batch closeout.
The existing `recovery-policy.ps1` owns atomic reservation in the same runtime state. Its batch limit
comes only from config. Normal counters remain `rework_count`/`final_rework_count`; retain historical
regular/exceptional fields only when already present. Batch outcome moves from `IN_PROGRESS` to
`FAILED` or `REPAIRED`; closed batches cannot replay. Before a fresh independent review, the coordinator
records the new validated PRE binding, phase `REVIEW`/`FINAL_AUDIT` and
`external_review.recovery_proposal_bound=false` together, retaining the batch history. Changing an
evidence-attempt name never resets that history. Only a genuinely completed checkpoint may archive
its history and initialize the next approved checkpoint. `technical_recovery.user_stop` prevents
automatic continuation. An actual watchdog `status=aborted` atomically persists `user_stop=true`
for enabled RUNNING recovery without consuming a batch/followup or changing evidence. Later session
and completed events remain stopped; only an explicit user resume permits the coordinator to clear
that flag through the existing metadata writer, preserving all counters and history. Do not invent
parallel state, approval fields or counters. Follow the schema
and checkpoint protocol for exact validation; local receipt validation alone grants no PASS.

Internal/external FAIL share the repair policy. Missing opt-in, genuine user decisions or exhausted
unresolved recovery remain gated; authorized diagnosis never grants checkpoint/Git advancement.

### Recovery field schemas (existing owners)

All artifact paths below are target-relative, non-redirected paths; SHA256 values bind exact bytes.
The coordinator writes metadata with journal -> full state -> separate equality readback. These
local bindings do not authenticate human/reviewer origin or serving models.

- Registry: `external_codex_bound_review.review_route_bindings[package_id][route_key]` contains
  `package_id`, `checkpoint_id`, `review_need`, resolvable commit `base_ref`, nonempty
  `allowlist_paths`, `verification_commands`, `scope_mode`, and `evidence_path_template` with
  `root`, `contract_file`, `manifest_file`. For `recovery_diagnosis`, use
  `review_need=RECOVERY_DIAGNOSIS`, `purpose=diagnosis`, `scope_mode=dirty`, no ladder history.
  A subsequent `CHECKPOINT_ESCALATION` record uses `scope_mode=dirty`,
  `ladder_role=checkpoint-reviewer`, `require_complete_ladder=true`; its PRE still requires the
  real configured UNAVAILABLE ladder evidence. An already-required `critical_final_audit` uses
  `review_need=FINAL_AUDIT`, `scope_mode=committed_final_audit`, `direct_external=true`,
  `forbid_ladder_history=true`. Recovery never changes which review route is required.
- Immutable commission JSON: `kind=AUTONOMOUS_TECHNICAL_RECOVERY`, nonempty concrete
  `user_authorization`, strict `allow_technical_repair=true`, `package_id`, `checkpoint_id`,
  absolute `target_root`, `branch`, `contract_sha256`, exact `repair_allowlist`, and `counter_floor`
  containing current `rework_count`/`final_rework_count` and every existing historical
  `regular_rework_count`/`exceptional_count`. Preserve this file/hash for the checkpoint.
- Runtime `technical_recovery`: strict `enabled=true`, `user_stop=false` only for authorized
  initialization/resume, `commission_path`, `commission_sha256`, `batches=[]` and
  `active_batch_id=null` only on first opt-in. Existing batches/counters never reset on new PRE,
  receipt or resume. The shared writer adds batches with `id`, `commission_sha256`, `proposal_path`,
  `proposal_sha256`, complete `bindingRecord`, `counters`, `followup_count`, `outcome=IN_PROGRESS`.
- Consolidated proposal JSON: `kind=TECHNICAL_RECOVERY_PROPOSAL`,
  `decision=REPAIR_WITHIN_COMMISSION`, strict `diagnosis_complete=true`,
  `requires_user_decision=false`, `changes_security_or_permissions=false`, `material_amendment=false`;
  exact `package_id`, `checkpoint_id`, `contract_sha256`, `manifest_sha256`, `diff_sha256` from
  validated Recovery PRE; nonempty `findings` of `{id,cause,repair,evidence_key}`, `repair_paths`
  inside both Commission and manifest allowlists, and nonempty `verification_commands` from the
  binding. Findings reference actual hash-bound manifest evidence. A technical label cannot
  override a known human/security decision.
- Evidence: existing `failed_review_junit` binds `failed-junit.xml` with failures or errors; or
  `failed_command_result` binds `failed-command.json` containing `kind=FAILED_COMMAND`, nonempty
  `command`/`context`, integer nonzero `exit_code`, strict `secrets_redacted=true`. These are failed
  diagnostic results, never review PASS. Existing manifest/profile/diff verification still applies.
- Receipt: existing recovery handoff identity/counters plus `result_kind=RECOVERY_PROPOSAL`,
  `proposal_path`, `proposal_sha256`; first obtain `RECOVERY_DIAGNOSIS_READY` from
  `EXTERNAL_CODEX_RECOVERY_PRE_HANDOFF` and anchor its complete `bindingRecord`. Only then invoke
  `EXTERNAL_CODEX_RECOVERY_RECEIPT`. Its reserved batch permits bounded REWORK under the Commission,
  not a gate verdict. After repair and affected gates, build a fresh candidate manifest and run
  the normal review PRE with a new evidence attempt. Anchor only its complete returned record,
  clear `recovery_proposal_bound`, and retain the history; never synthesize a record containing
  only `review_need`. Fresh independent review remains required.

## PILOT00 review substitute

`INDEPENDENT_ORCHESTRATOR_REVIEW` is not a `status` value. Live status stays
`IDLE`, `RUNNING`, `BLOCKED_HUMAN`, or `DONE`. The substitute is evidence for a
listed PILOT00 package after an explicit native-role `UNAVAILABLE`. It does not
attest `RUNTIME_ATTESTED` or `CONTROL_PLANE_PINNED`.

## Document integration

Use the existing flat AP structure under `docs/`. Prefer existing ledger/evidence/final sections in
the owning AP document or its established companion report. Do not create
`docs/development/work-packages/`, a second roadmap, or a second ADR hierarchy.
