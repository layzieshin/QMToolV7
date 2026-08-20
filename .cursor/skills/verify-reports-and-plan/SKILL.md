---
name: verify-reports-and-plan
description: Independently verify implementation, checkpoint, acceptance, CI, pull-request, or completion reports against the real repository and external evidence; classify what is proven, failed, blocked, or not run; then produce the smallest fail-fast next-step plan and a self-contained prompt for Cursor or another coding agent. Use when a user asks to review a report, assess whether work is actually complete or merge-ready, determine what comes next, or turn findings into an executable gated work package.
---

# Verify Reports and Plan

## Purpose

Treat every report as a set of claims to verify, not as proof. Establish the current source, Git, test, CI, review, and authorization state before accepting a status or planning the next action.

## Workflow

### 1. Establish the governing context

- Read repository instructions and the active plan, ledger, roadmap, or acceptance document.
- Identify the actual repository, worktree, branch, base, expected head, and task boundary.
- Distinguish review, diagnosis, implementation, monitoring, acceptance, and publication requests.
- Preserve unrelated dirty files. Never infer permission for commit, push, PR writes, destructive tests, approval, conversation resolution, merge, deployment, or cleanup.

### 2. Convert the report into verifiable claims

Extract at least:

- branch, head, base, divergence, staging, and changed-file manifest;
- claimed behavior and its existing owner/execution path;
- commands, test counts, skips, failures, timestamps, JUnit/log paths, and code hashes;
- CI status, PR head, review threads, branch policy, mergeability, and deployment state when relevant;
- explicit exclusions, human gates, destructive-run counts, and authorization boundaries.

Mark each claim `VERIFIED`, `PARTIAL`, `UNSUPPORTED`, `CONTRADICTED`, `FAILED`, `BLOCKED`, or `NOT RUN`.

### 3. Verify independently and proportionately

- Inspect current files and diffs instead of trusting summaries.
- Compare `git status`, staged paths, commit contents, local/remote heads, and PR head.
- Read primary evidence such as JUnit, logs, check runs, review threads, and exact error traces.
- Run small read-only or non-destructive focused checks when they materially resolve uncertainty.
- Verify that a green CI run belongs to the reported head SHA.
- Verify that a claimed fix has a regression test that protects the intended contract.
- Verify ownership and scope: extend existing API, service, route, client, and test owners rather than duplicating them.

Do not repeat expensive, destructive, live, or human-interactive gates merely to validate a report. Inspect their preserved evidence unless a new run is explicitly authorized.

### 4. Apply first-red and evidence semantics

- After the first mandatory red or blocked gate, do not start any further gates.
- Keep the parent checkpoint `FAILED` or `BLOCKED`; do not promote it because a later gate is green.
- Report every later mandatory gate that already ran in parallel and has primary evidence with its actual observed outcome (`PASS`, `FAILED`, or `BLOCKED`). Do not relabel that evidence as `NOT RUN`.
- Mark only never-started or never-reached steps `NOT RUN`; do not infer an unobserved outcome.
- If later gates were started after the first red or blocked mandatory gate, document that fail-fast violation separately from the gate outcomes.
- Preserve historical red evidence when a later remediation passes.
- Do not hide failures with retries, longer timeouts, skipped tests, weakened policy, broad exception handling, or changed assertions.
- Classify an environmental failure only with concrete evidence such as an unchanged code path, isolated pass, no overlapping process, fresh workspace, and a matching OS or tool error. Otherwise leave the cause open.
- Treat same-process tests, real-process tests, packaging, visible human smoke, production checks, and formal acceptance as different evidence levels.

### 5. Determine the exact status

Keep these statuses separate:

- sub-checkpoint PASS;
- parent checkpoint PASS or IN_PROGRESS;
- overall READY or NOT_READY;
- technically mergeable versus policy-clean;
- merged versus deployed;
- technical verification versus human `Accepted`.

Never promote technical evidence to formal human acceptance. Never call a PR ready when its current head, CI, conversations, or policy state says otherwise.

### 6. Plan the smallest next checkpoint

Define one bounded next action with:

- objective and formal status transition;
- exact allowed file or action scope and explicit exclusions;
- preflight checks;
- ordered implementation or diagnostic steps;
- focused gates followed by the required broader gate;
- fail-fast behavior;
- Definition of Done and evidence/report format;
- actions requiring separate authorization.

Do not mix remediation, freeze, destructive rerun, publication, review resolution, merge, deployment, or branch cleanup unless the user explicitly authorized each applicable action.

### 7. Produce a self-contained agent prompt

End with a copyable prompt for Cursor or another agent when the user wants work delegated. Include:

- repository, branch, expected head, and checkpoint name;
- verified starting state and objective;
- exact allowed and forbidden files or actions;
- implementation or diagnostic requirements without speculative fixes;
- precise commands when the repository defines them;
- unique evidence locations and result counts to report;
- fail-fast and retry rules;
- commit, push, PR, review, merge, deployment, and acceptance permissions;
- required final report fields.

If a critical product choice is unresolved, present the tradeoff and request the decision before emitting an executable implementation prompt. If only a gated action remains, provide the exact authorization sentence separately.

## Output contract

Lead with the verdict. Then report:

1. what is independently verified;
2. discrepancies, open risks, and evidence limitations;
3. the formal current status;
4. the smallest next step and why;
5. the copyable follow-up prompt or exact authorization sentence.

Use links to local files and external PRs when available. Keep commentary concise; make the final answer self-contained.

For complex checkpoints, PR closure, or multi-gate acceptance, read [evidence-and-prompt-patterns.md](references/evidence-and-prompt-patterns.md).
