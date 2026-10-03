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

## Execution host and temporary paths

Before the first package edit, `.cursor/tools/assert-execution-host.ps1` verifies the exact opened
registered worktree, attached branch, optional central Git-metadata write access, and a real Python
child temp roundtrip. When another coordinator must start Cursor CLI, it additionally checks that
the Cursor session store is writable and that the process is not routed through a disabled local
proxy. `EXECUTION_HOST_REQUIRED` stops before edits, reviews, or retries; automation never clears
proxy/sandbox controls or moves an already checked-out branch between worktrees.

`.cursor/tools/invoke-cursor-agent.ps1` is the only supported nested CLI launcher. It performs that
preflight, sets the child process `WorkingDirectory` to the validated target root, and runs Cursor
synchronously in the specified target, preserving the prompt as one argument so no detached writer
or split command-line option remains. Opt-in `-Interactive` omits non-interactive `--print` and
`--output-format`; `-ResumeSession` passes through to `cursor-agent --resume`. Coordinators and
`git-steward` must set native Shell `working_directory` on every call. Normally the already opened
Cursor workspace executes `/execute-work-package` directly and needs no nested CLI.

Ordinary Python work-package gates use `.cursor/tools/run-pytest-gate.ps1`. It allocates unique,
short repository-local process-temp and basetemp paths and owns optional JUnit output. Direct
pytest remains supported; `conftest.py` assigns a unique `build/pt/<pid>-<token>` default unless a
caller deliberately supplies `--basetemp`. Guarded PostgreSQL/J04 runners keep their stricter fresh
basetemp contract.

## Codex implementation entry

Authorized implementation packages that originate in the Codex IDE extension enter the existing
Cursor workflow through the same launcher and coordinator roles. Codex keeps questions, reviews,
architecture and planning; only bounded implementation work crosses into Cursor.

### Supported fresh-package invocation

Approval source, branch, and full HEAD must be fixed before launch. Example for a coordinator-owned
fresh entry at a new package boundary:

```powershell
& .\.cursor\tools\invoke-cursor-agent.ps1 `
  -TargetRoot I:\Projekte\QMToolV7-codex-cursor-entry `
  -WorkPackage codex-cursor-entry `
  -ExpectedBranch feature/codex-cursor-entry `
  -ExpectedHead 9939c96657f6a22f2fa594d4ffbccbd988a5a673 `
  -Prompt "<commissioned implementation prompt from the approving orchestrator>"
```

`-WorkPackage`, `-ExpectedBranch`, and `-ExpectedHead` form one complete binding group.
`-WorkPackage` is a binding label only; it is not an implicit `/execute-work-package` command or
broader Git authorization. The supplied task prompt carries the original approved scope. The
launcher requires the target's canonical `invoke-cursor-agent.ps1`, `agent-system.json`, and
`.cursor/runtime/workflow-state.json`, an attached branch matching the immutable 40-hex SHA, a clean
fresh target, and known inactive `IDLE` or completed `DONE` workflow state with no `human_gate` or
conflicting ownership. It rejects protected `main`/`master` targets, partial/blank binding,
branch-name `ExpectedHead`, malformed state, redirected hook/Git owner variables such as
`QMTOOL_WORKFLOW_STATE_PATH`, `QMTOOL_RUNTIME_LOG_PATH`, `GIT_DIR`, `GIT_WORK_TREE`,
`GIT_COMMON_DIR`, or `GIT_INDEX_FILE`, reparse-point redirected canonical launcher/config/runtime
owners, and any `-ResumeSession` combination. Generic prompt and resume calls without the binding
group keep their existing supported behavior; this path does not implement automatic package
resume. State/owner checks plus the child's immediate recheck are not an atomic exclusive-writer lock.

The child receives the binding in its prompt and must recheck identity/ownership before any edit.
The coordinator model comes only from the target's `.cursor/agent-system.json`
(`routing.coordinator_model`); the launcher does not expose a user-facing model parameter.
Opt-in `-AutoReview` forwards Cursor's native `--auto-review` only and cannot combine with `-Force`.

### Evidence and limits

Start/result lines append to
`build/codex-cursor-entry/<work-package>/execution-journal.md` with one launcher-generated
`launch_correlation_id` per attempt (not a native Cursor task/session id). The journal keeps
requested model, observed child executable/working-directory/process id or start-failure outcome,
native task/session evidence (`unknown` unless separately attested), and package result
(`unverified`) distinct. Launcher exit `0` never means package `DONE`, reviewer `PASS`, or runtime
model attestation. Failed entry never starts a child and never rewrites
`.cursor/runtime/workflow-state.json`.

Invoking the launcher does not grant push, PR, merge, or branch deletion. Those remain separately
user-gated. A launcher smoke from a trusted Cursor host proves only that entry host; the Codex IDE
extension path remains **NOT RUN** until exercised there.

Activation applies at a new package boundary in a fresh Codex chat after integration. Existing
UI/PILOT00 attempts, contracts, counters, runtime and acceptance states are preserved.

## State and evidence

- Local resume state: `.cursor/runtime/workflow-state.json` (ignored)
- State contract: `.cursor/runtime/README.md`
- Package truth/evidence: owning AP document, execution/ledger section, final/acceptance report,
  commits, PR, and CI

The runtime file is never fachliche documentation.

`.cursor/agent-system.json` is the only normative source for role models and numeric workflow
limits. The integrated `cursor-first` v3 profile (AGENT-COST-01, PR #60) applies to new packages
at the documented safe boundary. Composer 2.5
Standard carries routine execution; Grok review roles use the normalized ladder in
`review_model_fallback` beginning at attempt 1 `grok-4.7-high` (no hidden attempt 0 and no legacy
`grok-4.7-xhigh` route). Critical final audit for packages in `routing.ag_packages_critical` routes
**directly** to the external Codex/ChatGPT-authenticated orchestrator; exhausted checkpoint escalation
follows the applicable configured `checkpoint-reviewer` ladder (and Cursor GPT rung when configured)
before external handoff. `main` now contains v3; existing worktrees/attempts retain their started
profile until an explicitly approved transition, never an automatic retrofit.
Rules, skills and this guide explain behavior; `hooks.json` contains only the
Cursor-schema projection required by the platform, protected against drift by contract tests.

## Planning quality

Every new package records `planning_risk_level` (`LOW`, `MEDIUM`, `HIGH`), Requirement
Traceability for fachliche/visible decisions, a compact Risk-to-Evidence matrix, relevant
cross-checkpoint seams, and a Package Integration Scenario or justified `N/A`. Auth/roles,
security/trust, productive persistence, migration/data loss, public API/transport,
schema/ownership, concurrency, backup/restore, secrets, deployment and central composition make a
package at least HIGH risk.

Configured HIGH-risk plans receive the bounded readonly `plan-challenger` pre-mortem (Grok under
`cursor-first`). It asks whether green planned tests could still miss the confirmed requirement or
architecture. Findings return once to a fresh roadmap architect for an evidenced response; no
recursive challenger loop is allowed. Missing material requirement sources or unresolved architecture choices are
HUMAN_GATEs. Running packages are not retroactively reopened; V2 applies prospectively from their
next not-started checkpoint.

## Checkpoint loop

Before source edits, the parent writes `checkpoint-contract.md` to the existing evidence root and
records its SHA256. It freezes source commit, goal/use case, scope, invariants, criteria, evidence
and requirement sources. Reviewer and final audit use that contract. A necessary change preserves
the old snapshot and creates a formal amendment/successor; material fachliche, architecture,
public-contract, security or persistence movement requires the applicable HUMAN_GATE.

`implementer` → independent `checkpoint-reviewer` → configured bounded rework → native
`escalation-reviewer` local pre-handoff validation (`PRE_HANDOFF_READY`) → external Codex result →
locally bound `HANDOFF_READY`/`HANDOFF_INVALID` when routing requires `EXTERNAL_CODEX_BOUND_REVIEW`.

Four operational external routes share one registry owner
(`external_codex_bound_review.review_route_bindings`): W1 checkpoint escalation after a complete
UNAVAILABLE ladder; FINAL_AUDIT direct external with no ladder history; budget-FAIL recovery
diagnosis (`RECOVERY_DIAGNOSIS` → `RECOVERY_DIAGNOSIS_READY` → `RECOVERY_PROPOSAL_BOUND` only); and
native review that never substitutes external PASS. PRE computes `bindingRecord`; the coordinator
anchors it once in `external_review.bindingRecord`; BOUND and recovery receipt reuse that anchored
record plus existing `manifest-validate`. Diagnosis receipts alone do not grant resume, implement,
commit, `HANDOFF_READY`, or `CONTINUE`. A separately commissioned, runtime-validated technical
recovery batch permits bounded repair under the protocol below, never review PASS or Git authority.

Resume a running package only after `context-manifest.json` validates with
`checkpoint_snapshot.py manifest-validate --allow-reuse --verify-command "<exact normalized gate>"`
on a still-matching context. Repeat `--verify-command` for every expected normalized gate; missing or
wrong commands fail closed. The manifest remains an index; stale manifests block reuse of completed
green checkpoints; do not repeat steps, re-ask authorization, or re-reserve reviews when reuse is valid.

For the PILOT00 packages named in `checkpoint-protocol.md`, the native role is
still preferred. If that role returns explicit `UNAVAILABLE`, one separate
read-only `INDEPENDENT_ORCHESTRATOR_REVIEW` may fill the same responsibility.
The author of the diff cannot be that reviewer. The label is not a Terra or Sol
PASS and not a new budget.

Diagnosis, bundled repair and technical recovery have one protocol owner:
`.cursor/skills/execute-gated-macro/references/checkpoint-protocol.md`. Red blocks acceptance and
dependent progression while safe authorized diagnosis continues. Explicit autonomous mandates bound
to package/checkpoint/contract cover engineering recovery within configured
`max_technical_recovery_batches`, without consent per finding. Old blocked/stopped attempts need
explicit approved resume and retain counters/evidence. Existing-owner Scope Correction may meet
approved criteria without behavior outside them or unapproved surface/architecture/technology;
preserve an amendment. Genuine decisions remain HUMAN_GATEs. Satisfy package integration/full relevant
regression before a fresh final audit under configured routing. Internal/external FAIL share the
bounded repair policy; neither grants self-PASS.
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

Report token, cost, cache-hit, savings, runtime serving model, and reasoning effort as
`UNKNOWN`/`UNAVAILABLE` unless the host measured or attested them in primary evidence. Never claim
zero cost, cache activity, or savings without measurement. An untagged helper never implies complete
workflow cost coverage.

## External GitHub Codex review

GitHub Codex is an additional independent layer on the final PR head after internal integration,
full regression, Sol final audit and current-head CI. It never runs after individual checkpoints
and never replaces internal evidence. Existing current-head reviews are reused; otherwise the Git
Steward may post the bounded `@codex review` request through `FINAL_GIT`. Reviews, inline comments,
issue comments, PR head and checks are read through safe `gh` paths; mutating `gh api` and local
`gh pr review` submission remain forbidden. Merge uses only `gh pr merge <number> --squash` under
persisted gates.

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

`.cursor/agent-system.json` is the only normative model-map owner.

### AGENT-COST-01 qualification vs activation

| Phase | Where | Profile | What changes |
| --- | --- | --- | --- |
| Qualification (pre-merge) | `feature/cursor-agent-system-v3` branch candidate | `cursor-first` v3 | Branch-local proof only; `main` stays `balanced` v2 |
| Activation (post-merge) | `main` after squash-merge + documented safe transition | `cursor-first` v3 effective | **New** checkpoints/packages only |

Qualification **before** squash-merge installs and proves the frozen candidate on the isolated branch.
Activation **after** merge applies the documented safe transition; it does not retrofit running
packages or PILOT00 B1.

Actual activation (2026-10-02): [PR #60](https://github.com/layzieshin/QMToolV7/pull/60) merged
as `6b5653d44a73e57adc0d1b8f00650e689c29f303`, with both CI checks green on the final source.
`cursor-first` v3 is **ACTIVE FOR NEW PACKAGES** only after their workspace adopts integrated
`main` and starts a fresh approved package/checkpoint contract and state. All eight role models
already match the JSON; no serving identity or cost result is implied. The cancelled recovery
runtime remains `IDLE`; PILOT00, historical evidence and other worktrees are unchanged.

On the branch-local `cursor-first` v3 candidate, Composer 2.5 Standard carries routine Cursor
execution. Routine independent reviews use the normalized Grok ladder in `review_model_fallback`
beginning at `grok-4.7-high`. Critical final audit for packages in `routing.ag_packages_critical`
routes to the external Codex/ChatGPT-authenticated orchestrator; exhausted checkpoint escalation
follows the applicable configured `checkpoint-reviewer` ladder (and configured Cursor GPT rung when
present) before external handoff. External Codex is coordination, architecture, and critical final
audit — not a Cursor model ID, `RUNTIME_ATTESTED`, or `CONTROL_PLANE_PINNED`.

Serving model, token cost, cache hit rate, 50:50 usage, and billing remain **UNKNOWN** unless the
host measured or attested them in primary evidence. Never invent zero cost, cache activity, savings,
or serving-model claims. An untagged helper never implies complete workflow cost coverage.

Do not launch a challenger for routine packages, a triager without findings, Codex per checkpoint,
repeated explorers on the same scope, review rounds beyond config, or full chat transcripts as
evidence.

## HUMAN_GATEs

Cursor asks the user only for:

- a required established architecture/security/trust-model change;
- a fundamental new technology or central framework;
- a destructive data decision without an approved procedure;
- materially ambiguous requirements;
- missing credentials or external permissions;
- unresolved failure after applicable repair/escalation/authorized recovery limits or no justified
  new repair approach;
- recovery without concrete package/checkpoint/contract-bound autonomy or resume authorization;
- mandatory external merge approval or repository protection automation cannot satisfy.

Bundle genuine decisions with evidence, options, recommendation and consequences. Engineering defaults
and already authorized repairs need no new consent; continue independent authorized work.

## Manual stop

Use Cursor Stop normally. The stop hook resumes only after `status=completed`; `aborted` and
`error` produce no follow-up. `BLOCKED_HUMAN`, `DONE`, or `human_gate=true` also disable automatic
continuation. The follow-up limit comes from `.cursor/agent-system.json`.

## Cursor limitations

Local repair closure (2026-10-02): the complete `tests/docs` verification passed 252 tests
with no failures, errors or skips (`build/agent-cost-01/agent-rework-direct-final-junit.xml`).
This result is the pre-publication repair baseline; later PR #60 follow-up is recorded in the cost
profile. SessionStart blocks
Resume for actual recovery-diagnosis bindings as well as recovery receipts, while normal
Resume remains supported. Implementer RUNNING-state, canonical role, model and identity checks
remain mandatory; external-review registry preflight applies to actual external handoffs only.
The cancelled chain is stopped and operational state is `IDLE`; historical counters and
review outcomes are not reset or relabelled. Subsequent explicit human authorization, actual
PR #60 integration and the safe transition above establish activation for new packages only;
PILOT00 and serving/cost qualification remain unchanged.

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
