---
name: execute-gated-macro
description: Execute an explicitly authorized QMToolV7 AP-029 macro as serial, independently reviewed checkpoints with separate scope, evidence, remediation budget, and local commits. Use only when the user names the macro/checkpoints and grants implementation permission; local commits follow the repository Git workflow, while push, PR, merge, destructive, deployment, and acceptance actions remain separately gated.
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
- Stop the macro on the first unresolved checkpoint.
- Permit at most one remediation round per checkpoint, regardless of whether it follows an
  implementation gate or reviewer finding.
- Do not infer permission for destructive tests, external writes, push, PR, review resolution,
  merge, deployment, Echtdaten, human acceptance, cleanup or branch deletion.
- Preserve foreign changes. Never use blanket staging, reset, restore, clean, stash, rebase or
  force-push.
- The primary Cursor agent passes its complete report and evidence directly to the native reviewer
  and returns one consolidated result. Never ask the user to copy, paste, forward or relay a report
  between agents.

## Reviewer identity (D15)

Invoke `qmtool-evidence-reviewer` in a separate context via the native Cursor Task/subagent
mechanism. Reading the agent file or a main-agent self-review is not a reviewer run.

Require:

- Task model slug exactly `gpt-5.6-luna-xhigh`;
- agent frontmatter `model: gpt-5.6-luna[effort=xhigh]`;
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
3. Mark only the active checkpoint `IN_PROGRESS` and implement only its allowlist.
4. Run mandatory gates in order. At the first red/blocked gate, stop that sequence and preserve
   evidence.
5. If the remediation budget is unused and the correction is bounded and decision-complete, apply
   one `R1` remediation and run a new complete gate sequence. Otherwise stop the macro.
6. Create the `pre-review` snapshot and invoke the custom `qmtool-evidence-reviewer` in a separate
   native Cursor Task. Pass the original plan, complete parent report, actual diff/status and
   primary evidence directly; never ask the user to relay them. Require its output contract and
   capture parent-owned Task metadata separately.
7. Create the `post-review` snapshot. Any repository-state or fingerprint delta caused during
   review makes the checkpoint `BLOCKED`; do not revert it automatically.
8. Accept only reviewer `PASS` with an accepted evidence profile. A bounded
   `REMEDIATION_REQUIRED` finding consumes the same single remediation budget: correct it, rerun
   the affected gates and invoke a fresh reviewer Task. Any other verdict stops the checkpoint.
9. After PASS, update ledger/evidence, rerun the final documentation gate, stage exact allowed
   paths and create the local commit included by the implementation authorization unless the user
   opted out. Verify the commit file set.
10. Advance to the next checkpoint only when it is named by the same macro authorization.

Use the final report fields and status semantics in the checkpoint protocol. Report observed
parallel gate outcomes honestly; `NOT RUN` applies only to steps never started or never reached.
