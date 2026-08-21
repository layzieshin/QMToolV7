# AP-029 Checkpoint Protocol

## Status and sequencing

Allowed ledger statuses are `TODO`, `IN_PROGRESS`, `PASS`, `FAILED` and `BLOCKED`. Only one
checkpoint may be active. A green focused test never promotes a parent checkpoint by itself.

After the first mandatory red or blocked gate:

- do not start another gate in that sequence;
- preserve the evidence and first error;
- report already-running gates by their observed results;
- use `NOT RUN` only for never-started or never-reached work;
- record any fail-fast violation separately.

One remediation round means one bounded change set followed by a new gate sequence. An isolated
diagnostic is not a PASS and may not silently become a retry. Once the remediation budget is used,
any further non-PASS result stops the macro.

## Evidence layout

Use `build/ap-029-<checkpoint-id-lower>/` and unique attempt subdirectories. Never overwrite an
earlier result. Each checkpoint records:

- base, start and end HEAD; branch and divergence;
- allowlist, actual changed paths and foreign preserved paths;
- before, pre-review and post-review snapshot JSON;
- commands, exit codes, counts, skips/errors, JUnit and logs;
- first-red and later `NOT RUN` steps;
- reviewer configured/observed model, verdict and findings;
- remediation count;
- final commit SHA/file set when commit permission exists;
- remaining limitations and separately gated actions.

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
Requested model: gpt-5.6-luna-xhigh
Return the qmtool-evidence-reviewer output contract including D15 evidence_profile.
Do not mutate repository state.
```

Launch the reviewer as a native Cursor Task/subagent with model slug `gpt-5.6-luna-xhigh` in a
separate context. The primary Cursor agent sends the handoff directly, waits for the result and
returns one consolidated report; never ask the user to copy, paste, forward or relay between
agents. Capture `agent_id` from the native Task result. The reviewer does not need shell access or
visibility into its own Task id; unavailable self-observation alone is not a content blocker.
Accept Gate E only when `evidence_profile` is
`RUNTIME_ATTESTED` or `CONTROL_PLANE_PINNED` and `reviewer_verdict` is `PASS`. Treat
`CONTROL_PLANE_PINNED` as control-plane binding, never as observed runtime attestation. If
`evidence_profile` is `UNVERIFIED` or fingerprints diverge, Gate E is blocked.

Required reviewer content fields: `agent_name`, `configured_model`,
`requested_model`, `observed_runtime_model`, `observed_reasoning`, `evidence_profile`,
`contradictory_metadata`, `reviewer_verdict` and findings. Parent-owned fields are `agent_id`,
`separate_context`, `pre_fingerprint`, `post_fingerprint` and `mutation_detected`; capture them from
the native Task lifecycle instead of requiring reviewer self-attestation.

## Commit boundary

Commit only after reviewer PASS and only when the user's macro authorization explicitly permits a
local commit. Stage every path by name, compare the staged path list with the checkpoint allowlist,
then commit. Push and PR are separate permissions even if the local commit is green.

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
