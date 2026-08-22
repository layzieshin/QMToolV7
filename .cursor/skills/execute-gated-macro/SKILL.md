---
name: execute-gated-macro
description: Execute an explicitly authorized QMToolV7 AP-029 macro as serial, independently reviewed checkpoints with separate frozen contracts, scope, evidence, configured bounded rework, and gated Git operations.
---

# Execute Gated Macro

Use this skill only for an explicitly authorized AP-029 macro. The macro is an orchestration
envelope, not permission to blend checkpoint changes.

Before acting, read:

- `AGENTS.md` and `.cursor/rules/00-agent-workflow.mdc`;
- `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md` and the master roadmap;
- `.cursor/skills/verify-reports-and-plan/SKILL.md`;
- [the checkpoint protocol](references/checkpoint-protocol.md).

## Invariants

- Run checkpoints serially in the authorized order.
- Give every checkpoint its own allowlist, evidence root, diff fingerprint, gate sequence,
  independent reviewer verdict and local commit after PASS unless the user explicitly opts out.
- Before source edits freeze `checkpoint-contract.md`, record its SHA256 in the journal, and review
  against it. Preserve old snapshots and formal amendments; never move acceptance criteria silently.
- Stop the macro on the first unresolved checkpoint.
- Use `.cursor/agent-system.json` as the normative source for remediation, reviewer, scope-correction,
  escalation, parallelism and model limits. AP-029 has no implicit numeric override.
- Do not infer permission for destructive tests, external writes, deployment, Echtdaten, human
  acceptance, cleanup, or branch deletion. A standalone macro keeps push/PR/merge separately
  gated; an explicit `/execute-work-package` parent may authorize only the hook-gated
  git-steward flow defined in the checkpoint protocol.
- Preserve foreign changes. Never use blanket staging, reset, restore, clean, stash, rebase or
  force-push.
- The primary Cursor agent passes its complete report and evidence directly to the native reviewer
  and returns one consolidated result. Never ask the user to copy, paste, forward or relay a report
  between agents.

## Reviewer identity (D15)

Invoke `checkpoint-reviewer` in a separate context via the native Cursor Task/subagent
mechanism. Reading the agent file or a main-agent self-review is not a reviewer run.

Require:

- every task begins `[ROLE:checkpoint-reviewer]`;
- selected model exactly `gpt-5.6-terra`;
- agent frontmatter `model: gpt-5.6-terra`;
- a new agent id captured by the parent from the native Task result and a separate context;
- `$verify-reports-and-plan`;
- evidence profile `RUNTIME_ATTESTED` or `CONTROL_PLANE_PINNED` before accepting a PASS;
- honest `UNAVAILABLE` when local runtime metadata is absent;
- never label `CONTROL_PLANE_PINNED` as observed runtime attestation;
- identical pre/post fingerprints; mutation ⇒ `BLOCKED`.

If the profile is `UNVERIFIED` or runtime metadata contradicts the pin, treat Gate E as blocked and
stop the macro for that checkpoint.

## Execution

1. Confirm branch/base/HEAD, empty staging, foreign changes, current ledger checkpoint and exact
   user authorization.
2. Create the `before` snapshot with `scripts/checkpoint_snapshot.py`; stop if out-of-scope paths
   are present and are not explicitly declared foreign changes.
3. Create the immutable checkpoint contract in the existing evidence root, hash it with
   `Get-FileHash`, record `contract_sha256`, then mark only the active checkpoint `IN_PROGRESS` and
   implement only its allowlist.
4. Run mandatory gates in order. At the first red/blocked gate, stop that sequence and preserve
   evidence.
5. Each bounded, decision-complete failure consumes the configured checkpoint-rework budget and
   runs a new complete gate sequence. After exhaustion, invoke the configured fresh
   `[ROLE:escalation-reviewer]`; escalation `FAIL` sets `BLOCKED_HUMAN`.
6. If implementer reports `SCOPE_CORRECTION_REQUIRED`, classify it before editing under the strict
   existing-owner/approved-criterion/no-new-behavior-or-surface rule. Record an allowed correction
   within the configured budget; otherwise treat it as Scope Expansion and stop for normal planning.
7. Create the `pre-review` snapshot and invoke the custom `checkpoint-reviewer` in a separate
   native Cursor Task. Pass the original plan, complete parent report, actual diff/status and
   primary evidence directly; never ask the user to relay them. Require its output contract and
   capture parent-owned Task metadata separately.
8. Create the `post-review` snapshot. Any repository-state or fingerprint delta caused during
   review makes the checkpoint `BLOCKED`; do not revert it automatically.
9. Accept only reviewer `PASS` with an accepted evidence profile. Reviewer `FAIL` supplies the
   minimal order and consumes the configured shared rework budget; correct it, rerun the affected gates,
   and invoke a fresh reviewer Task. After the budget, use the single escalation path above.
10. After PASS, update ledger/evidence, rerun the final documentation gate, stage exact allowed
   paths and create the local commit included by the implementation authorization unless the user
   opted out. Verify the commit file set.
11. Advance to the next checkpoint only when it is named by the same macro authorization.

Package Integration and External GitHub Codex Review remain owned by the outer
`/execute-work-package` lifecycle. Never run Codex after individual AP-029 subcheckpoints; evaluate
it only on the final package PR head.

Use the final report fields and status semantics in the checkpoint protocol. Report observed
parallel gate outcomes honestly; `NOT RUN` applies only to steps never started or never reached.
