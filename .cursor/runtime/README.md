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
- `gates.full_regression_pass`, `gates.final_audit_pass`, `gates.ci_pass`

`updated_at` uses UTC ISO 8601. Set `human_gate=true` with `status=BLOCKED_HUMAN`. A manual Cursor
stop is represented by the hook input `status=aborted`; the stop hook then emits no follow-up.

## Document integration

Use the existing flat AP structure under `docs/`. Prefer existing ledger/evidence/final sections in
the owning AP document or its established companion report. Do not create
`docs/development/work-packages/`, a second roadmap, or a second ADR hierarchy.
