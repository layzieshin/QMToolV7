---
name: execute-work-package
description: Execute or resume one approved QMTool work package through isolated checkpoints, independent reviews, bounded rework, gated Git operations, final regression, final audit, PR, and merge.
disable-model-invocation: true
---

# Execute Work Package

Manual invocation only: `/execute-work-package <WP-ID or package path>`.

This skill coordinates Cursor-native agents; it is not a workflow engine. Persist transition facts
in `.cursor/runtime/workflow-state.json` and evidence in the existing AP/report structure. Read
`.cursor/agent-system.json`, `AGENTS.md`, Rules 00–02, P0 documents, the master roadmap, active
transition plan, owning package, and any package-specific protocol such as
`execute-gated-macro/references/checkpoint-protocol.md`.

For AP-029 checkpoints, `/execute-gated-macro` is the single checkpoint-execution owner. Invoke it
for the IMPLEMENT/REVIEW/REWORK/CHECKPOINT_GIT loop and use this skill only as the outer
start/resume, full-regression, final-audit, and final-Git lifecycle. The generic checkpoint loop
below applies only when no package-specific checkpoint owner exists; never run both paths for the
same checkpoint.

## Start or resume

1. Locate the approved package in the existing flat `docs/AP-*` structure. Requirements and
   architecture must already be decision-complete; otherwise use `/maintain-roadmap`.
2. Require one non-base work branch/worktree for exactly this package. Preserve foreign changes.
3. If state is `RUNNING`, resume its exact phase/checkpoint/`next_action`. Never reimplement a
   checkpoint whose journal verdict and commit are green.
4. Otherwise initialize the small state contract from `.cursor/runtime/README.md`:
   `status=RUNNING`, `phase=PLAN`, rework counters zero, gates false, package/branch/document paths,
   and a concrete `next_action`.
5. Use existing ledger/execution/final sections in the owning AP or its established companion
   report. Add compact sections there only when missing; store decisions and evidence, not chat
   transcripts.
6. Validate the package's `planning_risk_level`, Requirement Traceability, Risk-to-Evidence,
   cross-checkpoint seams, Package Integration Scenario, and `plan_challenge_status` against
   `planning_quality` in `.cursor/agent-system.json`. For a new decision-ready package whose risk
   profile requires it, invoke the configured `[ROLE:plan-challenger]` flow from
   `/maintain-roadmap`; it is not READY until that bounded flow is resolved. Do not retroactively
   re-plan completed or already-started checkpoints; apply V2 contracts prospectively from the next
   not-started checkpoint.

## Checkpoint loop

Process checkpoints serially unless independent read-only exploration is clearly safe. Observe the
configured parallel-worker limit and never overlap edits, shared schemas/interfaces/migrations, or
dependent state changes.

### FREEZE CHECKPOINT CONTRACT

Before the first source edit, write `checkpoint-contract.md` in the existing checkpoint evidence
directory. Include work-package and checkpoint IDs, UTC capture time, start HEAD, source document
and source commit, goal, concrete use case, in/out scope, architecture invariants, acceptance
criteria, planned evidence, and relevant requirement sources. Compute SHA256 with PowerShell
`Get-FileHash` and record `contract_sha256` in the execution journal before invoking implementer.
Do not add an orchestration program for this operation.

Preserve the snapshot. If the contract must change, keep the old file, classify the change, record
a formal plan amendment, and create a successor snapshot referencing it. A demonstrated
clarification without behavior change may use the planning process; a material change to fachliche
behavior, a user decision, architecture, public contract, security, or persistence requires the
applicable `HUMAN_GATE`. Never silently edit acceptance criteria after implementation begins.

### IMPLEMENT

1. Set `phase=IMPLEMENT`, current checkpoint, and concrete `next_action`.
2. Invoke the custom agent with a task beginning `[ROLE:implementer]`.
3. Supply the frozen contract path and SHA256, original package, in/out scope, invariants,
   acceptance criteria, allowlist, targeted commands, current status/diff, amendments, scope
   corrections, and attempt number.
4. Require changed files/responsibilities, behavior, exact tests/results, limitations, and open
   questions. The implementer makes no Git writes and cannot grant PASS.
5. If implementer returns `SCOPE_CORRECTION_REQUIRED`, verify before edit that every named file is
   an existing canonical owner omitted from the allowlist, is directly required by an approved
   criterion, adds no behavior/public surface/architecture/technology, and is small and immediate.
   Within the configured scope-correction budget, amend allowlist/evidence once and re-invoke the
   implementer. Otherwise classify it as Scope Expansion and use normal planning/HUMAN_GATE.

### REVIEW

1. For the first review set `rework_count=0`, `phase=REVIEW`.
2. Capture the complete diff and pre-review repository fingerprint.
3. Invoke a fresh custom agent with a task beginning `[ROLE:checkpoint-reviewer]`.
4. Supply frozen checkpoint contract/hash, preserved amendments, scope corrections, architecture
   rules, complete diff, implementer report, relevant tests and primary evidence. The reviewer
   independently inspects and reruns relevant tests.
5. Require per-criterion PASS/FAIL with evidence plus Contract Integrity, Moving Goalposts,
   Architecture Compliance, Regression Risk, Scope Compliance/Correction, affected seam evidence,
   Test Quality, Use Case Verification, fingerprints, and overall `PASS` or `FAIL`.
6. Limit each reviewer instance to the verification-pass budget in config. In a rework review, prior failed
   findings and their relevant regression are primary. A newly noticed issue blocks only when it
   violates an existing acceptance criterion, demonstrates a realistic security/data-integrity
   bypass, or was introduced by the rework. Other hardening ideas are journaled as non-blocking
   follow-ups and do not trigger another rework.

### REWORK AND ESCALATION

- Each normal `FAIL` consumes one `defaults.max_checkpoint_reworks` unit. Send only the reviewer's
  minimal order to `[ROLE:implementer]`, then run a fresh normal review.
- When that configured budget is exhausted and review still fails, set
  `phase=ESCALATION_REVIEW`, `escalation_used=true`, and invoke `[ROLE:escalation-reviewer]` up to
  `defaults.max_escalation_reviews` with the frozen contract/hash, amendments, scope corrections,
  architecture, complete diff,
  tests, all findings, and all reworks.
- Escalation `PASS` advances the checkpoint. Escalation `FAIL` permits no further implementation:
  set `status=BLOCKED_HUMAN`, `human_gate=true`, preserve its diagnosis/evidence/options, and stop.

Do not reset a counter, disguise retries as diagnostics, weaken assertions, add hidden fallback
paths, or continue after an unexplained failure. A material new blocker consumes the already
defined rework budget; renaming it does not create another budget or recursive reviewer loop.

### CHECKPOINT PASS

Only after independent reviewer or escalation-reviewer `PASS`:

1. Append compact journal evidence: attempts, commands/results, verdicts, final PASS proof.
2. Set `phase=CHECKPOINT_GIT` and `next_action` to the exact Git action.
3. Invoke `[ROLE:git-steward]`. It verifies exact paths, commits with package/checkpoint ID, and
   pushes the work branch.
4. Record commit SHA in the journal and `last_green_commit`; reset checkpoint rework/escalation
   fields; then start the next incomplete checkpoint.

## Finalization

After every checkpoint is green:

1. Run the package's Integration Scenario across all relevant checkpoint seams, or verify the
   planned justified `N/A`. Record realprocess/integration evidence before full regression.
2. Set `phase=FULL_REGRESSION`; invalidate all final gates.
3. Run the complete relevant regression and all applicable package/architecture/build gates from
   P0 and the owning package. This repository currently has no linter/typechecker; mark those N/A
   rather than inventing tools.
4. Use Cursor Agent Review once before final audit for substantial changes when available. For
   security/auth/permission changes, additionally use the available Security Review. These are
   signals, not substitutes for checkpoint review.
5. Write the compact work-package completion report with execution path, requirement sources,
   HIGH-risk evidence, package integration result,
   changed files, exact verification, data/API/contract effects, limitations, debt, and scope.
6. Set `gates.full_regression_pass=true` only when integration/N/A, full regression, and applicable
   package/architecture/build gates are green.

## Fresh final architect audit

1. Set `phase=FINAL_AUDIT`.
2. Invoke a fresh `[ROLE:roadmap-architect]` in `FINAL_AUDIT` mode with original package,
   requirement sources, frozen contracts/amendments, checkpoints, journal, full base-branch diff,
   HIGH-risk and package-integration evidence, regression evidence, architecture rules, and final report.
3. Accept only `FINAL_PASS` or `FINAL_FAIL`.
4. On `FINAL_FAIL`, issue its concrete bounded order to `[ROLE:implementer]`, increment
   `final_rework_count`, rerun full regression, and invoke another fresh final audit.
5. Each final-audit rework consumes the configured final-rework budget; another `FINAL_FAIL` after
   exhaustion sets `BLOCKED_HUMAN`.
6. On `FINAL_PASS`, set `gates.final_audit_pass=true`; update the existing roadmap, mark the package
   complete, and fully prepare the next logical package. Set `phase=NEXT_PACKAGE` only for that
   preparation. Never implement it automatically.

## Final Git and merge

1. Set `phase=FINAL_GIT` and invoke `[ROLE:git-steward]`.
2. Before creating the PR, inspect the final status/diff, explicitly stage the roadmap, completion
   report, execution journal, and other authorized finalization edits, create a finalization commit,
   push it, and update `last_green_commit`. Never leave FINAL_PASS documents only in the worktree.
3. Fetch and detect base movement. If base changed, integrate it using allowed Git conventions.
   Fachliche conflicts return to implementer/reviewer; the steward never decides them.
4. Invalidate and rerun full regression after base integration. If the material diff changed,
   invalidate and rerun the final architect audit.
5. Create/update the PR, wait for required CI on the actual PR head, and set `gates.ci_pass=true`
   only when checks are green. CI code failures return through the normal implementer/reviewer loop.
6. Apply the bounded External Review lifecycle below.
7. Merge only with full regression PASS, final audit PASS, CI PASS, no human gate, work branch
   different from base, and an external-review mergeable state. Never bypass protection.
8. External mandatory approval that automation cannot satisfy sets `BLOCKED_HUMAN`.
9. After confirmed merge set `status=DONE`, retain final evidence, and stop. Do not start the next
   prepared package or delete branches automatically.

## External GitHub Codex review

Use `external_review` in config as the only numeric/provider policy. Codex is an additional final-PR
reviewer, never a replacement for checkpoint reviews, integration, regression, final audit or CI.

1. After finalization commit, push, PR and current-head CI, read PR head, reviews, review comments,
   issue comments and checks through safe read-only `gh` commands. Recognize only configured bot
   logins and bind every result to its actual reviewed commit.
2. Reuse an existing Codex review only when it covers the current PR head. If none exists and the
   feature is enabled, instruct `[ROLE:git-steward]` to post `@codex review` only within the
   configured request-per-round budget, then wait/poll only within configured limits. Never use
   mutating `gh api`. The guard atomically reserves the authorized request as `PENDING` and advances
   its round before allowing the command; after that reservation, including after resume, only wait
   for/read the result and never resend that round.
3. Usage-limit response -> `LIMIT_REACHED`; timeout/no response -> `UNAVAILABLE`; disabled provider
   -> `DISABLED`. These are mergeable only because config makes unavailability nonblocking; report
   them without retry, purchase/upgrade attempt or HUMAN_GATE.
4. Findings -> `FINDINGS` and use the configured triage-pass budget with a fresh
   `[ROLE:external-review-triager]` for the whole round.
   False positives, nonblocking or already-fixed findings require no source change and are recorded.
   Confirmed blockers produce one bundled minimal rework order; Codex itself never changes code and
   `@codex address that feedback` is never automated.
5. Material late changes invalidate full regression, final audit and CI. Run targeted/relevant/full
   tests, fresh Sol final audit, finalization commit/push and CI on the new head before the next
   configured external-review round. `PASS` becomes `STALE` whenever PR head changes.
6. Stop after the configured review/rework budgets. Never request another automatic Codex review;
   after a final confirmed rework, keep the new head `STALE` until full regression, a fresh internal
   final audit and current-head CI all pass. Then clear the repaired blocking findings and set
   `BOUNDED_COMPLETE` with `round=max_review_rounds`, `reviewed_head=null` and no open findings.
   Record the consumed rounds, last confirmed findings, repair evidence and green current-head gates
   in the execution journal. This terminal state explicitly means the repaired head was not reviewed
   by Codex because a third round is forbidden; it never claims external `PASS`. A normal
   requirement/architecture HUMAN_GATE still takes precedence.

Mergeable external states are `PASS` with `reviewed_head` equal to current PR head,
`BOUNDED_COMPLETE`, `UNAVAILABLE`, `LIMIT_REACHED`, and `DISABLED`. `NOT_REQUESTED` while enabled, `PENDING`,
`FINDINGS`, `STALE`, missing/unknown state, or PASS on another head are not mergeable.

## HUMAN_GATE output

Stop only for an established architecture/security/trust change, fundamental technology/framework,
destructive data ambiguity, materially ambiguous requirements, missing credentials/permissions,
failed escalation, failed final audit after the configured rework budget, or mandatory external
merge approval.
Report the concrete blocker, why it cannot be decided autonomously, current evidence, two or three
options, recommendation, and consequence of each.
