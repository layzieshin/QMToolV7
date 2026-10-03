# AP-029 Checkpoint Protocol

## Status and sequencing

Allowed ledger statuses are `TODO`, `IN_PROGRESS`, `PASS`, `FAILED` and `BLOCKED`. Only one
checkpoint may be active. A green focused test never promotes a parent checkpoint by itself.

A mandatory red/blocked gate stops acceptance and dependent progression. Preserve the first error
and actual results. Safe, already authorized independent diagnostics whose prerequisites hold may
collect the complete actionable finding set; label them `NOT_ACCEPTANCE`. Do not advance the
checkpoint or mutate an unapproved target. `NOT RUN` means never started/reached. Diagnosis cannot
be relabeled as retry, review verdict or PASS.

Bundle engineering findings into one decision-complete repair order. One remediation round is one
bounded change set plus verification, not every assertion or diagnostic. Numeric normal-rework,
escalation, scope-correction and `max_technical_recovery_batches` limits come only from config.

### Authorized engineering recovery

An explicit autonomous mandate includes engineering recovery inside its approved goal, without
renewed consent per finding. Opt-in binds the concrete package, checkpoint and frozen contract for
a new attempt or explicitly approved resume. Config/document changes, positive budget and diagnosis
receipts never opt in old blocked/stopped attempts. Preserve their counters, contracts and evidence
interpretation. Manual stop requires human resume: watchdog `status=aborted` persists
`technical_recovery.user_stop=true`; later completed/session events must not clear it. PLAN registry
registration, immutable Commission fields and exact PRE -> receipt -> repair -> fresh-review PRE
sequencing use the existing owner schemas in `.cursor/runtime/README.md`; perform registration
before scope freeze and preserve budgets on explicitly authorized resume.

Use normal repair first, then existing escalation to consolidate causes. Within a valid bound
commission and configured technical-recovery limit, execute its bounded repair batches; record
normal and recovery use separately without resetting limits. This creates no extra model ladder
or external-review rounds. Local validation grants neither PASS nor execution by itself; bound
authorization and runtime guards remain required. Missing opt-in, exhausted recovery, no justified
new repair approach or a genuine user decision blocks dependent work.

Internal/external substantive FAIL follows the same applicable repair policy. Fix findings and
obtain a fresh independent verdict; never switch reviewer/model to evade FAIL. Correctable stale
or missing evidence requires repair/revalidation, not assumed PASS. Changed reviewed content needs
a fresh verdict; missing real identity, access or independent capability remains a gate.

### Verification and decisions

Rerun failed checks and affected dependencies/regression. Reuse unaffected evidence only with valid
exact-command/input/prerequisite/hash binding; a new binding does not make old results current.
The complete required package/integration matrix must be satisfied before PASS. Explicit full-run
and exact-candidate requirements remain mandatory; avoid unchanged expensive reruns without cause.

Keep criteria and architecture/security/data invariants fixed. Engineering defaults/corrections
needed to meet them are autonomous; preserve necessary amendments before editing. Bundle genuine
product, architecture, trust, credential/permission, cost, target-ownership, destructive-data or
human-acceptance decisions with evidence, options and recommendation. Continue independent authorized
work while dependent action is blocked. Never weaken tests, hide failures, bypass guards, alter
foreign work or substitute technical green for human acceptance.

## Runtime status evidence chain

Canonical owner for workflow/runtime status writes and coordinator status evidence. Follow this
serial order only:

1. native `Write` completes;
2. a separate native `Readback` completes and the actual persisted state equals the expected state;
3. only then record success evidence.

The first denial stops dependent steps; do not continue with readback, PASS evidence, or later
gates. Expose normal single approvals only; do not expand to permanent allow or AlwaysAllow bypass.
Historical denial chains remain distinct from fresh fixture or native evidence.

## Evidence layout

Use `build/ap-029-<checkpoint-id-lower>/` and unique attempt subdirectories. Never overwrite an
earlier result. Each checkpoint records:

- base, start and end HEAD; branch and divergence;
- allowlist, actual changed paths and foreign preserved paths;
- before, pre-review and post-review snapshot JSON;
- `context-manifest.json` built at checkpoint start and validated before resume/reuse;
- commands, exit codes, counts, skips/errors, JUnit and logs;
- first-red and later `NOT RUN` steps;
- reviewer configured/observed model, verdict and findings;
- remediation count;
- final commit SHA/file set when commit permission exists;
- remaining limitations and separately gated actions.

## Immutable checkpoint contract

Before the first source edit, create `checkpoint-contract.md` in the existing checkpoint evidence
root. Record work package/checkpoint, `captured_at`, start HEAD, source document and commit, goal,
use case, in/out scope, invariants, acceptance criteria, planned evidence, and requirement sources.
Compute SHA256 with PowerShell `Get-FileHash` and write `contract_sha256` to the execution journal.

## Context manifest lifecycle

At checkpoint start, build `context-manifest.json` with
`scripts/checkpoint_snapshot.py manifest-build`. Bind package/checkpoint, branch, HEAD, base SHA,
contract path+SHA256, profile path+slug+version+SHA256, exact allowlist, owner hashes, normalized
verification commands, canonical evidence paths below `build/`, evidence SHA-256 values (or honest
missing markers when evidence is not yet present), and the allowlist repository fingerprint. Record
the manifest path in the execution journal.

Before resume or reuse of a completed green checkpoint, run
`scripts/checkpoint_snapshot.py manifest-validate --allow-reuse --verify-command "<exact normalized gate>"`.
`--allow-reuse` without the exact expected verification command(s) fails closed. Validation
recomputes every workspace-derived field, compares recorded evidence SHA-256 values to live bytes,
and never trusts supplied expected/actual pairs from reports. Changed contract, profile/version,
owner content, verification command, base/HEAD, allowlist, repository state, evidence bytes,
missing/malformed manifest, traversal, or forged ignored evidence blocks reuse. A manifest built
before evidence exists records missing evidence honestly and cannot qualify for reuse until a
successor manifest is regenerated after the evidence exists. An unchanged matching manifest may
reuse the checkpoint context without repeating completed green work, re-asking authorization, or
re-reserving reviews. Regenerate the manifest after any material change.

Reviewer and final audit use this snapshot, not only mutable roadmap text. Preserve every prior
snapshot. A material change requires a formal amendment and successor snapshot referencing the old
hash; fachliche behavior, user decision, architecture, public contract, security, or persistence
changes use the applicable HUMAN_GATE. A demonstrated clarification without behavior change may be
handled by the planning process.

## Scope correction

On `SCOPE_CORRECTION_REQUIRED`, do not edit the omitted file. The parent may update the allowlist
within the configured budget only when it is an existing canonical owner directly required by an
approved criterion and the change is small and immediate, with no behavior outside approved criteria
or unapproved public surface, architecture or technology. Preserve an amendment with file,
responsibility, reason, affected criterion and reviewer verification before editing. Authorized
technical recovery uses the same owner/criterion trace within its configured limit. New user
decisions remain Scope Expansion; no incremental erosion of the approved goal or invariants.

## Reviewer handoff

Provide the reviewer only facts and primary artifacts, not the desired verdict:

```text
Review checkpoint <ID> using $verify-reports-and-plan.
Original user plan/request: <verbatim text or repository path>
Plan: docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md
Allowlist: <paths>
Evidence root: <path>
Complete parent report: <verbatim report or repository path>
Before fingerprint: <sha256>
Pre-review fingerprint: <sha256>
Remediation count: <0|1>
Task prefix: [ROLE:checkpoint-reviewer]
Requested model: <selected ladder rung from review_model_fallback>
Return the checkpoint-reviewer output contract including D15 evidence_profile and ladder attempt record.
Do not mutate repository state.
```

Launch the reviewer as the native `checkpoint-reviewer` custom agent in a separate context using the
authorized ladder from `.cursor/agent-system.json` `review_model_fallback`, beginning at attempt 1
`grok-4.7-high`, then `cursor-grok-4.6-xhigh`, `cursor-grok-4.6-high`, and `gpt-5.6-terra-high`
only after explicit prior `UNAVAILABLE` evidence for the same role/review identity. There is no
hidden attempt 0 and no legacy `grok-4.7-xhigh` route. Record each attempt; advance only on
`UNAVAILABLE`, never on substantive `FAIL`. The primary Cursor agent sends the handoff directly,
waits for the result and returns one consolidated report; never ask the user to copy, paste, forward
or relay between agents. Capture `agent_id` from the native Task result. The reviewer does not need shell access or visibility into its own Task id; unavailable self-observation alone is not a content blocker.
Accept Gate E only when `evidence_profile` is
`RUNTIME_ATTESTED` or `CONTROL_PLANE_PINNED` and `reviewer_verdict` is `PASS`. Treat
`CONTROL_PLANE_PINNED` as control-plane binding, never as observed runtime attestation. If
`evidence_profile` is `UNVERIFIED` or fingerprints diverge, Gate E is blocked.
For a package named in the `PILOT00_ORCHESTRATOR_REVIEW` marker only, Gate E may also be accepted
when the label is `INDEPENDENT_ORCHESTRATOR_REVIEW`, the native role was explicitly
`UNAVAILABLE`, and the substitute evidence below is complete. That label is not
`RUNTIME_ATTESTED` and not `CONTROL_PLANE_PINNED`.

Required substitute evidence when the native role is explicitly unavailable: real agent
or task id, separate context, required `author_id`, `implementer_id`, and `reviewer_id`
with the reviewer different from both the author and the implementer, readonly, no
mutation, identical pre/post fingerprints, requested and observed model recorded
separately, contract hash, diff hash, package inside the configured PILOT00 list,
known authorization source, `target_root` equal to `target_root` in that package's
frozen checkpoint contract, and no open human gate combined with verdict PASS.
Reject same author, reviewer equal to implementer, missing implementer id, missing
separate reviewer, mutation, contradictory metadata, wrong package, unknown
authorization, open human gate as PASS, and a foreign target. The marker does not
name one worktree for every package. Step 0 uses the frozen target of this
preparation worktree. Packages A–E use the frozen target of their own later package
worktree. `substitute_attempts_for_role_need` is the already-consumed count for that
role need: zero may pass once, and a missing or already-consumed count fails closed.
One substitute per role need. No new budget counter.

<!-- PILOT00_ORCHESTRATOR_REVIEW_START -->
scope_packages: PILOT00-AUTONOMY-AMENDMENT PILOT00-SETTINGS-PG PILOT00-SERVICE-RELEASE PILOT00-SIGNATURE-RECOVERY PILOT00-TARGET-RECOVERY-ADAPTER PILOT00-LINUX-INTEGRATION
label: INDEPENDENT_ORCHESTRATOR_REVIEW
known_authorization: Orchestrator_Autonomer_Pilotauftrag_20260927.md
target_source: frozen_checkpoint_contract
max_substitutes_per_role_need: 1
runtime_attestation: false
control_plane_attestation: false
global_relaxation: false
<!-- PILOT00_ORCHESTRATOR_REVIEW_END -->

Context-manifest creation requires a resolvable commit base. A planning manifest without evidence
may be valid as an index, but `manifest-validate --allow-reuse` requires at least one bound evidence
artifact as well as the exact expected verification commands; it cannot prove completion without evidence.

AGENT-COST-01 critical final audit and exhausted escalation use
`EXTERNAL_CODEX_BOUND_REVIEW` from `.cursor/agent-system.json`
`external_codex_bound_review.review_route_bindings` for the exact package/checkpoint/review_need
route. PRE computes `bindingRecord`; the coordinator anchors it once in
`workflow-state.external_review.bindingRecord` via the existing metadata writer path; BOUND and
recovery receipt validation reuse that anchored record plus `manifest-validate` (exit 0 and
valid=true). Recovery diagnosis emits `RECOVERY_DIAGNOSIS_READY` / `RECOVERY_PROPOSAL_BOUND` only —
never review `HANDOFF_READY`, `CONTINUE`, or gate/external PASS.
This is not `INDEPENDENT_ORCHESTRATOR_REVIEW`, not a Cursor model ID, and not D15
`RUNTIME_ATTESTED` or `CONTROL_PLANE_PINNED`. Local validators check structure, staleness, and
hash binding only; they do not authenticate external origin or serving model. Missing, stale, or
conflicting handoff evidence blocks the handoff. Diagnose and correct technical binding defects
under the authorized recovery policy; missing trust/access or an unresolved exhausted recovery
requires `BLOCKED_HUMAN`. No Cursor GPT fallback may substitute an external verdict.

<!-- EXTERNAL_CODEX_BOUND_REVIEW_START -->
contract_id: EXTERNAL_CODEX_BOUND_REVIEW
packages: AGENT-COST-01
external_host: codex-chatgpt-authenticated
local_validator_scope: workspace_derived_binding
canonical_evidence_root: build/agent-cost-01/w1/{evidence_attempt}
final_audit_evidence_root: build/agent-cost-01/w3/{evidence_attempt}
final_audit_allowlist_owner: external_codex_bound_review.w3_allowlist_paths
final_audit_base_ref: 4bedcc84cd81a46b6e8802a3a6b2296f9f5f9d5c
dirty_negative_canary_root: build/agent-cost-01/w3/w3-prep-01-dirty-canary-002
<!-- dirty_negative_canary: -001 historical labels-only stub (no hook-result); -002 mandated substitution with genuine HANDOFF_INVALID dirty_tracked_or_index naming all 9 owners -->
dirty_negative_canary_labels: DIRTY_NEGATIVE_CANARY NOT_FINAL_FREEZE NOT_FINAL_AUDIT_PASS
foreign_scope_default: dirty/W1 prefix matching on declared foreign rules only
foreign_scope_final_audit: committed_final_audit exact three path/size/hash bindings; foreign child DENY opt-in here only
final_audit_allowlist_match: exact35 path equality in committed_final_audit; dirty scope keeps prefix allowlist matching
pre_handoff_token: PRE_HANDOFF_READY
bound_review_token: HANDOFF_READY
workspace_fingerprint_source: checkpoint_snapshot.repository_state_sha256
runtime_attestation: false
control_plane_attestation: false
cursor_gpt_fallback: true
cursor_gpt_fallback_after_grok_ladder: true
external_codex_after_cursor_gpt_unavailable: true
substantive_fail_blocks_external: true
<!-- EXTERNAL_CODEX_BOUND_REVIEW_END -->

Exhausted checkpoint rework uses configured escalation and the recovery policy above. For external
handoff, local validation produces `PRE_HANDOFF_READY` in `EXTERNAL_CODEX_PRE_HANDOFF` mode;
then obtain the external result on the bound contract/diff/evidence. Only subsequent
`EXTERNAL_CODEX_BOUND_REVIEW` validation may produce `HANDOFF_READY`. Local validation grants no
checkpoint PASS. Critical packages retain configured direct-external final audit without duplicate audit.

Required reviewer content fields: `agent_name`, `configured_model`,
`requested_model`, `observed_runtime_model`, `observed_reasoning`, `evidence_profile`,
`contradictory_metadata`, `reviewer_verdict` and findings. Parent-owned fields are `agent_id`,
`separate_context`, `pre_fingerprint`, `post_fingerprint` and `mutation_detected`; capture them from
the native Task lifecycle instead of requiring reviewer self-attestation.

## Commit boundary

An explicit macro implementation authorization includes the local checkpoint commit after reviewer
PASS unless the user explicitly opts out. Stage every path by name, compare the staged path list
with the checkpoint allowlist, then commit. A standalone `/execute-gated-macro` invocation keeps
push and PR separately gated. When the macro is invoked by an explicit `/execute-work-package`
request, that outer request authorizes its git-steward checkpoint pushes and final PR/merge subject
to the persisted final gates, hook policy, CI, and branch protection.

`[ROLE:git-steward]` uses native Shell with `working_directory` on every call, pure serial Git
commands, and treats local commit as separate from any later separately authorized push.

## Final report

1. Macro/checkpoint status and reviewer verdict.
2. Branch, base, start/end HEAD and divergence.
3. Exact changed files and responsibilities.
4. Every attempt and gate with evidence.
5. Diff fingerprints before implementation and before/after review.
6. Remediation count and first-red/NOT-RUN classification.
7. Public surfaces, services, entrypoints and persistence changes.
8. Commit SHA/file set or `kein Commit`.
9. Foreign changes preserved.
10. Next authorized action and all actions still requiring permission.
