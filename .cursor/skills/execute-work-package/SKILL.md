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

## Checkpoint loop

Process checkpoints serially unless independent read-only exploration is clearly safe. Never allow
more than three parallel workers, overlapping edits, shared schemas/interfaces/migrations, or
dependent state changes.

### IMPLEMENT

1. Set `phase=IMPLEMENT`, current checkpoint, and concrete `next_action`.
2. Invoke the custom agent with a task beginning `[ROLE:implementer]`.
3. Supply the verbatim checkpoint, original package, in/out scope, invariants, acceptance criteria,
   allowlist, targeted commands, current status/diff, and attempt number.
4. Require changed files/responsibilities, behavior, exact tests/results, limitations, and open
   questions. The implementer makes no Git writes and cannot grant PASS.

### REVIEW

1. For the first review set `rework_count=0`, `phase=REVIEW`.
2. Capture the complete diff and pre-review repository fingerprint.
3. Invoke a fresh custom agent with a task beginning `[ROLE:checkpoint-reviewer]`.
4. Supply original checkpoint, architecture rules, complete diff, implementer report, relevant
   tests and primary evidence. The reviewer independently inspects and reruns relevant tests.
5. Require per-criterion PASS/FAIL with evidence plus Architecture Compliance, Regression Risk,
   Scope Compliance, Test Quality, Use Case Verification, fingerprints, and overall `PASS` or
   `FAIL`.
6. Limit each reviewer instance to one focused verification pass. In a rework review, prior failed
   findings and their relevant regression are primary. A newly noticed issue blocks only when it
   violates an existing acceptance criterion, demonstrates a realistic security/data-integrity
   bypass, or was introduced by the rework. Other hardening ideas are journaled as non-blocking
   follow-ups and do not trigger another rework.

### REWORK AND ESCALATION

- First normal `FAIL`: set `phase=REWORK`, `rework_count=1`; send only the reviewer's minimal order
  to `[ROLE:implementer]`, then run a fresh normal review.
- Second normal `FAIL`: set `phase=REWORK`, `rework_count=2`; perform one final bounded rework, then
  run a fresh normal review.
- If that review is still `FAIL`, set `phase=ESCALATION_REVIEW`, `escalation_used=true`, and invoke
  `[ROLE:escalation-reviewer]` exactly once with original request/checkpoint, architecture, complete
  diff, tests, all findings, and both reworks.
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

1. Set `phase=FULL_REGRESSION`; invalidate all final gates.
2. Run the complete relevant regression and all applicable package/architecture/build gates from
   P0 and the owning package. This repository currently has no linter/typechecker; mark those N/A
   rather than inventing tools.
3. Use Cursor Agent Review once before final audit for substantial changes when available. For
   security/auth/permission changes, additionally use the available Security Review. These are
   signals, not substitutes for checkpoint review.
4. Write the compact work-package completion report with execution path, criteria/use cases,
   changed files, exact verification, data/API/contract effects, limitations, debt, and scope.
5. Set `gates.full_regression_pass=true` only from real green evidence.

## Fresh final architect audit

1. Set `phase=FINAL_AUDIT`.
2. Invoke a fresh `[ROLE:roadmap-architect]` in `FINAL_AUDIT` mode with original package,
   checkpoints, journal, full base-branch diff, regression evidence, architecture rules, and final
   report.
3. Accept only `FINAL_PASS` or `FINAL_FAIL`.
4. On `FINAL_FAIL`, issue its concrete bounded order to `[ROLE:implementer]`, increment
   `final_rework_count`, rerun full regression, and invoke another fresh final audit.
5. Permit at most two final-audit reworks. A third `FINAL_FAIL` sets `BLOCKED_HUMAN`.
6. On `FINAL_PASS`, set `gates.final_audit_pass=true`; update the existing roadmap, mark the package
   complete, and fully prepare the next logical package. Set `phase=NEXT_PACKAGE` only for that
   preparation. Never implement it automatically.

## Final Git and merge

1. Set `phase=FINAL_GIT` and invoke `[ROLE:git-steward]`.
2. Fetch and detect base movement. If base changed, integrate it using allowed Git conventions.
   Fachliche conflicts return to implementer/reviewer; the steward never decides them.
3. Invalidate and rerun full regression after base integration. If the material diff changed,
   invalidate and rerun the final architect audit.
4. Create/update the PR, wait for required CI, and set `gates.ci_pass=true` only when checks are
   green. CI code failures return through the normal implementer/reviewer loop.
5. Merge only with full regression PASS, final audit PASS, CI PASS, no human gate, and work branch
   different from base. Never bypass protection.
6. External mandatory approval that automation cannot satisfy sets `BLOCKED_HUMAN`.
7. After confirmed merge set `status=DONE`, retain final evidence, and stop. Do not start the next
   prepared package or delete branches automatically.

## HUMAN_GATE output

Stop only for an established architecture/security/trust change, fundamental technology/framework,
destructive data ambiguity, materially ambiguous requirements, missing credentials/permissions,
failed escalation, failed final audit after two reworks, or mandatory external merge approval.
Report the concrete blocker, why it cannot be decided autonomously, current evidence, two or three
options, recommendation, and consequence of each.
