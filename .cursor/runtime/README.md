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
  `external_review.blocking_findings`, `external_review.last_checked_at`
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

## Document integration

Use the existing flat AP structure under `docs/`. Prefer existing ledger/evidence/final sections in
the owning AP document or its established companion report. Do not create
`docs/development/work-packages/`, a second roadmap, or a second ADR hierarchy.
