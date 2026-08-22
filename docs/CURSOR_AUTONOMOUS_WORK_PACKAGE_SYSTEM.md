# Cursor Autonomous Work Package System

QMToolV7 uses Cursor-native Project Rules, Skills, Custom Agents, Hooks, Worktrees, Agent Review,
GitHub tooling, and one small ignored runtime-state file. It does not contain a custom agent runner,
queue, workflow engine, or agent database.

## Normal use

- Change direction or roadmap: `/maintain-roadmap <direction>`
- Start or resume an approved package: `/execute-work-package <WP-ID>`
- Change role models:
  1. edit `.cursor/agent-system.json`;
  2. run `/apply-agent-profile`.

The roadmap remains `docs/MASTER_ORCHESTRATION_ROADMAP.md` plus the active transition plan.
Specifications, decisions, execution evidence, and final evidence stay in the established flat
`docs/AP-*` documents or their existing companion reports.

## State and evidence

- Local resume state: `.cursor/runtime/workflow-state.json` (ignored)
- State contract: `.cursor/runtime/README.md`
- Package truth/evidence: owning AP document, execution/ledger section, final/acceptance report,
  commits, PR, and CI

The runtime file is never fachliche documentation.

## Checkpoint loop

`implementer` → independent `checkpoint-reviewer` → at most two bounded reworks → one fresh
`escalation-reviewer`.

Escalation `FAIL` sets `BLOCKED_HUMAN`; no further automatic repair runs. After all checkpoints,
full relevant regression runs before a fresh Sol final architect audit. At most two final-audit
reworks are allowed. `FINAL_PASS` updates the existing roadmap and prepares—but does not
implement—the next package.

Only `git-steward` commits, pushes, creates/updates the PR, checks CI, and merges under persisted
gates. Branch protection is never bypassed.

### Review scope and cost control

Each normal reviewer performs one focused verification pass. A rework review primarily verifies
the previously failed finding and relevant regression. A new finding may block only when it breaks
an existing acceptance criterion, demonstrates a realistic security/data-integrity bypass, or was
introduced by the rework. Other parser variants, optional hardening, and speculative improvements
are recorded as follow-ups and do not extend the loop. Material new blockers consume the existing
rework budget; they do not create another budget.

## HUMAN_GATEs

Cursor asks the user only for:

- a required established architecture/security/trust-model change;
- a fundamental new technology or central framework;
- a destructive data decision without an approved procedure;
- materially ambiguous requirements;
- missing credentials or external permissions;
- escalation `FAIL` after two normal reworks;
- final-audit `FAIL` after two final reworks;
- mandatory external merge approval or repository protection automation cannot satisfy.

Every gate report includes evidence, two or three options, recommendation, and consequences.

## Manual stop

Use Cursor Stop normally. The stop hook resumes only after `status=completed`; `aborted` and
`error` produce no follow-up. `BLOCKED_HUMAN`, `DONE`, or `human_gate=true` also disable automatic
continuation. The configured follow-up limit is eight.

## Cursor limitations

- `sessionStart` injects context but cannot block startup and is unavailable to Cloud Agents.
- Shell hooks protect only Git operations executed through Cursor's shell path; server-side branch
  protection remains authoritative for external/UI Git actions.
- `beforeShellExecution` does not expose the calling custom-agent identity. Role contracts assign
  all Git writes exclusively to `git-steward`, while the hook can technically enforce only command,
  phase, branch, and persisted gates. It cannot cryptographically prove which agent issued an
  otherwise allowed command.
- Agent Review is an additional signal, not a hard merge gate by itself.
- Cursor/admin/plan restrictions can substitute a configured model. `subagentStart` rejects obvious
  tagged-role deviations, but cannot manufacture unavailable entitlement.
- The worktree setup is Windows-local and creates an ordinary `.venv` from the repository's
  documented requirements; secrets such as `.env` are not copied.
