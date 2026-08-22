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

A clean local `main` that is only behind its exact `origin/main` upstream may use the two exact
`git pull --ff-only` forms documented in Rule 01. The Git guard rechecks branch, upstream, clean
worktree/index and zero-ahead ancestry; every other pull, divergence, extra flag, `git -C` or inline
directory change remains blocked.

## State and evidence

- Local resume state: `.cursor/runtime/workflow-state.json` (ignored)
- State contract: `.cursor/runtime/README.md`
- Package truth/evidence: owning AP document, execution/ledger section, final/acceptance report,
  commits, PR, and CI

The runtime file is never fachliche documentation.

`.cursor/agent-system.json` is the only normative source for role models and numeric workflow
limits. Rules, skills and this guide explain behavior; `hooks.json` contains only the
Cursor-schema projection required by the platform, protected against drift by contract tests.

## Planning quality

Every new package records `planning_risk_level` (`LOW`, `MEDIUM`, `HIGH`), Requirement
Traceability for fachliche/visible decisions, a compact Risk-to-Evidence matrix, relevant
cross-checkpoint seams, and a Package Integration Scenario or justified `N/A`. Auth/roles,
security/trust, productive persistence, migration/data loss, public API/transport,
schema/ownership, concurrency, backup/restore, secrets, deployment and central composition make a
package at least HIGH risk.

Configured HIGH-risk plans receive the bounded readonly Terra `plan-challenger` pre-mortem. It asks
whether green planned tests could still miss the confirmed requirement or architecture. Findings
return once to a fresh Sol Roadmap Architect for an evidenced response; no recursive challenger
loop is allowed. Missing material requirement sources or unresolved architecture choices are
HUMAN_GATEs. Running packages are not retroactively reopened; V2 applies prospectively from their
next not-started checkpoint.

## Checkpoint loop

Before source edits, the parent writes `checkpoint-contract.md` to the existing evidence root and
records its SHA256. It freezes source commit, goal/use case, scope, invariants, criteria, evidence
and requirement sources. Reviewer and final audit use that contract. A necessary change preserves
the old snapshot and creates a formal amendment/successor; material fachliche, architecture,
public-contract, security or persistence movement requires the applicable HUMAN_GATE.

`implementer` → independent `checkpoint-reviewer` → configured bounded rework → configured fresh
`escalation-reviewer`.

Escalation `FAIL` sets `BLOCKED_HUMAN`; no further automatic repair runs. A missing allowlisted
file may use Scope Correction only when it is an existing canonical owner directly required by an
approved criterion and adds no behavior, surface, architecture or technology; otherwise it is
Scope Expansion. After all checkpoints, the package integration scenario and full relevant
regression run before a fresh Sol final architect audit. Configured final-audit rework is bounded.
`FINAL_PASS` updates the existing roadmap and prepares—but does not
implement—the next package.

Only `git-steward` commits, pushes, creates/updates the PR, checks CI, and merges under persisted
gates. Branch protection is never bypassed.

### Review scope and cost control

Each normal reviewer performs the configured focused verification passes. A rework review primarily verifies
the previously failed finding and relevant regression. A new finding may block only when it breaks
an existing acceptance criterion, demonstrates a realistic security/data-integrity bypass, or was
introduced by the rework. Other parser variants, optional hardening, and speculative improvements
are recorded as follow-ups and do not extend the loop. Material new blockers consume the existing
rework budget; they do not create another budget.

## External GitHub Codex review

GitHub Codex is an additional independent layer on the final PR head after internal integration,
full regression, Sol final audit and current-head CI. It never runs after individual checkpoints
and never replaces internal evidence. Existing current-head reviews are reused; otherwise the Git
Steward may post the bounded `@codex review` request through `FINAL_GIT`. Reviews, inline comments,
issue comments, PR head and checks are read through safe `gh` paths; mutating `gh api` remains
forbidden.

Codex findings are claims. A fresh readonly Terra `external-review-triager` classifies them as
`CONFIRMED_BLOCKING`, `CONFIRMED_NONBLOCKING`, `FALSE_POSITIVE`, `OUTDATED_ALREADY_FIXED`, or
`INSUFFICIENT_EVIDENCE`. Only confirmed material violations create one bundled minimal implementer
rework; `@codex address that feedback` is never automated. Late source changes invalidate full
regression, final audit and CI, and make an older review `STALE`.

External state is `NOT_REQUESTED`, `PENDING`, `PASS`, `FINDINGS`, `STALE`, `BOUNDED_COMPLETE`, `UNAVAILABLE`,
`LIMIT_REACHED`, or `DISABLED`. `PASS` must match current PR head. With green internal gates,
`PASS`, `BOUNDED_COMPLETE`, `UNAVAILABLE`, `LIMIT_REACHED`, and `DISABLED` are mergeable under config;
`NOT_REQUESTED` while enabled, `PENDING`, `FINDINGS`, and `STALE` are not. Usage limit or bounded
timeout is reported without retry loop, purchase attempt or HUMAN_GATE. Review rounds and rework
batches stop at config limits. If the last permitted confirmed rework creates a new head after all
review rounds are consumed, it remains `STALE` until full regression, a fresh final audit and
current-head CI pass. Only then is it recorded as `BOUNDED_COMPLETE` with
`round=max_review_rounds`, no `reviewed_head`, no open findings and journaled repair evidence. The
status states that the repaired head was not reviewed because a third Codex round is forbidden; it
is not represented as external PASS.

## Cost profile

The balanced model map is centralized in config: Sol for roadmap/architecture, escalation and final
audit; Terra for checkpoint review, risk-triggered Plan Challenge and finding-triggered external
triage; Composer standard/non-fast for implementation and exploration; Luna for Git. Do not launch
a challenger for routine packages, a triager without findings, Codex per checkpoint, repeated
explorers on the same scope, review rounds beyond config, or full chat transcripts as evidence.

## HUMAN_GATEs

Cursor asks the user only for:

- a required established architecture/security/trust-model change;
- a fundamental new technology or central framework;
- a destructive data decision without an approved procedure;
- materially ambiguous requirements;
- missing credentials or external permissions;
- escalation `FAIL` after the configured normal rework budget;
- final-audit `FAIL` after the configured final rework budget;
- mandatory external merge approval or repository protection automation cannot satisfy.

Every gate report includes evidence, two or three options, recommendation, and consequences.

## Manual stop

Use Cursor Stop normally. The stop hook resumes only after `status=completed`; `aborted` and
`error` produce no follow-up. `BLOCKED_HUMAN`, `DONE`, or `human_gate=true` also disable automatic
continuation. The follow-up limit comes from `.cursor/agent-system.json`.

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
